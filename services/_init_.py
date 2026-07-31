"""
Сервисы для работы с подписками, тарифами и использованием.
"""

from .subscription_service import (
    get_user_tariff,
    set_user_tariff,
    get_user_limit,
    activate_subscription,
    get_subscription_end_date,
    get_user_tokens_balance,
    check_subscription_active,
    deduct_tokens_with_check
)
from .usage_service import (
    track_usage,
    get_user_usage_today,
    check_and_consume_limit,
    get_usage_stats
)
from .tariff_service import (
    get_tariff_config,
    get_tariff_limits,
    get_tariff_features,
    get_tariff_price,
    get_tariff_name,
    get_all_tariff_ids
)

__all__ = [
    # Subscription
    "get_user_tariff",
    "set_user_tariff",
    "get_user_limit",
    "activate_subscription",
    "get_subscription_end_date",
    "get_user_tokens_balance",
    "check_subscription_active",
    "deduct_tokens_with_check",
    # Usage
    "track_usage",
    "get_user_usage_today",
    "check_and_consume_limit",
    "get_usage_stats",
    # Tariff
    "get_tariff_config",
    "get_tariff_limits",
    "get_tariff_features",
    "get_tariff_price",
    "get_tariff_name",
    "get_all_tariff_ids",
]
