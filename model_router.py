from models import ResponseType, Tariff
from settings import settings

# Маппинг тарифов на модели GenAPI
MODEL_MAP = {
    Tariff.FREE: {
        ResponseType.TEXT: "deepseek/deepseek-v4-flash",
        ResponseType.IMAGE: "flux-schnell",
        ResponseType.VIDEO: "ltx-video",
    },
    Tariff.LITE: {
        ResponseType.TEXT: "deepseek/deepseek-v4-pro",
        ResponseType.IMAGE: "flux-dev",
        ResponseType.VIDEO: "veo-3.1-lite",
    },
    Tariff.PRO: {
        ResponseType.TEXT: "openai/gpt-5.4-mini",
        ResponseType.IMAGE: "flux-pro",
        ResponseType.VIDEO: "veo-3.1",
    },
    Tariff.BUSINESS: {
        ResponseType.TEXT: "openai/gpt-5.5",
        ResponseType.IMAGE: "flux-pro",
        ResponseType.VIDEO: "veo-3.1",
    },
}


def get_model_for_tariff(tariff: Tariff, response_type: ResponseType) -> str:
    """Возвращает модель для заданного тарифа и типа ответа."""
    tariff_config = MODEL_MAP.get(tariff, MODEL_MAP[Tariff.FREE])
    return tariff_config.get(response_type, tariff_config.get(ResponseType.TEXT, "deepseek/deepseek-v4-flash"))
