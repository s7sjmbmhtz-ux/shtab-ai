"""
Конфигурация тарифов ШТАБ AI
"""

from typing import Dict, Any

TARIFFS: Dict[str, Dict[str, Any]] = {
    "free": {
        "id": "free",
        "name": "FREE",
        "price": 0,
        "currency": "RUB",
        "period": "месяц",
        "text_limit": 3,
        "image_limit": 1,
        "description": "Знакомство с ботом, базовые AI инструменты",
        "for": "новичков, тестирования",
        "color": "⚪",
        "features": [
            "3 текста в день",
            "1 изображение в день",
            "DeepSeek Flash",
            "Gemini Flash Lite"
        ]
    },
    "lite": {
        "id": "lite",
        "name": "LITE",
        "price": 499,
        "currency": "RUB",
        "period": "месяц",
        "text_limit": 20,
        "image_limit": 5,
        "description": "Начинающим предпринимателям, малому бизнесу",
        "for": "начинающих предпринимателей, малого бизнеса",
        "color": "🟢",
        "features": [
            "20 текстов в день",
            "5 изображений в день",
            "DeepSeek Pro",
            "Gemini Flash"
        ]
    },
    "pro": {
        "id": "pro",
        "name": "PRO",
        "price": 1490,
        "currency": "RUB",
        "period": "месяц",
        "text_limit": 100,
        "image_limit": 20,
        "description": "Активному бизнесу, маркетологам, продавцам",
        "for": "активного бизнеса, маркетологов, продавцов",
        "color": "🔵",
        "features": [
            "100 текстов в день",
            "20 изображений в день",
            "GPT-5.4 mini",
            "Gemini Pro Image"
        ]
    },
    "business": {
        "id": "business",
        "name": "BUSINESS",
        "price": 3990,
        "currency": "RUB",
        "period": "месяц",
        "text_limit": 500,
        "image_limit": 100,
        "description": "Компаниям, командам, большому объёму",
        "for": "компаний, команд, большого объёма",
        "color": "🟣",
        "features": [
            "500 текстов в день",
            "100 изображений в день",
            "GPT-5.5",
            "Gemini Pro Image"
        ]
    }
}


def get_tariff(tariff_id: str) -> Dict[str, Any]:
    """Возвращает конфигурацию тарифа по ID."""
    return TARIFFS.get(tariff_id, TARIFFS["free"])


def get_all_tariffs() -> Dict[str, Dict[str, Any]]:
    """Возвращает все тарифы."""
    return TARIFFS