"""
Маршрутизация моделей в зависимости от тарифа и типа запроса.
"""

from settings import settings
from models import Tariff, ResponseType


def get_model_for_tariff(tariff: Tariff, response_type: ResponseType) -> str:
    """
    Возвращает модель для указанного тарифа и типа ответа.
    """
    if response_type == ResponseType.TEXT:
        return _get_text_model(tariff)
    elif response_type == ResponseType.IMAGE:
        return _get_image_model(tariff)
    return settings.free_text_model


def _get_text_model(tariff: Tariff) -> str:
    if tariff == Tariff.FREE:
        return settings.free_text_model
    elif tariff == Tariff.LITE:
        return settings.lite_text_model
    elif tariff == Tariff.PRO:
        return settings.pro_text_model
    elif tariff == Tariff.BUSINESS:
        return settings.business_text_model
    return settings.free_text_model


def _get_image_model(tariff: Tariff) -> str:
    if tariff == Tariff.FREE:
        return settings.free_image_model
    elif tariff == Tariff.LITE:
        return settings.lite_image_model
    elif tariff == Tariff.PRO:
        return settings.pro_image_model
    elif tariff == Tariff.BUSINESS:
        return settings.business_image_model
    return settings.free_image_model


def get_default_models() -> dict:
    """Возвращает модели по умолчанию для FREE тарифа."""
    return {
        "text": settings.free_text_model,
        "image": settings.free_image_model,
    }