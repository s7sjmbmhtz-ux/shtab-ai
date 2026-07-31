import httpx
import asyncio
import json
import base64
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from settings import settings
from models import (
    GenerationStatus, AIResponse, ResponseType,
    ImageResponse, AudioFile
)
from utils import logger


class AIProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> AIResponse:
        pass


class TextProvider(AIProvider):
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.api_key = settings.GENAPI_API_KEY
        self.base_url = settings.GENAPI_BASE_URL

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError, asyncio.TimeoutError))
    )
    async def _make_request(self, prompt: str, model: str, temperature: float) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature
        }

        timeout = getattr(settings, 'AI_TIMEOUT', 120)

        response = await self.client.post(
            f"{self.base_url}/api/v1/networks/{model}",
            headers=headers,
            json=payload,
            timeout=timeout
        )
        response.raise_for_status()
        data = response.json()
        
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0].get("message", {}).get("content", "")
        return data.get("result", data.get("response", str(data)))

    async def generate(self, prompt: str, **kwargs) -> AIResponse:
        model = kwargs.get("model", settings.FREE_TEXT_MODEL)
        temperature = kwargs.get("temperature", 0.7)

        try:
            start_time = asyncio.get_event_loop().time()
            content = await self._make_request(prompt, model, temperature)
            elapsed = asyncio.get_event_loop().time() - start_time

            if not content:
                return AIResponse(
                    content="",
                    provider="genapi",
                    model=model,
                    status=GenerationStatus.EMPTY_RESPONSE,
                    response_type=ResponseType.TEXT
                )

            return AIResponse(
                content=content,
                provider="genapi",
                model=model,
                elapsed=elapsed,
                status=GenerationStatus.SUCCESS,
                response_type=ResponseType.TEXT
            )
        except Exception as e:
            logger.error(f"❌ Ошибка генерации текста: {e}")
            return AIResponse(
                content="",
                provider="genapi",
                model=model,
                status=GenerationStatus.ERROR,
                metadata={"error": str(e)},
                response_type=ResponseType.TEXT
            )


class ImageProvider(AIProvider):
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.api_key = settings.GENAPI_API_KEY
        self.base_url = settings.GENAPI_BASE_URL

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError, asyncio.TimeoutError))
    )
    async def _make_request(self, prompt: str, size: str, model: str) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "prompt": prompt,
            "size": size,
            "n": 1
        }

        timeout = getattr(settings, 'AI_TIMEOUT', 120)

        response = await self.client.post(
            f"{self.base_url}/api/v1/networks/{model}",
            headers=headers,
            json=payload,
            timeout=timeout
        )
        response.raise_for_status()
        return response.json()

    async def generate(self, prompt: str, **kwargs) -> AIResponse:
        size = kwargs.get("size", "1024x1024")
        model = kwargs.get("model", settings.FREE_IMAGE_MODEL)

        try:
            start_time = asyncio.get_event_loop().time()
            result = await self._make_request(prompt, size, model)
            elapsed = asyncio.get_event_loop().time() - start_time

            image_url = None
            if result.get("data") and isinstance(result["data"], list):
                image_url = result["data"][0].get("url")
                if not image_url and result["data"][0].get("b64_json"):
                    b64_data = result["data"][0]["b64_json"]
                    image_url = f"data:image/png;base64,{b64_data}"

            if not image_url:
                return AIResponse(
                    content="",
                    provider="genapi",
                    model=model,
                    status=GenerationStatus.EMPTY_RESPONSE,
                    response_type=ResponseType.IMAGE,
                    metadata={"error": "URL изображения не найден"}
                )

            response_data = {
                "type": "image",
                "url": image_url,
                "size": size,
                "prompt": prompt
            }

            return AIResponse(
                content=json.dumps(response_data, ensure_ascii=False),
                provider="genapi",
                model=model,
                elapsed=elapsed,
                status=GenerationStatus.SUCCESS,
                response_type=ResponseType.IMAGE,
                metadata=response_data
            )

        except Exception as e:
            logger.error(f"❌ Ошибка генерации изображения: {e}")
            return AIResponse(
                content="",
                provider="genapi",
                model=model,
                status=GenerationStatus.ERROR,
                response_type=ResponseType.IMAGE,
                metadata={"error": str(e)}
            )


