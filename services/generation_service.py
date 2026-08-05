"""Единая точка запуска текста, изображений и видео с биллингом."""
from __future__ import annotations

from typing import Any

from model_catalog import GenerationKind, get_model
from services.billing_service import Charge, billing_service
from services.genapi_client import GenAPIClient, genapi_client
from services.media_storage import LocalMedia
from settings import settings


class GenerationService:
    def __init__(self, client: GenAPIClient = genapi_client):
        self.client = client

    async def generate_text(self, user_id: int, model_key: str, messages: list[dict[str, str]]) -> dict[str, Any]:
        model = get_model(model_key)
        if model.kind != GenerationKind.TEXT:
            raise ValueError("Выбрана не текстовая модель")
        charge = await billing_service.reserve(user_id, model_key)
        try:
            payload = {**model.defaults, "model": model.api_model, "messages": messages}
            return await self.client.post(settings.GENAPI_PROXY_URL, model.endpoint, payload)
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
        if model.kind == GenerationKind.TEXT:
            raise ValueError("Для текста используйте generate_text")
        if model.requires_input_image and not input_image:
            raise ValueError(f"{model.title} требует входное изображение")
        if input_image and not model.supports_input_image:
            raise ValueError(f"{model.title} не поддерживает входное изображение")
        if end_image and not model.supports_end_image:
            raise ValueError(f"{model.title} не поддерживает конечное изображение")

        charge = await billing_service.reserve(user_id, model_key, amount=token_cost)
        try:
            payload, files = self._media_payload(model_key, prompt, input_image, end_image)
            payload.update(overrides or {})
            result = await self.client.post(settings.GENAPI_BASE_URL, model.endpoint, payload, files=files or None)
            return charge, result
        except Exception:
            await billing_service.refund(charge, "Ошибка запуска генерации")
            raise

    @staticmethod
    def _media_payload(
        model_key: str,
        prompt: str,
        image: LocalMedia | None,
        end_image: LocalMedia | None,
    ) -> tuple[
        dict[str, Any],
        dict[str, LocalMedia | list[LocalMedia]],
    ]:
        model = get_model(model_key)
        payload: dict[str, Any] = {**model.defaults}
        files: dict[str, LocalMedia | list[LocalMedia]] = {}
        if model.api_model:
            payload["model"] = model.api_model

        prompt_fields = {"runway-gen4": "promptText", "luma-ray2": "user_prompt"}
        payload[prompt_fields.get(model_key, "prompt")] = prompt

        image_fields = {
            "flux-schnell": "image", "flux-dev": "image", "flux-pro": "image",
            "nano-banana-lite": "image_urls", "nano-banana-2": "image_urls",
            "ltx-2-3": "image_url", "kling-o3": "start_image_url",
            "kling-v3": "start_image_url", "veo-3-1-lite": "image_url",
            "veo-3-1": "image_urls", "luma-ray2": "image_url",
            "runway-gen4": "firstFrame",
        }
        end_fields = {
            "ltx-2-3": "end_image_url", "kling-o3": "end_image_url",
            "kling-v3": "end_image_url", "veo-3-1-lite": "last_frame_url",
            "luma-ray2": "image_end_url",
        }
        if image:
            if model.endpoint == "/api/v1/networks/flux":
                field = "image"
                payload.setdefault("strength", 0.8)
                files[field] = image
            elif model_key in {"nano-banana-lite", "nano-banana-2"}:
                # GenAPI требует image_urls как массив файлов.
                files["image_urls[]"] = [image]
            else:
                field = image_fields[model_key]
                files[field] = image

            if model_key == "kling-o3":
                payload["model"] = "image-to-video"
        if end_image:
            files[end_fields[model_key]] = end_image
        return payload, files


generation_service = GenerationService()
