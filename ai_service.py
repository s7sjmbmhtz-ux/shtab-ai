import httpx
import asyncio
import json
import base64
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod

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
    def __init__(self):
        self.api_key = settings.GENAPI_API_KEY
        self.base_url = settings.GENAPI_BASE_URL

    async def _make_request(self, prompt: str, model: str, temperature: float) -> str:
        if not self.api_key or self.api_key in ["", "None", "sk-"]:
            logger.error("❌ API-ключ пустой! Проверьте GENAPI_API_KEY в .env")
            raise ValueError("API-ключ не настроен")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        payload = {
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature
        }
        payload = {k: v for k, v in payload.items() if v is not None}

        timeout = httpx.Timeout(
            connect=30,
            read=120,
            write=30,
            pool=30
        )

        base_url = self.base_url.rstrip('/')
        url = f"{base_url}/api/v1/networks/{model}"
        
        logger.info("=" * 60)
        logger.info("📤 TEXT API ЗАПРОС")
        logger.info(f"URL: {url}")
        logger.info(f"Headers: Authorization: Bearer {self.api_key[:10]}...")
        logger.info(f"Payload: {json.dumps(payload, ensure_ascii=False)}")
        logger.info("=" * 60)

        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                http2=False,
                follow_redirects=True
            ) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=payload
                )
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке запроса: {e}")
            raise

        logger.info(f"📥 Ответ: статус {response.status_code}")
        logger.info(f"📥 Тело: {response.text[:1000]}")
        
        if response.status_code >= 400:
            logger.error(f"❌ Ошибка API: {response.text[:500]}")
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
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP ошибка: {e.response.status_code}")
            logger.error(f"❌ Ответ API: {e.response.text[:500]}")
            return AIResponse(
                content="",
                provider="genapi",
                model=model,
                status=GenerationStatus.ERROR,
                metadata={"error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"},
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
    def __init__(self):
        self.api_key = settings.GENAPI_API_KEY
        self.base_url = settings.GENAPI_BASE_URL

    async def _make_request(self, prompt: str, size: str, model: str) -> Dict[str, Any]:
        if not self.api_key or self.api_key in ["", "None", "sk-"]:
            logger.error("❌ API-ключ пустой! Проверьте GENAPI_API_KEY в .env")
            raise ValueError("API-ключ не настроен")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        payload = {
            "prompt": prompt,
            "size": size,
            "n": 1
        }
        payload = {k: v for k, v in payload.items() if v is not None}

        timeout = httpx.Timeout(
            connect=30,
            read=120,
            write=30,
            pool=30
        )

        base_url = self.base_url.rstrip('/')
        url = f"{base_url}/api/v1/networks/{model}"
        
        logger.info("=" * 60)
        logger.info("📤 IMAGE API ЗАПРОС")
        logger.info(f"URL: {url}")
        logger.info(f"Headers: Authorization: Bearer {self.api_key[:10]}...")
        logger.info(f"Payload: {json.dumps(payload, ensure_ascii=False)}")
        logger.info("=" * 60)

        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                http2=False,
                follow_redirects=True
            ) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=payload
                )
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке запроса: {e}")
            raise

        logger.info(f"📥 Ответ: статус {response.status_code}")
        logger.info(f"📥 Тело: {response.text[:1000]}")
        
        if response.status_code >= 400:
            logger.error(f"❌ Ошибка API: {response.text[:500]}")
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

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP ошибка: {e.response.status_code}")
            logger.error(f"❌ Ответ API: {e.response.text[:500]}")
            return AIResponse(
                content="",
                provider="genapi",
                model=model,
                status=GenerationStatus.ERROR,
                response_type=ResponseType.IMAGE,
                metadata={"error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
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
    def __init__(self):
        self.api_key = settings.GENAPI_API_KEY
        self.base_url = settings.GENAPI_BASE_URL
        self.max_wait_time = 600

    def _clean_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = {}
        for k, v in payload.items():
            if v is None:
                continue
            if isinstance(v, dict):
                cleaned[k] = self._clean_payload(v)
            elif isinstance(v, list):
                cleaned[k] = [x for x in v if x is not None]
            else:
                cleaned[k] = v
        return cleaned

    async def _check_status(self, request_id: str) -> Dict[str, Any]:
        if not self.api_key or self.api_key in ["", "None", "sk-"]:
            logger.error("❌ API-ключ пустой!")
            raise ValueError("API-ключ не настроен")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        base_url = self.base_url.rstrip('/')
        url = f"{base_url}/api/v1/request/get/{request_id}"
        logger.info(f"🔍 Проверка статуса: {url}")
        
        timeout = httpx.Timeout(connect=30, read=30, write=30, pool=30)
        
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                http2=False,
                follow_redirects=True
            ) as client:
                response = await client.get(
                    url,
                    headers=headers
                )
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке статуса: {e}")
            raise
        
        logger.info(f"📥 Статус ответа: {response.status_code}")
        logger.info(f"📥 Тело: {response.text[:500]}")
        
        if response.status_code >= 400:
            logger.error(f"❌ Ошибка проверки статуса: {response.text[:500]}")
            response.raise_for_status()
        
        return response.json()

    async def _wait_for_video(self, request_id: str, timeout: int = 600) -> Optional[Dict[str, Any]]:
        start_time = asyncio.get_event_loop().time()
        check_interval = 5
        
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            try:
                status = await self._check_status(request_id)
                logger.info(f"📊 Статус видео: {status.get('status')}, прогресс: {status.get('progress', 0)}%")
                
                if status.get("status") == "success":
                    return status
                elif status.get("status") in ["failed", "error"]:
                    logger.error(f"❌ Генерация видео провалилась: {status}")
                    return status
                elif status.get("status") in ["starting", "processing", "queued", "pending"]:
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

    async def _make_request(self, prompt: str, model: str, **kwargs) -> Dict[str, Any]:
        if not self.api_key or self.api_key in ["", "None", "sk-"]:
            logger.error("❌ API-ключ пустой! Проверьте GENAPI_API_KEY в .env")
            raise ValueError("API-ключ не настроен")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        payload = {
            "callback_url": None,
            "translate_input": True,
            "prompt": prompt
        }
        
        # ============================================================
        # LTX 2.3
        # ============================================================
        if model == "ltx-2-3":
            payload.update({
                "duration": kwargs.get("duration", 5),
                "mode": kwargs.get("mode", "pro"),
                "resolution": kwargs.get("resolution", "1080p"),
                "aspect_ratio": kwargs.get("aspect_ratio", "16:9"),
                "fps": 25,
                "generate_audio": True
            })
        
        # ============================================================
        # CogVideoX 5B
        # ============================================================
        elif model == "cog-video-x-5b":
            payload.update({
                "duration": kwargs.get("duration", 5),
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
        elif model == "kling-video-o3":
            payload.update({
                "duration": kwargs.get("duration", 5),
                "model": kwargs.get("model_type", "text-to-video"),
                "aspect_ratio": kwargs.get("aspect_ratio", "16:9"),
                "pro": kwargs.get("pro", False),
                "generate_audio": kwargs.get("generate_audio", False),
                "shot_type": kwargs.get("shot_type", "customize"),
                "keep_audio": kwargs.get("keep_audio", False)
            })
            if "start_image_url" in kwargs:
                payload["start_image_url"] = kwargs["start_image_url"]
            if "end_image_url" in kwargs:
                payload["end_image_url"] = kwargs["end_image_url"]
        
        # ============================================================
        # Kling Video V3
        # ============================================================
        elif model == "kling-video-v3":
            payload.update({
                "duration": kwargs.get("duration", 5),
                "model": kwargs.get("model_type", "pro"),
                "aspect_ratio": kwargs.get("aspect_ratio", "16:9"),
                "generate_audio": kwargs.get("generate_audio", True),
                "negative_prompt": kwargs.get("negative_prompt", "blur, distort, and low quality"),
                "cfg_scale": kwargs.get("cfg_scale", 0.5),
                "shot_type": kwargs.get("shot_type", "customize")
            })
            if "start_image_url" in kwargs:
                payload["start_image_url"] = kwargs["start_image_url"]
            if "end_image_url" in kwargs:
                payload["end_image_url"] = kwargs["end_image_url"]
        
        # ============================================================
        # Veo 3.1
        # ============================================================
        elif model == "veo-3.1":
            if "image_urls" in kwargs and kwargs["image_urls"]:
                mode = "img2video"
            else:
                mode = "txt2video"
            
            payload.update({
                "duration": f"{kwargs.get('duration', 5)}s",
                "mode": mode,
                "resolution": kwargs.get("resolution", "720p"),
                "generate_audio": kwargs.get("generate_audio", True),
                "aspect_ratio": kwargs.get("aspect_ratio", "16:9"),
                "enhance_prompt": kwargs.get("enhance_prompt", False),
                "fast": kwargs.get("fast", False),
                "auto_fix": kwargs.get("auto_fix", True)
            })
            if "negative_prompt" in kwargs:
                payload["negative_prompt"] = kwargs["negative_prompt"]
            if "seed" in kwargs:
                payload["seed"] = kwargs["seed"]
            if "image_urls" in kwargs:
                payload["image_urls"] = kwargs["image_urls"]
        
        # ============================================================
        # Veo 3.1 Lite
        # ============================================================
        elif model == "veo-3-1-lite":
            payload.update({
                "duration": f"{kwargs.get('duration', 5)}s",
                "aspect_ratio": kwargs.get("aspect_ratio", "16:9"),
                "resolution": kwargs.get("resolution", "720p"),
                "generate_audio": kwargs.get("generate_audio", True),
                "auto_fix": kwargs.get("auto_fix", True)
            })
            if "negative_prompt" in kwargs:
                payload["negative_prompt"] = kwargs["negative_prompt"]
            if "seed" in kwargs:
                payload["seed"] = kwargs["seed"]
            if "image_url" in kwargs:
                payload["image_url"] = kwargs["image_url"]
            if "last_frame_url" in kwargs:
                payload["last_frame_url"] = kwargs["last_frame_url"]
        
        # ============================================================
        # Luma Ray2
        # ============================================================
        elif model == "luma":
            payload["user_prompt"] = prompt
            del payload["prompt"]
            payload.update({
                "duration": f"{kwargs.get('duration', 5)}s",
                "aspect_ratio": kwargs.get("aspect_ratio", "16:9"),
                "expand_prompt": kwargs.get("expand_prompt", True),
                "loop": kwargs.get("loop", False),
                "resolution": kwargs.get("resolution", "720p"),
                "model": kwargs.get("model_type", "ray-2-flash")
            })
            if "image_url" in kwargs:
                payload["image_url"] = kwargs["image_url"]
            if "image_end_url" in kwargs:
                payload["image_end_url"] = kwargs["image_end_url"]
        
        # ============================================================
        # Runway Gen-4
        # ============================================================
        elif model == "runway-gen4":
            payload["promptText"] = prompt
            del payload["prompt"]
            payload.update({
                "duration": kwargs.get("duration", 5),
                "model": kwargs.get("model_type", "gen4_turbo"),
                "ratio": kwargs.get("ratio", "1280:720")
            })
            if "firstFrame" in kwargs:
                payload["firstFrame"] = kwargs["firstFrame"]
        
        # ============================================================
        # НЕИЗВЕСТНАЯ МОДЕЛЬ
        # ============================================================
        else:
            payload["duration"] = kwargs.get("duration", 5)
            logger.warning(f"⚠️ Неизвестная модель: {model}, используется базовый payload")

        payload = self._clean_payload(payload)

        timeout = httpx.Timeout(
            connect=30,
            read=600,
            write=30,
            pool=30
        )

        base_url = self.base_url.rstrip('/')
        url = f"{base_url}/api/v1/networks/{model}"
        
        logger.info("=" * 60)
        logger.info("📤 VIDEO API ЗАПРОС")
        logger.info(f"URL: {url}")
        logger.info(f"Headers: Authorization: Bearer {self.api_key[:10]}...")
        logger.info(f"Payload: {json.dumps(payload, ensure_ascii=False)}")
        logger.info("=" * 60)

        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                http2=False,
                follow_redirects=True
            ) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=payload
                )
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке запроса: {e}")
            raise

        logger.info(f"📥 Ответ: статус {response.status_code}")
        logger.info(f"📥 Тело: {response.text[:1000]}")
        
        if response.status_code >= 400:
            logger.error(f"❌ Ошибка API: {response.text[:500]}")
            response.raise_for_status()
        
        return response.json()

    async def generate(self, prompt: str, **kwargs) -> AIResponse:
        model = kwargs.get("model", settings.FREE_VIDEO_MODEL)
        duration = kwargs.get("duration", 5)
        size = kwargs.get("size", "1280x720")

        try:
            start_time = asyncio.get_event_loop().time()
            
            kwargs_copy = kwargs.copy()
            kwargs_copy.pop("model", None)
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

            request_id = result.get("request_id")
            if request_id:
                logger.info(f"⏳ Видео генерируется, request_id: {request_id}")
                
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
                
                if final_result.get("status") in ["failed", "error"]:
                    return AIResponse(
                        content="",
                        provider="genapi_video",
                        model=model,
                        status=GenerationStatus.ERROR,
                        response_type=ResponseType.VIDEO,
                        metadata={"error": f"Ошибка генерации: {final_result.get('error', 'Неизвестная ошибка')}"}
                    )
                
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

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP ошибка Video API: {e.response.status_code}")
            logger.error(f"❌ Ответ API: {e.response.text[:500]}")
            return AIResponse(
                content="",
                provider="genapi_video",
                model=model,
                status=GenerationStatus.ERROR,
                response_type=ResponseType.VIDEO,
                metadata={"error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
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
    def __init__(self):
        pass

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
        self._providers = {
            "text": TextProvider(),
            "image": ImageProvider(),
            "video": VideoProvider(),
            "audio": AudioProvider(),
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
        pass


ai_service = AIService()
