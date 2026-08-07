"""Единая точка запуска текста, изображений и видео с биллингом."""
from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from database import db_manager
from model_catalog import GenerationKind, get_model
from services.billing_service import Charge, billing_service
from services.genapi_client import GenAPIClient, genapi_client
from services.media_storage import LocalMedia
from services.public_media_service import public_media_service
from settings import settings


# transport: file — multipart; url/url_array — JSON со временной публичной ссылкой.
IMAGE_INPUT_CONFIG: dict[str, tuple[str, str]] = {
    "gpt-image-2": ("url_array", "image_urls"),
    "nano-banana-lite": ("url_array", "image_urls"),
    "nano-banana-2": ("url_array", "image_urls"),
    "flux-2-pro": ("url_array", "image_urls"),
    "qwen-image-2": ("url_array", "image_urls"),
    "flux-kontext": ("url_array", "images"),
    "cartoonify": ("file", "image_url"),
    "flux-dev": ("file", "image"),
    "flux-pro": ("file", "image"),
    "flux-schnell": ("file", "image"),
    "marketplace-main": ("file", "image"),
    "marketplace-lifestyle": ("file", "image"),
    "marketplace-infographic": ("file", "image"),
    "marketplace-bundle-item": ("file", "image"),
}

# Для видео используем JSON + публичные HTTPS-ссылки. Это сохраняет
# правильные типы bool/list и не превращает generate_audio в строку multipart.
VIDEO_INPUT_CONFIG: dict[str, tuple[str, str]] = {
    "ltx-2-3": ("url", "image_url"),
    "kling-o3": ("url", "start_image_url"),
    "kling-v3": ("url", "start_image_url"),
    "veo-3-1-lite": ("url", "image_url"),
    "veo-3-1": ("url_array", "image_urls"),
    "luma-ray2": ("url", "image_url"),
    "runway-gen4": ("url", "firstFrame"),
}

VIDEO_END_CONFIG: dict[str, tuple[str, str]] = {
    "ltx-2-3": ("url", "end_image_url"),
    "kling-o3": ("url", "end_image_url"),
    "kling-v3": ("url", "end_image_url"),
    "veo-3-1-lite": ("url", "last_frame_url"),
    "luma-ray2": ("url", "image_end_url"),
}


