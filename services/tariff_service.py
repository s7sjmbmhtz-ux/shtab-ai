"""
Сервис для работы с тарифами.
"""

from typing import Dict, Any, List
from tariffs import TARIFFS, get_tariff, get_all_tariffs


def get_tariff_config(tariff_id: str) -> Dict[str, Any]:
    """Возвращает полную конфигурацию тарифа."""
    return get_tariff(tariff_id)


def get_tariff_limits(tariff_id: str) -> Dict[str, int]:
    """Возвращает лимиты тарифа."""
    config = get_tariff_config(tariff_id)
    return {
        "text": config.get("text_limit", 0),
        "image": config.get("image_limit", 0),
        "video": config.get("video_limit", 0),
    }


def get_tariff_features(tariff_id: str) -> List[str]:
    """Возвращает список функций тарифа."""
    config = get_tariff_config(tariff_id)
    return config.get("features", [])


def get_tariff_price(tariff_id: str) -> int:
    """Возвращает цену тарифа."""
    return get_tariff_config(tariff_id).get("price", 0)


def get_tariff_name(tariff_id: str) -> str:
    """Возвращает название тарифа."""
    return get_tariff_config(tariff_id).get("name", tariff_id.upper())


def get_all_tariff_ids() -> List[str]:
    """Возвращает список всех ID тарифов."""
    return list(TARIFFS.keys())
