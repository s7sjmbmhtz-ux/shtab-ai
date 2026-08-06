"""Inline-клавиатуры админ-панели ШТАБ AI."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from model_catalog import GenerationKind


def admin_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin:users")],
        [
            InlineKeyboardButton(text="🤖 Модели", callback_data="admin:models"),
            InlineKeyboardButton(text="💎 Пакеты", callback_data="admin:packages"),
        ],
        [
            InlineKeyboardButton(text="💳 Платежи", callback_data="admin:payments"),
            InlineKeyboardButton(text="⚠️ Ошибки", callback_data="admin:errors"),
        ],
        [
            InlineKeyboardButton(text="📣 Рассылка", callback_data="admin:broadcast"),
            InlineKeyboardButton(text="🩺 Система", callback_data="admin:health"),
        ],
        [InlineKeyboardButton(text="📜 Журнал действий", callback_data="admin:audit")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="admin:close")],
    ])


def admin_back_keyboard(target: str = "main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"admin:{target}")],
    ])


def users_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔎 Найти пользователя", callback_data="admin:user_search")],
        [InlineKeyboardButton(text="🕘 Последние пользователи", callback_data="admin:user_recent")],
        [InlineKeyboardButton(text="⬅️ В админ-панель", callback_data="admin:main")],
    ])


def user_card_keyboard(user_id: int, *, blocked: bool) -> InlineKeyboardMarkup:
    block_text = "✅ Разблокировать" if blocked else "⛔ Заблокировать"
    block_action = "unblock" if blocked else "block"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Начислить", callback_data=f"admin:user_add:{user_id}"),
            InlineKeyboardButton(text="➖ Списать", callback_data=f"admin:user_sub:{user_id}"),
        ],
        [InlineKeyboardButton(text="🎁 Сбросить бесплатные попытки", callback_data=f"admin:user_free:{user_id}")],
        [InlineKeyboardButton(text=block_text, callback_data=f"admin:user_{block_action}:{user_id}")],
        [InlineKeyboardButton(text="📜 История операций", callback_data=f"admin:user_history:{user_id}")],
        [InlineKeyboardButton(text="⬅️ К пользователям", callback_data="admin:users")],
    ])


def confirm_keyboard(confirm_data: str, cancel_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=confirm_data)],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=cancel_data)],
    ])


def model_categories_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Текст", callback_data=f"admin:model_kind:{GenerationKind.TEXT.value}")],
        [InlineKeyboardButton(text="🖼 Изображения", callback_data=f"admin:model_kind:{GenerationKind.IMAGE.value}")],
        [InlineKeyboardButton(text="🎬 Видео", callback_data=f"admin:model_kind:{GenerationKind.VIDEO.value}")],
        [InlineKeyboardButton(text="⬅️ В админ-панель", callback_data="admin:main")],
    ])


def model_list_keyboard(models: list[tuple[str, str, bool]], kind: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for key, title, enabled in models:
        icon = "🟢" if enabled else "🔴"
        rows.append([InlineKeyboardButton(text=f"{icon} {title}", callback_data=f"admin:model:{key}")])
    rows.append([InlineKeyboardButton(text="⬅️ К категориям", callback_data="admin:models")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def model_card_keyboard(model_key: str, *, enabled: bool, kind: str) -> InlineKeyboardMarkup:
    toggle_text = "🔴 Отключить" if enabled else "🟢 Включить"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data=f"admin:model_toggle:{model_key}")],
        [InlineKeyboardButton(text="⬅️ К списку", callback_data=f"admin:model_kind:{kind}")],
    ])


def package_list_keyboard(packages: list[dict]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for package in packages:
        icon = "🟢" if package["enabled"] else "🔴"
        rows.append([
            InlineKeyboardButton(
                text=f"{icon} {package['title']} · {package['tokens']} 💎 · {package['price_rub']} ₽",
                callback_data=f"admin:package:{package['package_key']}",
            )
        ])
    rows.append([InlineKeyboardButton(text="⬅️ В админ-панель", callback_data="admin:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def package_card_keyboard(package_key: str, *, enabled: bool) -> InlineKeyboardMarkup:
    toggle_text = "🔴 Отключить" if enabled else "🟢 Включить"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💎 Изменить токены", callback_data=f"admin:package_tokens:{package_key}"),
            InlineKeyboardButton(text="₽ Изменить цену", callback_data=f"admin:package_price:{package_key}"),
        ],
        [InlineKeyboardButton(text=toggle_text, callback_data=f"admin:package_toggle:{package_key}")],
        [InlineKeyboardButton(text="⬅️ К пакетам", callback_data="admin:packages")],
    ])


def broadcast_preview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить всем", callback_data="admin:broadcast_confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:broadcast_cancel")],
    ])
