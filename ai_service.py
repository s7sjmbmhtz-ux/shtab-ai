import httpx
import asyncio
import json
import base64
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from abc import ABC, abstractmethod
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

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
# TEXT PROVIDER
# ============================================================

class TextProvider(AIProvider):
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.api_key = settings.provod_api_key
        self.base_url = settings.provod_base_url
        self.default_model = settings.free_text_model

    @retry(
        stop=stop_after_attempt(3),
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

        response = await self.client.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        data = response.json()
        
        # Provod.ai использует формат OpenAI
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0].get("message", {}).get("content", "")
        else:
            return data.get("result", data.get("response", str(data)))

    async def generate(self, prompt: str, **kwargs) -> AIResponse:
        model = kwargs.get("model", self.default_model)
        temperature = kwargs.get("temperature", 0.7)

        try:
            start_time = asyncio.get_event_loop().time()
            content = await self._make_request(prompt, model, temperature)
            elapsed = asyncio.get_event_loop().time() - start_time

            if not content:
                return AIResponse(
                    content="",
                    provider="deepseek",
                    model=model,
                    status=GenerationStatus.EMPTY_RESPONSE,
                    response_type=ResponseType.TEXT
                )

            return AIResponse(
                content=content,
                provider="deepseek",
                model=model,
                elapsed=elapsed,
                status=GenerationStatus.SUCCESS,
                response_type=ResponseType.TEXT
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP ошибка Provod.ai: {e.response.status_code} - {e.response.text}")
            return AIResponse(
                content="",
                provider="deepseek",
                model=model,
                status=GenerationStatus.ERROR,
                metadata={"error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"},
                response_type=ResponseType.TEXT
            )
        except Exception as e:
            logger.error(f"Ошибка генерации текста: {e}")
            return AIResponse(
                content="",
                provider="deepseek",
                model=model,
                status=GenerationStatus.ERROR,
                metadata={"error": str(e)},
                response_type=ResponseType.TEXT
            )


# ============================================================
# IMAGE PROVIDER
# ============================================================

class ImageProvider(AIProvider):
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.api_key = settings.provod_api_key
        self.base_url = settings.provod_base_url

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

        response = await self.client.post(
            f"{self.base_url}/images/generations",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()

    async def generate(self, prompt: str, **kwargs) -> AIResponse:
        size = kwargs.get("size", "1024x1024")
        model = kwargs.get("model", settings.free_image_model)

        try:
            start_time = asyncio.get_event_loop().time()
            result = await self._make_request(prompt, size, model)
            elapsed = asyncio.get_event_loop().time() - start_time

            logger.info(f"Image API ответ: {result}")

            if not result:
                return AIResponse(
                    content="",
                    provider="image_generator",
                    model=model,
                    status=GenerationStatus.EMPTY_RESPONSE,
                    response_type=ResponseType.IMAGE
                )

            # Пробуем разные форматы ответа
            image_url = None
            
            if result.get("data") and isinstance(result["data"], list):
                # Формат 1: url (OpenAI)
                image_url = result["data"][0].get("url")
                
                # Формат 2: b64_json (Provod.ai)
                if not image_url and result["data"][0].get("b64_json"):
                    b64_data = result["data"][0]["b64_json"]
                    image_url = f"data:image/png;base64,{b64_data}"
            
            # Формат 3: url (прямой)
            if not image_url and result.get("url"):
                image_url = result["url"]
            
            # Формат 4: images[0].url
            if not image_url and result.get("images"):
                image_url = result["images"][0].get("url")
            
            # Формат 5: output (Replicate)
            if not image_url and result.get("output"):
                if isinstance(result["output"], list) and len(result["output"]) > 0:
                    image_url = result["output"][0]
                elif isinstance(result["output"], str):
                    image_url = result["output"]

            if not image_url:
                logger.error(f"Не удалось найти URL в ответе: {result}")
                return AIResponse(
                    content="",
                    provider="image_generator",
                    model=model,
                    status=GenerationStatus.EMPTY_RESPONSE,
                    response_type=ResponseType.IMAGE,
                    metadata={"error": "URL изображения не найден", "raw_response": str(result)[:500]}
                )

            response_data = {
                "type": "image",
                "url": image_url,
                "size": size,
                "prompt": prompt
            }

            return AIResponse(
                content=json.dumps(response_data, ensure_ascii=False),
                provider="image_generator",
                model=model,
                elapsed=elapsed,
                status=GenerationStatus.SUCCESS,
                response_type=ResponseType.IMAGE,
                metadata=response_data
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP ошибка Image API: {e.response.status_code} - {e.response.text}")
            return AIResponse(
                content="",
                provider="image_generator",
                model=model,
                status=GenerationStatus.ERROR,
                response_type=ResponseType.IMAGE,
                metadata={"error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
            )
        except Exception as e:
            logger.error(f"Ошибка генерации изображения: {e}")
            return AIResponse(
                content="",
                provider="image_generator",
                model=model,
                status=GenerationStatus.ERROR,
                response_type=ResponseType.IMAGE,
                metadata={"error": str(e)}
            )


# ============================================================
# AUDIO PROVIDER
# ============================================================

class AudioProvider(AIProvider):
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.stt_provider = settings.stt_provider or "speech_to_text"
        self.default_model = settings.default_stt_model

    async def _make_request(self, audio: AudioFile, language: str, model: str) -> Dict[str, Any]:
        # TODO: Реализовать реальный STT API
        raise NotImplementedError("Распознавание голоса пока не реализовано")

    def _build_response(self, result: Dict[str, Any], audio: AudioFile, language: str, model: Optional[str], elapsed: float) -> AIResponse:
        model_name = model or self.default_model

        return AIResponse(
            content=result.get("text", ""),
            provider=self.stt_provider,
            model=result.get("model", model_name),
            elapsed=elapsed,
            status=GenerationStatus.SUCCESS,
            response_type=ResponseType.TEXT,
            metadata={
                "language": result.get("language", language),
                "duration": audio.duration,
                "filename": audio.filename,
                "extension": audio.extension,
                "size_mb": round(audio.size_mb, 2),
                "provider": self.stt_provider
            }
        )

    async def generate(self, prompt: str = "", **kwargs) -> AIResponse:
        # Заглушка
        return AIResponse(
            content="",
            provider=self.stt_provider,
            model=self.default_model,
            status=GenerationStatus.NOT_IMPLEMENTED,
            response_type=ResponseType.TEXT,
            metadata={"error": "Voice генерация пока не реализована"}
        )


# ============================================================
# AISERVICE (ФАСАД)
# ============================================================

class AIService:
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=settings.ai_timeout,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=50)
        )

        self._providers = {
            "text": TextProvider(self.client),
            "image": ImageProvider(self.client),
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
