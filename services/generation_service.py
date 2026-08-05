"""Единая точка запуска текста, изображений и видео с биллингом."""
from __future__ import annotations

from typing import Any

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
    "seededit": ("file", "image"),
    "cartoonify": ("file", "image_url"),
    "flux-dev": ("file", "image"),
    "flux-pro": ("file", "image"),
    "flux-schnell": ("file", "image"),
    "marketplace-main": ("file", "image"),
    "marketplace-lifestyle": ("file", "image"),
    "marketplace-infographic": ("file", "image"),
    "marketplace-bundle-item": ("file", "image"),
}

VIDEO_INPUT_FIELDS = {
    "ltx-2-3": "image_url",
    "kling-o3": "start_image_url",
    "kling-v3": "start_image_url",
    "veo-3-1-lite": "image_url",
    "veo-3-1": "image_urls",
    "luma-ray2": "image_url",
    "runway-gen4": "firstFrame",
}

VIDEO_END_FIELDS = {
    "ltx-2-3": "end_image_url",
    "kling-o3": "end_image_url",
    "kling-v3": "end_image_url",
    "veo-3-1-lite": "last_frame_url",
    "luma-ray2": "image_end_url",
}


class GenerationService:
    def __init__(self, client: GenAPIClient = genapi_client):
        self.client = client

    @staticmethod
    def requires_public_url(model_key: str) -> bool:
        config = IMAGE_INPUT_CONFIG.get(model_key)
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
            return await self.client.post(
                settings.GENAPI_PROXY_URL,
                model.endpoint,
                payload,
            )
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
        )
        try:
            result = await self.client.post(
                settings.GENAPI_BASE_URL,
                model.endpoint,
                payload,
                files=files or None,
            )
            return charge, result
        except Exception:
            await billing_service.refund(charge, "Ошибка запуска генерации")
            raise

    async def retry_media_task(
        self,
        model_key: str,
        prompt: str,
        *,
        input_image: LocalMedia | None = None,
        end_image: LocalMedia | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Повторяет запрос без повторного списания токенов."""
        model = get_model(model_key)
        self._validate_media(model_key, input_image, end_image)
        payload, files = await self._media_payload(
            model_key,
            prompt,
            input_image,
            end_image,
        )
        payload.update(overrides or {})
        return await self.client.post(
            settings.GENAPI_BASE_URL,
            model.endpoint,
            payload,
            files=files or None,
        )

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
                    payload[field] = await public_media_service.register(image)
                elif transport == "url_array":
                    payload[field] = [await public_media_service.register(image)]
                else:
                    raise ValueError(
                        f"Неизвестный способ передачи изображения: {transport}"
                    )

                if model.endpoint == "/api/v1/networks/flux":
                    payload.setdefault("strength", 0.8)
            else:
                field = VIDEO_INPUT_FIELDS[model_key]
                # Текущие video-endpoint принимают url_or_file напрямую.
                files[field] = image
                if model_key == "kling-o3":
                    payload["model"] = "image-to-video"

        if end_image:
            files[VIDEO_END_FIELDS[model_key]] = end_image

        return payload, files


generation_service = GenerationService()
