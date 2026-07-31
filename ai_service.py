import httpx
import asyncio
import json
import base64
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, RetryError

from settings import settings
from models import (
    GenerationStatus, AIResponse, ResponseType,
    ImageResponse, AudioFile
)
from utils import logger


# ============================================================
# AI PROVIDER (ABSTRACT)
# ============================================================

class AIProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> AIResponse:
        pass


# ============================================================
# TEXT PROVIDER (GenAPI)
# ============================================================

class TextProvider(AIProvider):
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.api_key = settings.GENAPI_API_KEY
        self.base_url = settings.GENAPI_BASE_URL

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError, asyncio.TimeoutError))
    )
    async def _make_request(self, prompt: str, model: str, temperature: float) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature
        }

        timeout = getattr(settings, 'AI_TIMEOUT', 120)

        response = await self.client.post(
            f"{self.base_url}/chat/completions",
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
            logger.error(f"Ошибка генерации текста: {e}")
            return AIResponse(
                content="",
                provider="genapi",
                model=model,
                status=GenerationStatus.ERROR,
                metadata={"error": str(e)},
                response_type=ResponseType.TEXT
            )


# ============================================================
# IMAGE PROVIDER (GenAPI)
# ============================================================

class ImageProvider(AIProvider):
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.api_key = settings.GENAPI_API_KEY
        self.base_url = settings.GENAPI_BASE_URL

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError, asyncio.TimeoutError))
    )
    async def _make_request(self, prompt: str, size: str, model: str) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "n": 1
        }

        timeout = getattr(settings, 'AI_TIMEOUT', 120)

        response = await self.client.post(
            f"{self.base_url}/images/generations",
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
            logger.error(f"Ошибка генерации изображения: {e}")
            return AIResponse(
                content="",
                provider="genapi",
                model=model,
                status=GenerationStatus.ERROR,
                response_type=ResponseType.IMAGE,
                metadata={"error": str(e)}
            )


# ============================================================
# VIDEO PROVIDER (GenAPI) — УНИВЕРСАЛЬНЫЙ
# ============================================================

class VideoProvider(AIProvider):
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.api_key = settings.GENAPI_API_KEY
        self.base_url = settings.GENAPI_BASE_URL

    async def _make_request(self, prompt: str, model: str, **kwargs) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # ============================================================
        # БАЗОВЫЙ PAYLOAD ДЛЯ ВСЕХ МОДЕЛЕЙ
        # ============================================================
        payload = {
            "callback_url": None,
            "prompt": prompt,
            "duration": kwargs.get("duration", 5)
        }
        
        # ============================================================
        # ДОПОЛНИТЕЛЬНЫЕ ПАРАМЕТРЫ ДЛЯ LTX 2.3
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
        # ДОПОЛНИТЕЛЬНЫЕ ПАРАМЕТРЫ
        # ============================================================
        if kwargs.get("image"):
            payload["image_url"] = kwargs.get("image")
        
        if kwargs.get("end_image"):
            payload["end_image_url"] = kwargs.get("end_image")
        
        if kwargs.get("negative_prompt"):
            payload["negative_prompt"] = kwargs.get("negative_prompt")

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
            # ОБРАБОТКА РАЗНЫХ ФОРМАТОВ ОТВЕТА
            # ============================================================
            video_url = None
            
            # Если это асинхронный запрос — возвращаем request_id
            if result.get("request_id") and result.get("status") == "starting":
                logger.info(f"⏳ Видео генерируется, request_id: {result.get('request_id')}")
                # TODO: Реализовать Long-Pooling или callback
                return AIResponse(
                    content=json.dumps({"status": "processing", "request_id": result.get("request_id")}),
                    provider="genapi_video",
                    model=model,
                    status=GenerationStatus.SUCCESS,
                    response_type=ResponseType.VIDEO,
                    metadata={"request_id": result.get("request_id")}
                )
            
            # Стандартные форматы ответа
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
            
            if not video_url and result.get("videos"):
                if isinstance(result["videos"], list) and len(result["videos"]) > 0:
                    video_url = result["videos"][0].get("url")

            if not video_url:
                logger.error(f"❌ Не удалось найти URL видео в ответе: {result}")
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
            logger.error(f"❌ Response: {e.response.text[:500]}")
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


# ============================================================
# AUDIO PROVIDER (заглушка)
# ============================================================

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


# ============================================================
# AISERVICE (ФАСАД)
# ============================================================

class AIService:
    def __init__(self):
        timeout = getattr(settings, 'AI_TIMEOUT', 120)
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