class GenerationService:
    def __init__(self, client: GenAPIClient = genapi_client):
        self.client = client

    @staticmethod
    def requires_public_url(model_key: str) -> bool:
        config = IMAGE_INPUT_CONFIG.get(model_key) or VIDEO_INPUT_CONFIG.get(model_key)
        return bool(config and config[0] in {"url", "url_array"})

    async def generate_text(
        self,
        user_id: int,
        model_key: str,
        messages: list[dict[str, str]],
    ) -> dict[str, Any]:
        model = get_model(model_key)
        if model.kind != GenerationKind.TEXT:
            raise ValueError("Выбрана не текстовая модель")
        charge = await billing_service.reserve(user_id, model_key)
        try:
            payload = {
                **model.defaults,
                "model": model.api_model,
                "messages": messages,
            }
            result = await self.client.post(
                settings.GENAPI_PROXY_URL,
                model.endpoint,
                payload,
            )
            await billing_service.complete(charge, result=result)
            prompt = next(
                (
                    str(item.get("content") or "")
                    for item in reversed(messages)
                    if item.get("role") == "user"
                ),
                "",
            )
            with contextlib.suppress(Exception):
                await db_manager.create_generation_history(
                    user_id=user_id,
                    economic_id=charge.ledger_id,
                    model_key=model_key,
                    kind=model.kind.value,
                    prompt=prompt,
                    generation_settings={"messages_count": len(messages)},
                    response_preview=self._text_preview(result),
                    status="completed",
                )
            return result
        except asyncio.CancelledError:
            await billing_service.refund(
                charge,
                "Текстовая генерация прервана",
                count_failure=False,
            )
            raise
        except Exception:
            await billing_service.refund(charge, "Ошибка текстовой генерации")
            raise

    async def create_media_task(
        self,
        user_id: int,
        model_key: str,
        prompt: str,
        *,
        input_image: LocalMedia | None = None,
        end_image: LocalMedia | None = None,
        overrides: dict[str, Any] | None = None,
        token_cost: int | None = None,
        provider_cost_rub: float | None = None,
    ) -> tuple[Charge, dict[str, Any]]:
        model = get_model(model_key)
        self._validate_media(model_key, input_image, end_image)

        # Подготавливаем ссылку до списания: отсутствие домена не должно
        # создавать даже временную транзакцию.
        payload, files = await self._media_payload(
            model_key,
            prompt,
            input_image,
            end_image,
        )
        payload.update(overrides or {})

        charge = await billing_service.reserve(
            user_id,
            model_key,
            amount=token_cost,
            provider_cost_rub=provider_cost_rub,
        )
        try:
            result = await self.client.post(
                settings.GENAPI_BASE_URL,
                model.endpoint,
                payload,
                files=files or None,
            )
            return charge, result
        except asyncio.CancelledError:
            await billing_service.refund(
                charge,
                "Запуск генерации прерван",
                count_failure=False,
            )
            raise
        except Exception:
            await billing_service.refund(charge, "Ошибка запуска генерации")
            raise

    @staticmethod
    def _text_preview(result: dict[str, Any]) -> str | None:
        choices = result.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"][:3000]
        output = result.get("output")
        if isinstance(output, str):
            return output[:3000]
        if isinstance(output, dict):
            for key in ("text", "content", "response"):
                if isinstance(output.get(key), str):
                    return output[key][:3000]
        return None

    @staticmethod
    def _validate_media(
        model_key: str,
        input_image: LocalMedia | None,
        end_image: LocalMedia | None,
    ) -> None:
        model = get_model(model_key)
        if model.kind == GenerationKind.TEXT:
            raise ValueError("Для текста используйте generate_text")
        if model.requires_input_image and not input_image:
            raise ValueError(f"{model.title} требует входное изображение")
        if input_image and not model.supports_input_image:
            raise ValueError(f"{model.title} не поддерживает входное изображение")
        if end_image and not model.supports_end_image:
            raise ValueError(f"{model.title} не поддерживает конечное изображение")

    async def _media_payload(
        self,
        model_key: str,
        prompt: str,
        image: LocalMedia | None,
        end_image: LocalMedia | None,
    ) -> tuple[dict[str, Any], dict[str, LocalMedia]]:
        model = get_model(model_key)
        payload: dict[str, Any] = {**model.defaults}
        files: dict[str, LocalMedia] = {}

        if model.api_model:
            payload["model"] = model.api_model

        prompt_fields = {
            "runway-gen4": "promptText",
            "luma-ray2": "user_prompt",
        }
        if model_key != "cartoonify":
            payload[prompt_fields.get(model_key, "prompt")] = prompt

        if image:
            if model.kind == GenerationKind.IMAGE:
                transport, field = IMAGE_INPUT_CONFIG.get(
                    model_key,
                    ("file", "image"),
                )
                if transport == "file":
                    files[field] = image
                elif transport == "url":
                    payload[field] = await public_media_service.register_verified(image)
                elif transport == "url_array":
                    payload[field] = [await public_media_service.register_verified(image)]
                else:
                    raise ValueError(
                        f"Неизвестный способ передачи изображения: {transport}"
                    )

                if model.endpoint == "/api/v1/networks/flux":
                    payload.setdefault("strength", 0.8)
            else:
                transport, field = VIDEO_INPUT_CONFIG[model_key]
                image_url = await public_media_service.register_verified(image)
                if transport == "url":
                    payload[field] = image_url
                elif transport == "url_array":
                    payload[field] = [image_url]
                else:
                    raise ValueError(
                        f"Неизвестный способ передачи видео-изображения: {transport}"
                    )

                if model_key == "kling-o3":
                    payload["model"] = "image-to-video"
                elif model_key == "veo-3-1":
                    payload["mode"] = "img2video"

        # Veo 3.1 требует явного режима и без входного изображения.
        if model_key == "veo-3-1" and not image:
            payload["mode"] = "txt2video"
            payload.pop("image_urls", None)

        if end_image:
            transport, field = VIDEO_END_CONFIG[model_key]
            end_url = await public_media_service.register_verified(end_image)
            if transport == "url":
                payload[field] = end_url
            elif transport == "url_array":
                payload[field] = [end_url]
            else:
                raise ValueError(
                    f"Неизвестный способ передачи конечного кадра: {transport}"
                )

        return payload, files


generation_service = GenerationService()
