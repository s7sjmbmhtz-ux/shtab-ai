"""
Конфигурация тарифов.
"""

from enum import Enum
from typing import Dict, Any, List


class Tariff(str, Enum):
    FREE = "free"
    LITE = "lite"
    PRO = "pro"
    BUSINESS = "business"


TARIFFS: Dict[str, Dict[str, Any]] = {
    "free": {
        "id": "free",
        "name": "⚪ FREE",
        "color": "⚪",
        "price": 0,
        "period": "бессрочно",
        "text_limit": 3,
        "image_limit": 1,
        "video_limit": 0,
        "tokens": 100,
        "features": ["📝 Текстовые запросы", "🖼 Генерация изображений"],
        "description": "Для знакомства с сервисом"
    },
    "lite": {
        "id": "lite",
        "name": "🟢 LITE",
        "color": "🟢",
        "price": 499,
        "period": "месяц",
        "text_limit": 20,
        "image_limit": 5,
        "video_limit": 2,
        "tokens": 500,
        "features": ["📝 Текстовые запросы", "🖼 Генерация изображений", "🎬 Генерация видео"],
        "description": "Для небольших проектов"
    },
    "pro": {
        "id": "pro",
        "name": "🔵 PRO",
        "color": "🔵",
        "price": 1499,
        "period": "месяц",
        "text_limit": 100,
        "image_limit": 20,
        "video_limit": 10,
        "tokens": 2000,
        "features": ["📝 Текстовые запросы", "🖼 Генерация изображений", "🎬 Генерация видео", "📊 Расширенная аналитика"],
        "description": "Для бизнеса"
    },
    "business": {
        "id": "business",
        "name": "🟣 BUSINESS",
        "color": "🟣",
        "price": 4999,
        "period": "месяц",
        "text_limit": 500,
        "image_limit": 100,
        "video_limit": 50,
        "tokens": 10000,
        "features": ["📝 Текстовые запросы", "🖼 Генерация изображений", "🎬 Генерация видео", "📊 Расширенная аналитика", "👥 Приоритетная поддержка", "🔒 Индивидуальные настройки"],
        "description": "Для крупных компаний"
    }
}


def get_all_tariffs() -> Dict[str, Dict[str, Any]]:
    """Получить все тарифы"""
    return TARIFFS


def get_tariff(tariff_id: str) -> Dict[str, Any]:
    """Получить тариф по ID"""
    return TARIFFS.get(tariff_id, TARIFFS["free"])


def get_tariff_price(tariff_id: str) -> int:
    """Получить цену тарифа"""
    return get_tariff(tariff_id).get("price", 0)


def get_tariff_limits(tariff_id: str) -> Dict[str, int]:
    """Получить лимиты тарифа"""
    tariff = get_tariff(tariff_id)
    return {
        "text": tariff.get("text_limit", 0),
        "image": tariff.get("image_limit", 0),
        "video": tariff.get("video_limit", 0),
        "tokens": tariff.get("tokens", 0)
    }


def get_tariff_features(tariff_id: str) -> List[str]:
    """Получить список функций тарифа"""
    return get_tariff(tariff_id).get("features", [])