class VideoProvider(AIProvider):
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.api_key = settings.GENAPI_API_KEY
        self.base_url = settings.GENAPI_BASE_URL
        self.max_wait_time = 600  # 10 минут на генерацию видео

    async def _check_status(self, request_id: str) -> Dict[str, Any]:
        """Проверка статуса видео по request_id."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}/api/v1/request/get/{request_id}"
        logger.info(f"🔍 Проверка статуса: {url}")
        
        response = await self.client.get(
            url,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError, asyncio.TimeoutError))
    )
    async def _make_request(self, prompt: str, model: str, **kwargs) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # ============================================================
        # БАЗОВЫЙ PAYLOAD
        # ============================================================
        duration = kwargs.get("duration", 5)
        
        # Для Veo и Luma duration всегда со строкой "s"
        if model in ["veo-3.1", "veo-3-1-lite", "luma"]:
            duration = f"{duration}s"
        
        payload = {
            "callback_url": None,
            "prompt": prompt,
            "duration": duration
        }
        
        # ============================================================
        # LTX 2.3
        # ============================================================
        if model == "ltx-2-3":
            payload.update({
                "mode": kwargs.get("mode", "pro"),
                "resolution": kwargs.get("resolution", "1080p"),
                "aspect_ratio": kwargs.get("aspect_ratio", "16:9"),
                "fps": 25,
                "generate_audio": True
            })
        
        # ============================================================
        # CogVideoX 5B
        # ============================================================
        if model == "cog-video-x-5b":
            payload.update({
                "width": kwargs.get("width", 720),
                "height": kwargs.get("height", 480),
                "negative_prompt": kwargs.get("negative_prompt", "Distorted, discontinuous, Ugly, blurry, low resolution, motionless, static, disfigured, disconnected limbs, Ugly faces, incomplete arms"),
                "num_inference_steps": kwargs.get("num_inference_steps", 50),
                "guidance_scale": kwargs.get("guidance_scale", 7),
                "seed": kwargs.get("seed", -1),
                "use_rife": kwargs.get("use_rife", True),
                "export_fps": kwargs.get("export_fps", 30)
            })
        
        # ============================================================
        # Kling Video O3
        # ============================================================
        if model == "kling-video-o3":
            payload.update({
                "model": kwargs.get("model_type", "text-to-video"),
                "aspect_ratio": kwargs.get("aspect_ratio", "16:9"),
                "pro": kwargs.get("pro", False),
                "generate_audio": kwargs.get("generate_audio", False),
                "shot_type": kwargs.get("shot_type", "customize"),
                "keep_audio": kwargs.get("keep_audio", False)
            })
            if kwargs.get("start_image_url"):
                payload["start_image_url"] = kwargs.get("start_image_url")
            if kwargs.get("end_image_url"):
                payload["end_image_url"] = kwargs.get("end_image_url")
        
        # ============================================================
        # Kling Video V3
        # ============================================================
        if model == "kling-video-v3":
            payload.update({
                "model": kwargs.get("model_type", "pro"),
                "aspect_ratio": kwargs.get("aspect_ratio", "16:9"),
                "generate_audio": kwargs.get("generate_audio", True),
                "negative_prompt": kwargs.get("negative_prompt", "blur, distort, and low quality"),
                "cfg_scale": kwargs.get("cfg_scale", 0.5),
                "shot_type": kwargs.get("shot_type", "customize")
            })
            if kwargs.get("start_image_url"):
                payload["start_image_url"] = kwargs.get("start_image_url")
            if kwargs.get("end_image_url"):
                payload["end_image_url"] = kwargs.get("end_image_url")
        
        # ============================================================
        # Veo 3.1
        # ============================================================
        if model == "veo-3.1":
            payload.update({
                "mode": kwargs.get("mode", "txt2video"),
                "resolution": kwargs.get("resolution", "720p"),
                "generate_audio": kwargs.get("generate_audio", True),
                "aspect_ratio": kwargs.get("aspect_ratio", "16:9"),
                "enhance_prompt": kwargs.get("enhance_prompt", False),
                "fast": kwargs.get("fast", False),
                "auto_fix": kwargs.get("auto_fix", True)
            })
            if kwargs.get("negative_prompt"):
                payload["negative_prompt"] = kwargs.get("negative_prompt")
            if kwargs.get("seed"):
                payload["seed"] = kwargs.get("seed")
            if kwargs.get("image_urls"):
                payload["image_urls"] = kwargs.get("image_urls")
        
        # ============================================================
        # Veo 3.1 Lite
        # ============================================================
        if model == "veo-3-1-lite":
            payload.update({
                "aspect_ratio": kwargs.get("aspect_ratio", "16:9"),
                "resolution": kwargs.get("resolution", "720p"),
                "generate_audio": kwargs.get("generate_audio", True),
                "auto_fix": kwargs.get("auto_fix", True)
            })
            if kwargs.get("negative_prompt"):
                payload["negative_prompt"] = kwargs.get("negative_prompt")
            if kwargs.get("seed"):
                payload["seed"] = kwargs.get("seed")
            if kwargs.get("image_url"):
                payload["image_url"] = kwargs.get("image_url")
            if kwargs.get("last_frame_url"):
                payload["last_frame_url"] = kwargs.get("last_frame_url")
        
        # ============================================================
        # Luma Ray2
        # ============================================================
        if model == "luma":
            payload["user_prompt"] = prompt
            del payload["prompt"]
            payload.update({
                "aspect_ratio": kwargs.get("aspect_ratio", "16:9"),
                "expand_prompt": kwargs.get("expand_prompt", True),
                "loop": kwargs.get("loop", False),
                "resolution": kwargs.get("resolution", "720p"),
                "model": kwargs.get("model_type", "ray-2-flash")
            })
            if kwargs.get("image_url"):
                payload["image_url"] = kwargs.get("image_url")
            if kwargs.get("image_end_url"):
                payload["image_end_url"] = kwargs.get("image_end_url")
        
        # ============================================================
        # Runway Gen-4
        # ============================================================
        if model == "runway-gen4":
            payload["promptText"] = prompt
            del payload["prompt"]
            payload.update({
                "model": kwargs.get("model_type", "gen4_turbo"),
                "ratio": kwargs.get("ratio", "1280:720")
            })
            if kwargs.get("firstFrame"):
                payload["firstFrame"] = kwargs.get("firstFrame")
            else:
                raise ValueError("Runway Gen-4 requires firstFrame (image)")

        timeout = getattr(settings, 'AI_TIMEOUT', 120)

        url = f"{self.base_url}/api/v1/networks/{model}"
        logger.info(f"📤 Video API запрос: {url}")
        logger.info(f"📤 Payload: {payload}")

        response = await self.client.post(
            url,
            headers=headers,
            json=payload,
            timeout=timeout
        )
        response.raise_for_status()
        return response.json()

    async def _wait_for_video(self, request_id: str, timeout: int = 600) -> Optional[Dict[str, Any]]:
        """Ожидание готовности видео с проверкой статуса."""
        start_time = asyncio.get_event_loop().time()
        check_interval = 5  # проверяем каждые 5 секунд
        
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            try:
                status = await self._check_status(request_id)
                logger.info(f"📊 Статус видео: {status.get('status')}, прогресс: {status.get('progress', 0)}%")
                
                if status.get("status") == "success":
                    return status
                elif status.get("status") == "failed":
                    logger.error(f"❌ Генерация видео провалилась: {status}")
                    return None
                elif status.get("status") in ["starting", "processing", "queued"]:
                    await asyncio.sleep(check_interval)
                    continue
                else:
                    logger.warning(f"⚠️ Неизвестный статус: {status}")
                    await asyncio.sleep(check_interval)
                    
            except Exception as e:
                logger.error(f"❌ Ошибка проверки статуса: {e}")
                await asyncio.sleep(check_interval)
        
        logger.error(f"⏰ Таймаут ожидания видео ({timeout} сек)")
        return None

    async def generate(self, prompt: str, **kwargs) -> AIResponse:
        model = kwargs.get("model", settings.FREE_VIDEO_MODEL)
        duration = kwargs.get("duration", 5)
        size = kwargs.get("size", "1280x720")

        try:
            start_time = asyncio.get_event_loop().time()
            
            kwargs_copy = kwargs.copy()
            kwargs_copy.pop("model", None)
            kwargs_copy.pop("duration", None)
            kwargs_copy.pop("size", None)
            
            result = await self._make_request(prompt=prompt, model=model, **kwargs_copy)
            elapsed = asyncio.get_event_loop().time() - start_time

            logger.info(f"✅ Video API ответ: {result}")

            if not result:
                return AIResponse(
                    content="",
                    provider="genapi_video",
                    model=model,
                    status=GenerationStatus.EMPTY_RESPONSE,
                    response_type=ResponseType.VIDEO
                )

            # ============================================================
            # АСИНХРОННАЯ ГЕНЕРАЦИЯ — ждём результат
            # ============================================================
            request_id = result.get("request_id")
            if request_id:
                logger.info(f"⏳ Видео генерируется, request_id: {request_id}")
                
                # Отправляем сообщение пользователю о начале генерации
                # (это будет обработано в handlers.py)
                
                # Ждём готовности видео
                final_result = await self._wait_for_video(request_id)
                
                if not final_result:
                    return AIResponse(
                        content="",
                        provider="genapi_video",
                        model=model,
                        status=GenerationStatus.ERROR,
                        response_type=ResponseType.VIDEO,
                        metadata={"error": "Таймаут ожидания видео или ошибка генерации"}
                    )
                
                # Извлекаем URL из результата
                video_url = None
                output = final_result.get("output")
                
                if isinstance(output, list) and len(output) > 0:
                    video_url = output[0]
                elif isinstance(output, str):
                    video_url = output
                elif isinstance(output, dict):
                    video_url = output.get("url") or output.get("video_url")
                
                if not video_url and final_result.get("result"):
                    video_url = final_result["result"]
                
                if not video_url:
                    return AIResponse(
                        content="",
                        provider="genapi_video",
                        model=model,
                        status=GenerationStatus.EMPTY_RESPONSE,
                        response_type=ResponseType.VIDEO,
                        metadata={"error": "URL видео не найден", "raw_response": str(final_result)[:500]}
                    )
                
                response_data = {
                    "type": "video",
                    "url": video_url,
                    "duration": duration,
                    "size": size,
                    "prompt": prompt,
                    "model": model
                }

                return AIResponse(
                    content=json.dumps(response_data, ensure_ascii=False),
                    provider="genapi_video",
                    model=model,
                    elapsed=elapsed,
                    status=GenerationStatus.SUCCESS,
                    response_type=ResponseType.VIDEO,
                    metadata=response_data
                )
            
            # ============================================================
            # СИНХРОННАЯ ГЕНЕРАЦИЯ — сразу есть URL
            # ============================================================
            video_url = None
            
            if result.get("data") and isinstance(result["data"], list) and len(result["data"]) > 0:
                video_url = result["data"][0].get("url")
                if not video_url and result["data"][0].get("b64_json"):
                    b64_data = result["data"][0]["b64_json"]
                    video_url = f"data:video/mp4;base64,{b64_data}"
            
            if not video_url and result.get("output"):
                if isinstance(result["output"], list) and len(result["output"]) > 0:
                    video_url = result["output"][0]
                elif isinstance(result["output"], str):
                    video_url = result["output"]
            
            if not video_url and result.get("url"):
                video_url = result["url"]

            if not video_url:
                return AIResponse(
                    content="",
                    provider="genapi_video",
                    model=model,
                    status=GenerationStatus.EMPTY_RESPONSE,
                    response_type=ResponseType.VIDEO,
                    metadata={"error": "URL видео не найден", "raw_response": str(result)[:500]}
                )

            response_data = {
                "type": "video",
                "url": video_url,
                "duration": duration,
                "size": size,
                "prompt": prompt,
                "model": model
            }

            return AIResponse(
                content=json.dumps(response_data, ensure_ascii=False),
                provider="genapi_video",
                model=model,
                elapsed=elapsed,
                status=GenerationStatus.SUCCESS,
                response_type=ResponseType.VIDEO,
                metadata=response_data
            )

        except Exception as e:
            logger.error(f"❌ Ошибка генерации видео: {e}")
            return AIResponse(
                content="",
                provider="genapi_video",
                model=model,
                status=GenerationStatus.ERROR,
                response_type=ResponseType.VIDEO,
                metadata={"error": str(e)}
            )


class AudioProvider(AIProvider):
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def generate(self, prompt: str = "", **kwargs) -> AIResponse:
        return AIResponse(
            content="",
            provider="audio",
            model="none",
            status=GenerationStatus.NOT_IMPLEMENTED,
            response_type=ResponseType.AUDIO,
            metadata={"error": "Audio генерация пока не реализована"}
        )


class AIService:
    def __init__(self):
        timeout = getattr(settings, 'AI_TIMEOUT', 600)  # Увеличиваем до 600 секунд
        self.client = httpx.AsyncClient(
            timeout=timeout,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=50)
        )
        self._providers = {
            "text": TextProvider(self.client),
            "image": ImageProvider(self.client),
            "video": VideoProvider(self.client),
            "audio": AudioProvider(self.client),
        }

    async def generate(
        self,
        provider_type: str = "text",
        response_type: ResponseType = ResponseType.TEXT,
        prompt: str = "",
        **kwargs
    ) -> AIResponse:
        provider = self._providers.get(provider_type)
        if not provider:
            raise ValueError(f"Unsupported provider: {provider_type}")
        return await provider.generate(prompt, **kwargs)

    async def close(self) -> None:
        await self.client.aclose()


ai_service = AIService()
