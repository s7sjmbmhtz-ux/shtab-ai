"""Полноценная Telegram-админка ШТАБ AI."""
from __future__ import annotations

import asyncio
import contextlib
import html
from itertools import product
from typing import Any

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from admin_keyboards import (
    admin_back_keyboard,
    admin_main_keyboard,
    broadcast_preview_keyboard,
    confirm_keyboard,
    model_card_keyboard,
    model_categories_keyboard,
    model_list_keyboard,
    package_card_keyboard,
    package_list_keyboard,
    generation_job_card_keyboard,
    generation_jobs_keyboard,
    user_card_keyboard,
    users_keyboard,
)
from admin_states import (
    AdminBroadcastStates,
    AdminModelStates,
    AdminPackageStates,
    AdminUserStates,
)
from database import db_manager
from model_catalog import GenerationKind, MODELS, get_model
from services.operations_service import operations_service
from services.generation_jobs import generation_job_service
from settings import settings
from utils import logger
from video_options import (
    Choice,
    default_video_selection,
    get_video_options,
    selection_labels,
    video_cost_tokens,
)

router = Router(name="admin_router")


class AdminFilter(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        return bool(event.from_user and settings.is_admin(event.from_user.id))


router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())


def _safe(value: Any) -> str:
    return html.escape(str(value or "—"))


async def _edit(callback: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            await callback.message.answer(text, reply_markup=reply_markup)


async def _audit(admin_id: int, action: str, *, target: int | None = None, details: str = "") -> None:
    await db_manager.log_admin_action(admin_id, action, target_user_id=target, details=details)


async def _user_card_text(user_id: int) -> tuple[str, bool]:
    user = await db_manager.get_user(user_id)
    if not user:
        return "Пользователь не найден.", False
    free = await db_manager.get_free_credits(user_id)
    async with db_manager.connection() as conn:
        generations = int((await (await conn.execute(
            "SELECT COUNT(*) AS c FROM token_transactions WHERE user_id=? AND type IN ('spend','free_trial')",
            (user_id,),
        )).fetchone())["c"])
        paid = await (await conn.execute(
            "SELECT COUNT(*) AS c, COALESCE(SUM(amount),0) AS total FROM payments WHERE user_id=? AND status='paid'",
            (user_id,),
        )).fetchone()
    blocked = bool(user.get("is_blocked"))
    username = f"@{user['username']}" if user.get("username") else "—"
    status = "⛔ Заблокирован" if blocked else "✅ Активен"
    text = (
        "<b>👤 Пользователь</b>\n\n"
        f"ID: <code>{user_id}</code>\n"
        f"Имя: <b>{_safe(user.get('first_name'))}</b>\n"
        f"Username: <b>{_safe(username)}</b>\n"
        f"Статус: <b>{status}</b>\n"
        f"Баланс: <b>{int(user.get('tokens') or 0)} 💎</b>\n"
        f"Генераций: <b>{generations}</b>\n"
        f"Оплат: <b>{int(paid['c'])}</b> на <b>{float(paid['total']):.2f} ₽</b>\n"
        f"Бесплатно: текст {free['text_left']}, изображение {free['image_left']}, видео {free['video_left']}\n"
        f"Регистрация: <code>{_safe(str(user.get('created_at') or '')[:16])}</code>\n"
        f"Последняя активность: <code>{_safe(str(user.get('last_activity') or '')[:16])}</code>"
    )
    if blocked and user.get("blocked_reason"):
        text += f"\nПричина: {_safe(user['blocked_reason'])}"
    return text, blocked


async def _show_user(callback: CallbackQuery, user_id: int) -> None:
    text, blocked = await _user_card_text(user_id)
    await _edit(callback, text, user_card_keyboard(user_id, blocked=blocked))


@router.message(Command("admin"))
@router.message(F.text == "🛠 Админ-панель")
@router.message(F.text == "👑 Статистика")
async def open_admin(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _audit(message.from_user.id, "admin_open")
    await message.answer(
        "<b>🛠 Админ-панель ШТАБ AI</b>\n\nВыберите раздел:",
        reply_markup=admin_main_keyboard(),
    )


@router.callback_query(F.data == "admin:main")
async def admin_main(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await _edit(callback, "<b>🛠 Админ-панель ШТАБ AI</b>\n\nВыберите раздел:", admin_main_keyboard())


@router.callback_query(F.data == "admin:close")
async def admin_close(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await _edit(callback, "Админ-панель закрыта.")


@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery) -> None:
    async with db_manager.connection() as conn:
        users = await (await conn.execute(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN date(created_at)=date('now') THEN 1 ELSE 0 END) AS new_today,
                      SUM(CASE WHEN date(last_activity)=date('now') THEN 1 ELSE 0 END) AS active_today,
                      SUM(CASE WHEN is_blocked=1 THEN 1 ELSE 0 END) AS blocked,
                      COALESCE(SUM(tokens),0) AS balances
               FROM users"""
        )).fetchone()
        payments = await (await conn.execute(
            """SELECT COUNT(*) AS count, COALESCE(SUM(amount),0) AS revenue
               FROM payments WHERE status='paid'"""
        )).fetchone()
        generations = await (await conn.execute(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN type='free_trial' THEN 1 ELSE 0 END) AS free_count,
                      COALESCE(-SUM(CASE WHEN type='spend' THEN amount ELSE 0 END),0) AS spent
               FROM token_transactions WHERE type IN ('spend','free_trial')"""
        )).fetchone()
        failed_requests = int((await (await conn.execute(
            "SELECT COUNT(*) AS c FROM requests WHERE status!='success' OR error_message IS NOT NULL"
        )).fetchone())["c"])
        failed_payments = int((await (await conn.execute(
            "SELECT COUNT(*) AS c FROM payments WHERE status='failed'"
        )).fetchone())["c"])
        popular = await (await conn.execute(
            """SELECT description, COUNT(*) AS c FROM token_transactions
               WHERE type IN ('spend','free_trial')
               GROUP BY description ORDER BY c DESC LIMIT 5"""
        )).fetchall()
    popular_text = "\n".join(f"• {_safe(row['description'])}: <b>{row['c']}</b>" for row in popular) or "• Данных пока нет"
    text = (
        "<b>📊 Статистика</b>\n\n"
        f"Пользователей: <b>{int(users['total'] or 0)}</b>\n"
        f"Новых сегодня: <b>{int(users['new_today'] or 0)}</b>\n"
        f"Активных сегодня: <b>{int(users['active_today'] or 0)}</b>\n"
        f"Заблокировано: <b>{int(users['blocked'] or 0)}</b>\n"
        f"Токенов на балансах: <b>{int(users['balances'] or 0)} 💎</b>\n\n"
        f"Генераций: <b>{int(generations['total'] or 0)}</b>\n"
        f"Из них бесплатных: <b>{int(generations['free_count'] or 0)}</b>\n"
        f"Списано за генерации: <b>{int(generations['spent'] or 0)} 💎</b>\n\n"
        f"Успешных оплат: <b>{int(payments['count'] or 0)}</b>\n"
        f"Выручка: <b>{float(payments['revenue'] or 0):.2f} ₽</b>\n"
        f"Ошибок генераций в БД: <b>{failed_requests}</b>\n"
        f"Неудачных платежей: <b>{failed_payments}</b>\n\n"
        "<b>Популярные операции:</b>\n" + popular_text
    )
    await callback.answer()
    await _edit(callback, text, admin_back_keyboard())


@router.callback_query(F.data == "admin:economy")
async def admin_economy(callback: CallbackQuery) -> None:
    async with db_manager.connection() as conn:
        payments = await (await conn.execute(
            """SELECT COALESCE(SUM(amount),0) AS total,
                      COALESCE(SUM(CASE WHEN date(paid_at)=date('now')
                                       THEN amount ELSE 0 END),0) AS today
               FROM payments WHERE status='paid'"""
        )).fetchone()
        economics = await (await conn.execute(
            """SELECT
                   SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS completed,
                   SUM(CASE WHEN status='refunded' THEN 1 ELSE 0 END) AS refunded,
                   SUM(CASE WHEN status IN ('reserved','processing') THEN 1 ELSE 0 END) AS pending,
                   COALESCE(SUM(CASE WHEN status='completed' THEN revenue_rub ELSE 0 END),0) AS revenue,
                   COALESCE(SUM(CASE WHEN status IN ('completed','refunded') THEN provider_cost_rub ELSE 0 END),0) AS cost,
                   COALESCE(SUM(CASE WHEN status IN ('completed','refunded') AND charge_source!='tokens'
                                     THEN provider_cost_rub ELSE 0 END),0) AS promo_cost
               FROM generation_economics
               WHERE created_at >= datetime('now', '-30 days')"""
        )).fetchone()
        balances = float((await (await conn.execute(
            "SELECT COALESCE(SUM(tokens),0) AS total FROM users"
        )).fetchone())["total"] or 0)
        models = await (await conn.execute(
            """SELECT model_key,
                      SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS completed,
                      SUM(CASE WHEN status='refunded' THEN 1 ELSE 0 END) AS refunded,
                      COALESCE(SUM(CASE WHEN status='completed' THEN revenue_rub ELSE 0 END),0) AS revenue,
                      COALESCE(SUM(CASE WHEN status IN ('completed','refunded') THEN provider_cost_rub ELSE 0 END),0) AS cost
               FROM generation_economics
               WHERE created_at >= datetime('now', '-7 days')
               GROUP BY model_key
               ORDER BY cost DESC, completed DESC LIMIT 8"""
        )).fetchall()

    revenue = float(economics["revenue"] or 0)
    cost = float(economics["cost"] or 0)
    profit = revenue - cost
    margin = profit * 100 / revenue if revenue > 0 else 0.0
    liability = balances * settings.ECONOMY_TOKEN_VALUE_KOPEKS / 100.0
    lines = [
        "<b>💹 Экономика</b>",
        "",
        f"Получено через ЮKassa: <b>{float(payments['total'] or 0):.2f} ₽</b>",
        f"Сегодня: <b>{float(payments['today'] or 0):.2f} ₽</b>",
        f"Токены на балансах: <b>{int(balances)} 💎</b> ≈ {liability:.2f} ₽ обязательств",
        "",
        "<b>Генерации за 30 дней:</b>",
        f"Завершено: <b>{int(economics['completed'] or 0)}</b>",
        f"Возвращено: <b>{int(economics['refunded'] or 0)}</b>",
        f"В обработке: <b>{int(economics['pending'] or 0)}</b>",
        f"Расчётная выручка: <b>{revenue:.2f} ₽</b>",
        f"Себестоимость: <b>{cost:.2f} ₽</b>",
        f"Валовая прибыль: <b>{profit:.2f} ₽</b>",
        f"Маржа: <b>{margin:.1f}%</b>",
        f"Бесплатные и админ-запуски: <b>{float(economics['promo_cost'] or 0):.2f} ₽</b>",
        "",
        "<b>Модели за 7 дней:</b>",
    ]
    for row in models:
        model_revenue = float(row["revenue"] or 0)
        model_cost = float(row["cost"] or 0)
        model_margin = (
            (model_revenue - model_cost) * 100 / model_revenue
            if model_revenue > 0 else 0.0
        )
        lines.append(
            f"• {_safe(row['model_key'])}: <b>{int(row['completed'] or 0)}</b> шт. · "
            f"{model_revenue - model_cost:.2f} ₽ · {model_margin:.1f}% · "
            f"возвраты {int(row['refunded'] or 0)}"
        )
    if not models:
        lines.append("• Данных пока нет")
    lines.extend([
        "",
        f"Расчёт консервативный: <b>{settings.ECONOMY_TOKEN_VALUE_KOPEKS} коп./💎</b>. "
        "Налоги и постоянные расходы сюда не входят.",
    ])
    await callback.answer()
    await _edit(callback, "\n".join(lines), admin_back_keyboard())


@router.callback_query(F.data == "admin:users")
async def admin_users(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await _edit(callback, "<b>👥 Пользователи</b>\n\nНайдите пользователя по Telegram ID, @username или имени.", users_keyboard())


@router.callback_query(F.data == "admin:user_search")
async def admin_user_search(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminUserStates.waiting_query)
    await callback.answer()
    await _edit(callback, "Отправьте Telegram ID, @username или часть имени.", admin_back_keyboard("users"))


@router.message(AdminUserStates.waiting_query, F.text)
async def admin_user_search_result(message: Message, state: FSMContext) -> None:
    rows = await db_manager.search_users(message.text, limit=20)
    await state.clear()
    if not rows:
        await message.answer("Пользователь не найден.", reply_markup=users_keyboard())
        return
    keyboard_rows = []
    for row in rows:
        username = f"@{row['username']}" if row.get("username") else row.get("first_name") or "Без имени"
        icon = "⛔" if row.get("is_blocked") else "👤"
        keyboard_rows.append([
            InlineKeyboardButton(
                text=f"{icon} {username} · {row['telegram_id']}",
                callback_data=f"admin:user:{row['telegram_id']}",
            )
        ])
    keyboard_rows.append([InlineKeyboardButton(text="⬅️ К пользователям", callback_data="admin:users")])
    await message.answer(
        f"Найдено: <b>{len(rows)}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
    )


@router.callback_query(F.data == "admin:user_recent")
async def admin_recent_users(callback: CallbackQuery) -> None:
    rows = await db_manager.get_recent_users(20)
    keyboard_rows = []
    for row in rows:
        username = f"@{row['username']}" if row.get("username") else row.get("first_name") or "Без имени"
        icon = "⛔" if row.get("is_blocked") else "👤"
        keyboard_rows.append([
            InlineKeyboardButton(text=f"{icon} {username} · {row['telegram_id']}", callback_data=f"admin:user:{row['telegram_id']}")
        ])
    keyboard_rows.append([InlineKeyboardButton(text="⬅️ К пользователям", callback_data="admin:users")])
    await callback.answer()
    await _edit(callback, "<b>🕘 Последние пользователи</b>", InlineKeyboardMarkup(inline_keyboard=keyboard_rows))


@router.callback_query(F.data.startswith("admin:user:"))
async def admin_user_card(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    user_id = int(callback.data.rsplit(":", 1)[1])
    await callback.answer()
    await _show_user(callback, user_id)


@router.callback_query(F.data.startswith("admin:user_add:"))
@router.callback_query(F.data.startswith("admin:user_sub:"))
async def admin_user_adjust_start(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":")
    action = "add" if parts[1] == "user_add" else "sub"
    user_id = int(parts[2])
    await state.set_state(AdminUserStates.waiting_token_amount)
    await state.update_data(target_user_id=user_id, adjust_action=action)
    verb = "начисления" if action == "add" else "списания"
    await callback.answer()
    await _edit(callback, f"Введите количество токенов для {verb} пользователю <code>{user_id}</code>.", admin_back_keyboard("users"))


@router.message(AdminUserStates.waiting_token_amount, F.text)
async def admin_user_adjust_amount(message: Message, state: FSMContext) -> None:
    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("Введите целое число больше нуля.")
        return
    if amount <= 0 or amount > 10_000_000:
        await message.answer("Количество должно быть от 1 до 10 000 000.")
        return
    await state.update_data(adjust_amount=amount)
    await state.set_state(AdminUserStates.waiting_token_comment)
    await message.answer("Введите обязательный комментарий к операции.")


@router.message(AdminUserStates.waiting_token_comment, F.text)
async def admin_user_adjust_comment(message: Message, state: FSMContext) -> None:
    comment = message.text.strip()
    if len(comment) < 3:
        await message.answer("Комментарий слишком короткий.")
        return
    if len(comment) > 500:
        await message.answer("Комментарий не должен превышать 500 символов.")
        return
    data = await state.get_data()
    await state.update_data(adjust_comment=comment)
    sign = "+" if data["adjust_action"] == "add" else "−"
    await message.answer(
        "<b>Подтверждение изменения баланса</b>\n\n"
        f"Пользователь: <code>{data['target_user_id']}</code>\n"
        f"Изменение: <b>{sign}{data['adjust_amount']} 💎</b>\n"
        f"Комментарий: {_safe(comment)}",
        reply_markup=confirm_keyboard("admin:user_adjust_confirm", f"admin:user:{data['target_user_id']}"),
    )


@router.callback_query(F.data == "admin:user_adjust_confirm")
async def admin_user_adjust_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    required = {"target_user_id", "adjust_action", "adjust_amount", "adjust_comment"}
    if not required.issubset(data):
        await callback.answer("Операция устарела", show_alert=True)
        return
    user_id = int(data["target_user_id"])
    amount = int(data["adjust_amount"])
    delta = amount if data["adjust_action"] == "add" else -amount
    try:
        balance = await db_manager.admin_adjust_tokens(user_id, delta, f"Администратор: {data['adjust_comment']}")
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await _audit(callback.from_user.id, "token_adjustment", target=user_id, details=f"delta={delta}; {data['adjust_comment']}")
    await state.clear()
    await callback.answer("Баланс изменён")
    text, blocked = await _user_card_text(user_id)
    text += f"\n\n✅ Новый баланс: <b>{balance} 💎</b>"
    await _edit(callback, text, user_card_keyboard(user_id, blocked=blocked))


@router.callback_query(F.data.startswith("admin:user_free:"))
async def admin_reset_free(callback: CallbackQuery) -> None:
    user_id = int(callback.data.rsplit(":", 1)[1])
    await db_manager.set_free_credits(
        user_id,
        text_left=settings.FREE_TEXT_GENERATIONS,
        image_left=settings.FREE_IMAGE_GENERATIONS,
        video_left=settings.FREE_VIDEO_GENERATIONS,
    )
    await _audit(callback.from_user.id, "free_credits_reset", target=user_id)
    await callback.answer("Бесплатные попытки восстановлены", show_alert=True)
    await _show_user(callback, user_id)


@router.callback_query(F.data.startswith("admin:user_block:"))
async def admin_block_start(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = int(callback.data.rsplit(":", 1)[1])
    if settings.is_admin(user_id):
        await callback.answer("Администратора блокировать нельзя", show_alert=True)
        return
    await state.set_state(AdminUserStates.waiting_block_reason)
    await state.update_data(target_user_id=user_id)
    await callback.answer()
    await _edit(callback, f"Введите причину блокировки пользователя <code>{user_id}</code>.", admin_back_keyboard("users"))


@router.message(AdminUserStates.waiting_block_reason, F.text)
async def admin_block_reason(message: Message, state: FSMContext) -> None:
    reason = message.text.strip()
    if len(reason) < 3:
        await message.answer("Укажите понятную причину.")
        return
    if len(reason) > 500:
        await message.answer("Причина не должна превышать 500 символов.")
        return
    data = await state.get_data()
    await state.update_data(block_reason=reason)
    await message.answer(
        f"Заблокировать пользователя <code>{data['target_user_id']}</code>?\nПричина: {_safe(reason)}",
        reply_markup=confirm_keyboard("admin:user_block_confirm", f"admin:user:{data['target_user_id']}"),
    )


@router.callback_query(F.data == "admin:user_block_confirm")
async def admin_block_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    user_id = int(data.get("target_user_id", 0))
    reason = str(data.get("block_reason", ""))
    if not user_id or not reason:
        await callback.answer("Операция устарела", show_alert=True)
        return
    await db_manager.set_user_blocked(user_id, True, reason)
    await _audit(callback.from_user.id, "user_blocked", target=user_id, details=reason)
    await state.clear()
    await callback.answer("Пользователь заблокирован", show_alert=True)
    await _show_user(callback, user_id)


@router.callback_query(F.data.startswith("admin:user_unblock:"))
async def admin_unblock(callback: CallbackQuery) -> None:
    user_id = int(callback.data.rsplit(":", 1)[1])
    await db_manager.set_user_blocked(user_id, False)
    await _audit(callback.from_user.id, "user_unblocked", target=user_id)
    await callback.answer("Пользователь разблокирован", show_alert=True)
    await _show_user(callback, user_id)


@router.callback_query(F.data.startswith("admin:user_history:"))
async def admin_user_history(callback: CallbackQuery) -> None:
    user_id = int(callback.data.rsplit(":", 1)[1])
    rows = await db_manager.get_token_transactions(user_id, 20)
    lines = [f"<b>📜 Операции пользователя</b> <code>{user_id}</code>"]
    for row in rows:
        amount = int(row["amount"])
        sign = "+" if amount > 0 else ""
        description = str(row.get("description") or row.get("type") or "Операция")
        if len(description) > 160:
            description = description[:157] + "…"
        lines.append(f"<code>{str(row['created_at'])[:16]}</code> · <b>{sign}{amount} 💎</b>\n{_safe(description)}")
    if not rows:
        lines.append("\nОпераций пока нет.")
    await callback.answer()
    await _edit(callback, "\n\n".join(lines), admin_back_keyboard(f"user:{user_id}"))


@router.callback_query(F.data == "admin:models")
async def admin_models(callback: CallbackQuery) -> None:
    await callback.answer()
    await _edit(callback, "<b>🤖 Управление моделями</b>\n\nОтключённые модели скрываются из меню и не запускаются по старым кнопкам.", model_categories_keyboard())


@router.callback_query(F.data.startswith("admin:model_kind:"))
async def admin_model_kind(callback: CallbackQuery) -> None:
    kind_value = callback.data.rsplit(":", 1)[1]
    try:
        kind = GenerationKind(kind_value)
    except ValueError:
        await callback.answer("Неизвестная категория", show_alert=True)
        return
    models = [
        (model.key, model.title, db_manager.is_model_enabled_cached(model.key))
        for model in MODELS.values() if model.kind == kind
    ]
    await callback.answer()
    await _edit(callback, f"<b>Модели: {kind.value}</b>\n\n🟢 включена · 🔴 отключена", model_list_keyboard(models, kind.value))


def _model_economics_text(model_key: str, db_settings: dict[str, Any]) -> str:
    stored_price = int(db_settings.get("token_cost") or 0)
    price = db_manager.get_model_safety_price(model_key, stored_price)
    model = get_model(model_key)
    price_title = (
        "Цена конфигурации по умолчанию"
        if model.kind == GenerationKind.VIDEO else "Цена"
    )
    provider_cost = db_settings.get("provider_cost_rub")
    margin = float(
        db_settings.get("min_margin_percent")
        if db_settings.get("min_margin_percent") is not None
        else settings.ECONOMY_MIN_MARGIN_PERCENT
    )
    minimum = db_manager.minimum_safe_tokens(model_key)
    safe = db_manager.is_generation_price_safe(model_key, price)
    cost_label = (
        f"{float(provider_cost):.2f} ₽"
        if provider_cost is not None else "не задана"
    )
    return (
        f"{price_title}: <b>{price} 💎</b>\n"
        f"Расчётная себестоимость: <b>{cost_label}</b>"
        f"{' (конфигурация по умолчанию)' if model.kind == GenerationKind.VIDEO else ''}\n"
        f"Минимальная маржа: <b>{margin:.1f}%</b>\n"
        f"Защитный минимум: <b>{minimum if minimum is not None else '—'} 💎</b>\n"
        f"Проверка экономики: <b>{'✅ безопасно' if safe else '⛔ запуск запрещён'}</b>\n"
    )


def _video_price_lines(model_key: str) -> list[str]:
    options = get_video_options(model_key)
    base = default_video_selection(model_key)
    qualities = options.qualities or (Choice(str(base.get("quality") or ""), options.fixed_quality_label or "—"),)
    resolutions = options.resolutions or (Choice(str(base.get("resolution") or ""), options.fixed_resolution_label or "—"),)
    durations = options.durations or (int(base.get("duration") or 0),)
    audios = options.audio_choices or (Choice(str(base.get("audio") or ""), options.fixed_audio_label or "—"),)
    lines: list[str] = []
    for quality, resolution, duration, audio in product(qualities, resolutions, durations, audios):
        selection = dict(base)
        selection.update(
            quality=quality.value or None,
            resolution=resolution.value or None,
            duration=duration or None,
            audio=audio.value or None,
        )
        try:
            price = video_cost_tokens(model_key, selection)
        except (KeyError, ValueError):
            continue
        labels = selection_labels(model_key, selection)
        lines.append(
            f"• {labels['quality']} · {labels['resolution']} · {labels['duration']} · {labels['audio']} — <b>{price} 💎</b>"
        )
    return lines


@router.callback_query(F.data.startswith("admin:model:"))
async def admin_model_card(callback: CallbackQuery) -> None:
    model_key = callback.data.split(":", 2)[2]
    try:
        model = get_model(model_key)
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    db_settings = await db_manager.get_model_settings(model_key) or {}
    enabled = bool(db_settings.get("enabled", model.enabled))
    text = (
        f"<b>🤖 {model.title}</b>\n\n"
        f"Ключ: <code>{model.key}</code>\n"
        f"Тип: <b>{model.kind.value}</b>\n"
        f"Статус: <b>{'🟢 включена' if enabled else '🔴 отключена'}</b>\n"
        f"Endpoint: <code>{_safe(model.endpoint)}</code>\n"
        + _model_economics_text(model_key, db_settings)
    )
    if model.kind == GenerationKind.VIDEO:
        lines = _video_price_lines(model_key)
        text += "\n<b>Актуальные конфигурации:</b>\n" + ("\n".join(lines) if lines else "Нет подтверждённых конфигураций")
    if db_settings.get("disabled_reason"):
        text += (
            "\n\n<b>Причина отключения:</b> "
            f"{_safe(db_settings['disabled_reason'])}"
        )
        if db_settings.get("auto_disabled_until"):
            text += f"\nАвтовключение: <code>{_safe(db_settings['auto_disabled_until'])}</code>"
    await callback.answer()
    await _edit(callback, text, model_card_keyboard(model_key, enabled=enabled, kind=model.kind.value))


@router.callback_query(F.data == "admin:jobs")
async def admin_jobs(callback: CallbackQuery) -> None:
    async with db_manager.connection() as conn:
        rows = await (await conn.execute(
            """SELECT * FROM generation_jobs
               ORDER BY CASE WHEN status IN ('processing','ready') THEN 0 ELSE 1 END,
                        updated_at DESC, id DESC LIMIT 25"""
        )).fetchall()
    jobs = [dict(row) for row in rows]
    active = sum(row["status"] in {"processing", "ready"} for row in jobs)
    await callback.answer()
    await _edit(
        callback,
        f"<b>🧾 Очередь генераций</b>\n\nАктивных: <b>{active}</b>. "
        "Ниже активные и последние завершённые задания.",
        generation_jobs_keyboard(jobs),
    )


@router.callback_query(F.data.startswith("admin:job:"))
async def admin_job_card(callback: CallbackQuery) -> None:
    job_id = int(callback.data.rsplit(":", 1)[1])
    row = await db_manager.get_generation_job(job_id)
    if not row:
        await callback.answer("Задание не найдено", show_alert=True)
        return
    error = str(row.get("error_message") or "—")[:1000]
    text = (
        f"<b>🧾 Задание #{job_id}</b>\n\n"
        f"Пользователь: <code>{row['user_id']}</code>\n"
        f"Модель: <code>{_safe(row['model_key'])}</code>\n"
        f"Статус: <b>{_safe(row['status'])}</b>\n"
        f"Request ID: <code>{_safe(row.get('provider_request_id'))}</code>\n"
        f"Списание: <b>{row['token_cost']} 💎</b> ({_safe(row['charge_source'])})\n"
        f"Попыток восстановления: <b>{row['attempts']}</b>\n"
        f"Создано: <code>{_safe(row['created_at'])}</code>\n"
        f"Обновлено: <code>{_safe(row['updated_at'])}</code>\n\n"
        f"Последняя ошибка: {_safe(error)}"
    )
    await callback.answer()
    await _edit(callback, text, generation_job_card_keyboard(job_id, str(row["status"])))


@router.callback_query(F.data.startswith("admin:job_retry:"))
async def admin_job_retry(callback: CallbackQuery) -> None:
    job_id = int(callback.data.rsplit(":", 1)[1])
    scheduled = await generation_job_service.schedule_recovery(job_id)
    await _audit(callback.from_user.id, "generation_job_retry", details=f"job_id={job_id}")
    await callback.answer(
        "Проверка поставлена в очередь" if scheduled else "Задание уже проверяется или закрыто",
        show_alert=True,
    )


@router.callback_query(F.data.startswith("admin:job_refund:"))
async def admin_job_refund_confirm(callback: CallbackQuery) -> None:
    job_id = int(callback.data.rsplit(":", 1)[1])
    row = await db_manager.get_generation_job(job_id)
    if not row or row["status"] not in {"processing", "ready"}:
        await callback.answer("Задание уже закрыто", show_alert=True)
        return
    await callback.answer()
    await _edit(
        callback,
        f"Вернуть списание по заданию <b>#{job_id}</b> пользователю "
        f"<code>{row['user_id']}</code>? Задание будет закрыто.",
        confirm_keyboard(f"admin:job_refund_confirm:{job_id}", f"admin:job:{job_id}"),
    )


@router.callback_query(F.data.startswith("admin:job_refund_confirm:"))
async def admin_job_refund_execute(callback: CallbackQuery, bot: Bot) -> None:
    job_id = int(callback.data.rsplit(":", 1)[1])
    row = await db_manager.get_generation_job(job_id)
    if not row:
        await callback.answer("Задание не найдено", show_alert=True)
        return
    refunded = await generation_job_service.fail_and_refund(
        job_id,
        "Возврат администратором",
        count_failure=False,
    )
    if refunded:
        with contextlib.suppress(Exception):
            await bot.send_message(
                int(row["user_id"]),
                f"↩️ Списание по генерации <b>#{job_id}</b> возвращено администратором.",
            )
        await _audit(
            callback.from_user.id,
            "generation_job_refund",
            target=int(row["user_id"]),
            details=f"job_id={job_id}",
        )
    await callback.answer(
        "Списание возвращено" if refunded else "Задание уже закрыто",
        show_alert=True,
    )
    await _edit(
        callback,
        f"{'✅ Списание возвращено' if refunded else 'Задание уже было закрыто'} "
        f"по генерации <b>#{job_id}</b>.",
        admin_back_keyboard("jobs"),
    )


@router.callback_query(F.data == "admin:funnel")
async def admin_funnel(callback: CallbackQuery) -> None:
    stages = [
        ("bot_started", "Запустили бота"),
        ("model_selected", "Выбрали модель"),
        ("generation_confirmed", "Подтвердили генерацию"),
        ("generation_completed", "Получили результат"),
        ("packages_open", "Открыли пакеты"),
        ("payment_created", "Создали платёж"),
        ("payment_paid", "Оплатили"),
    ]
    async with db_manager.connection() as conn:
        rows = await (await conn.execute(
            """SELECT event, COUNT(*) AS events, COUNT(DISTINCT user_id) AS users
               FROM funnel_events
               WHERE created_at >= datetime('now', '-30 days')
               GROUP BY event"""
        )).fetchall()
    stats = {str(row["event"]): dict(row) for row in rows}
    lines = ["<b>📉 Воронка за 30 дней</b>", ""]
    previous = None
    for event, title in stages:
        users = int(stats.get(event, {}).get("users") or 0)
        events = int(stats.get(event, {}).get("events") or 0)
        conversion = "—" if previous in {None, 0} else f"{users * 100 / previous:.1f}%"
        lines.append(f"• {title}: <b>{users}</b> чел. · {events} событий · конверсия {conversion}")
        previous = users
    await callback.answer()
    await _edit(callback, "\n".join(lines), admin_back_keyboard())


@router.callback_query(F.data.startswith("admin:model_toggle:"))
async def admin_model_toggle(callback: CallbackQuery) -> None:
    model_key = callback.data.split(":", 2)[2]
    model = get_model(model_key)
    current = await db_manager.get_model_settings(model_key)
    enabled = not bool(current and current["enabled"])
    try:
        await db_manager.set_model_enabled(model_key, enabled)
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await _audit(callback.from_user.id, "model_enabled" if enabled else "model_disabled", details=model_key)
    await callback.answer("Модель включена" if enabled else "Модель отключена", show_alert=True)
    db_settings = await db_manager.get_model_settings(model_key) or {}
    text = (
        f"<b>🤖 {model.title}</b>\n\n"
        f"Ключ: <code>{model.key}</code>\n"
        f"Тип: <b>{model.kind.value}</b>\n"
        f"Статус: <b>{'🟢 включена' if enabled else '🔴 отключена'}</b>\n"
        f"Endpoint: <code>{_safe(model.endpoint)}</code>\n"
        + _model_economics_text(model_key, db_settings)
    )
    if model.kind == GenerationKind.VIDEO:
        text += "\n<b>Актуальные конфигурации:</b>\n" + "\n".join(_video_price_lines(model_key))
    await _edit(callback, text, model_card_keyboard(model_key, enabled=enabled, kind=model.kind.value))


@router.callback_query(F.data.startswith("admin:model_price:"))
@router.callback_query(F.data.startswith("admin:model_cost:"))
@router.callback_query(F.data.startswith("admin:model_margin:"))
async def admin_model_economics_start(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    prefix, model_key = callback.data.rsplit(":", 1)
    try:
        get_model(model_key)
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    if prefix.endswith("model_price"):
        field = "price"
        await state.set_state(AdminModelStates.waiting_price)
        prompt = "Введите новую цену генерации в 💎 целым числом."
    elif prefix.endswith("model_cost"):
        field = "provider_cost"
        await state.set_state(AdminModelStates.waiting_provider_cost)
        prompt = "Введите текущую себестоимость одной генерации в рублях."
    else:
        field = "margin"
        await state.set_state(AdminModelStates.waiting_margin)
        prompt = "Введите минимальную маржу от 0 до 99 процентов."
    await state.update_data(model_key=model_key, model_economics_field=field)
    await callback.answer()
    await _edit(callback, prompt, admin_back_keyboard(f"model:{model_key}"))


@router.message(AdminModelStates.waiting_price, F.text)
@router.message(AdminModelStates.waiting_provider_cost, F.text)
@router.message(AdminModelStates.waiting_margin, F.text)
async def admin_model_economics_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    model_key = str(data.get("model_key") or "")
    field = str(data.get("model_economics_field") or "")
    try:
        value = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer("Введите число больше нуля.")
        return
    if value <= 0 or value > 1_000_000:
        await message.answer("Значение вне допустимого диапазона.")
        return

    current = await db_manager.get_model_settings(model_key)
    if not current:
        await state.clear()
        await message.answer("Модель не найдена.")
        return
    try:
        if field == "price":
            if not value.is_integer():
                raise ValueError("Цена в 💎 должна быть целым числом")
            await db_manager.set_model_price(
                model_key,
                int(value),
                enabled=bool(current["enabled"]),
            )
            details = f"{model_key}: token_cost={int(value)}"
        elif field == "provider_cost":
            safe = await db_manager.set_model_economics(
                model_key,
                provider_cost_rub=value,
            )
            details = f"{model_key}: provider_cost_rub={value}"
            if not safe:
                details += "; auto_disabled=true"
        elif field == "margin":
            if value >= 100:
                raise ValueError("Маржа должна быть меньше 100 процентов")
            safe = await db_manager.set_model_economics(
                model_key,
                min_margin_percent=value,
            )
            details = f"{model_key}: min_margin_percent={value}"
            if not safe:
                details += "; auto_disabled=true"
        else:
            raise ValueError("Неизвестный параметр")
    except ValueError as exc:
        await message.answer(f"⚠️ {_safe(exc)}")
        return

    await _audit(message.from_user.id, "model_economics_updated", details=details)
    await state.clear()
    model = get_model(model_key)
    current = await db_manager.get_model_settings(model_key) or {}
    enabled = bool(current.get("enabled"))
    await message.answer(
        f"✅ Настройки <b>{_safe(model.title)}</b> обновлены.\n\n"
        + _model_economics_text(model_key, current),
        reply_markup=model_card_keyboard(
            model_key,
            enabled=enabled,
            kind=model.kind.value,
        ),
    )


@router.callback_query(F.data == "admin:packages")
async def admin_packages(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    packages = db_manager.get_token_packages_cached(enabled_only=False)
    await callback.answer()
    await _edit(callback, "<b>💎 Пакеты токенов</b>\n\nИзменения применяются сразу к меню покупки.", package_list_keyboard(packages))


@router.callback_query(F.data.startswith("admin:package:"))
async def admin_package_card(callback: CallbackQuery) -> None:
    key = callback.data.rsplit(":", 1)[1]
    package = db_manager.get_token_package_cached(key)
    if not package:
        await callback.answer("Пакет не найден", show_alert=True)
        return
    text = (
        f"<b>💎 { _safe(package['title']) }</b>\n\n"
        f"Ключ: <code>{key}</code>\n"
        f"Токены: <b>{package['tokens']} 💎</b>\n"
        f"Цена: <b>{package['price_rub']} ₽</b>\n"
        f"Статус: <b>{'🟢 включён' if package['enabled'] else '🔴 отключён'}</b>"
    )
    await callback.answer()
    await _edit(callback, text, package_card_keyboard(key, enabled=bool(package["enabled"])))


@router.callback_query(F.data.startswith("admin:package_tokens:"))
@router.callback_query(F.data.startswith("admin:package_price:"))
async def admin_package_edit_start(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":")
    field = "tokens" if parts[1] == "package_tokens" else "price_rub"
    key = parts[2]
    await state.update_data(package_key=key, package_field=field)
    if field == "tokens":
        await state.set_state(AdminPackageStates.waiting_tokens)
        prompt = "Введите новое количество токенов."
    else:
        await state.set_state(AdminPackageStates.waiting_price)
        prompt = "Введите новую цену в рублях целым числом."
    await callback.answer()
    await _edit(callback, prompt, admin_back_keyboard("packages"))


@router.message(AdminPackageStates.waiting_tokens, F.text)
@router.message(AdminPackageStates.waiting_price, F.text)
async def admin_package_edit_value(message: Message, state: FSMContext) -> None:
    try:
        value = int(message.text.strip())
    except ValueError:
        await message.answer("Введите целое число больше нуля.")
        return
    if value <= 0 or value > 100_000_000:
        await message.answer("Значение вне допустимого диапазона.")
        return
    data = await state.get_data()
    key = data["package_key"]
    field = data["package_field"]
    kwargs = {field: value}
    try:
        await db_manager.update_token_package(key, **kwargs)
    except ValueError as exc:
        await message.answer(f"⚠️ {_safe(exc)}")
        return
    await _audit(message.from_user.id, "package_updated", details=f"{key}: {field}={value}")
    await state.clear()
    package = db_manager.get_token_package_cached(key)
    await message.answer(
        f"✅ Пакет <b>{_safe(package['title'])}</b> обновлён.\n"
        f"{package['tokens']} 💎 за {package['price_rub']} ₽",
        reply_markup=package_card_keyboard(key, enabled=bool(package["enabled"])),
    )


@router.callback_query(F.data.startswith("admin:package_toggle:"))
async def admin_package_toggle(callback: CallbackQuery) -> None:
    key = callback.data.rsplit(":", 1)[1]
    package = db_manager.get_token_package_cached(key)
    if not package:
        await callback.answer("Пакет не найден", show_alert=True)
        return
    enabled = not bool(package["enabled"])
    await db_manager.update_token_package(key, enabled=enabled)
    await _audit(callback.from_user.id, "package_enabled" if enabled else "package_disabled", details=key)
    package = db_manager.get_token_package_cached(key)
    await callback.answer("Пакет включён" if enabled else "Пакет отключён", show_alert=True)
    await _edit(
        callback,
        f"<b>💎 {_safe(package['title'])}</b>\n\nКлюч: <code>{key}</code>\nТокены: <b>{package['tokens']} 💎</b>\nЦена: <b>{package['price_rub']} ₽</b>\nСтатус: <b>{'🟢 включён' if enabled else '🔴 отключён'}</b>",
        package_card_keyboard(key, enabled=enabled),
    )


@router.callback_query(F.data == "admin:payments")
async def admin_payments(callback: CallbackQuery) -> None:
    async with db_manager.connection() as conn:
        summary = await (await conn.execute(
            """SELECT status, COUNT(*) AS c, COALESCE(SUM(amount),0) AS total
               FROM payments GROUP BY status ORDER BY c DESC"""
        )).fetchall()
        rows = await (await conn.execute(
            """SELECT provider_payment_id, user_id, amount, status, created_at
               FROM payments ORDER BY id DESC LIMIT 15"""
        )).fetchall()
    status_labels = {"paid": "✅ оплачен", "pending": "⏳ ожидает", "creating": "🛠 создаётся", "cancelled": "🚫 отменён", "failed": "❌ ошибка"}
    summary_text = "\n".join(f"• {status_labels.get(row['status'], _safe(row['status']))}: <b>{row['c']}</b> · {float(row['total']):.2f} ₽" for row in summary) or "• Платежей нет"
    recent = []
    for row in rows:
        recent.append(
            f"<code>{_safe(row['provider_payment_id'])}</code> · <code>{row['user_id']}</code> · "
            f"<b>{float(row['amount']):.2f} ₽</b> · {status_labels.get(row['status'], _safe(row['status']))}"
        )
    text = "<b>💳 Платежи</b>\n\n<b>Сводка:</b>\n" + summary_text + "\n\n<b>Последние:</b>\n" + ("\n".join(recent) or "Платежей пока нет")
    await callback.answer()
    await _edit(callback, text, admin_back_keyboard())


@router.callback_query(F.data == "admin:errors")
async def admin_errors(callback: CallbackQuery) -> None:
    async with db_manager.connection() as conn:
        requests = await (await conn.execute(
            """SELECT user_id, model, tool, error_message, created_at
               FROM requests
               WHERE status!='success' OR error_message IS NOT NULL
               ORDER BY id DESC LIMIT 12"""
        )).fetchall()
        payments = await (await conn.execute(
            """SELECT user_id, provider_payment_id, amount, created_at
               FROM payments WHERE status='failed' ORDER BY id DESC LIMIT 8"""
        )).fetchall()
    lines = ["<b>⚠️ Последние ошибки</b>"]
    if requests:
        lines.append("\n<b>Генерации:</b>")
        for row in requests:
            error = str(row["error_message"] or "Неизвестная ошибка")
            if len(error) > 180:
                error = error[:177] + "…"
            lines.append(f"• <code>{row['user_id']}</code> · {_safe(row['model'] or row['tool'])}\n{_safe(error)}")
    if payments:
        lines.append("\n<b>Платежи:</b>")
        for row in payments:
            lines.append(f"• <code>{_safe(row['provider_payment_id'])}</code> · <code>{row['user_id']}</code> · {float(row['amount']):.2f} ₽")
    if not requests and not payments:
        lines.append("\nОшибок в базе пока нет.")
    await callback.answer()
    await _edit(callback, "\n".join(lines), admin_back_keyboard())


@router.callback_query(F.data == "admin:health")
async def admin_health(callback: CallbackQuery) -> None:
    checks: list[tuple[str, bool, str]] = []
    pending_jobs = 0
    try:
        async with db_manager.connection() as conn:
            await (await conn.execute("SELECT 1")).fetchone()
            pending_jobs = int((await (await conn.execute(
                """SELECT COUNT(*) AS c FROM generation_jobs
                   WHERE status IN ('processing','ready')"""
            )).fetchone())["c"])
        checks.append(("База данных", True, settings.DB_PATH))
    except Exception as exc:
        checks.append(("База данных", False, str(exc)))
    checks.extend([
        ("Telegram Bot Token", bool(settings.BOT_TOKEN), "задан" if settings.BOT_TOKEN else "не задан"),
        ("GenAPI", bool(settings.GENAPI_API_KEY), "ключ задан" if settings.GENAPI_API_KEY else "ключ не задан"),
        ("ЮKassa", bool(settings.YOOKASSA_SHOP_ID and settings.YOOKASSA_SECRET_KEY), "данные заданы" if settings.YOOKASSA_SHOP_ID and settings.YOOKASSA_SECRET_KEY else "не настроена"),
        (
            "Webhook ЮKassa",
            bool(settings.MEDIA_PUBLIC_BASE_URL),
            (
                f"{settings.MEDIA_PUBLIC_BASE_URL}{settings.YOOKASSA_WEBHOOK_PATH}"
                if settings.MEDIA_PUBLIC_BASE_URL else "нужен публичный домен"
            ),
        ),
        ("Публичный медиа-домен", bool(settings.MEDIA_PUBLIC_BASE_URL), settings.MEDIA_PUBLIC_BASE_URL or "не задан"),
    ])
    enabled_models = sum(db_manager.is_model_enabled_cached(key) for key in MODELS)
    enabled_packages = len(db_manager.get_token_packages_cached(enabled_only=True))
    latest_backup = operations_service.latest_backup()
    lines = ["<b>🩺 Состояние системы</b>", ""]
    for title, ok, detail in checks:
        lines.append(f"{'✅' if ok else '❌'} <b>{title}</b>: {_safe(detail)}")
    lines.extend([
        "",
        f"Включено моделей: <b>{enabled_models}/{len(MODELS)}</b>",
        f"Активных пакетов: <b>{enabled_packages}</b>",
        f"Генераций в обработке: <b>{pending_jobs}</b>",
        f"Последняя копия БД: <b>{_safe(latest_backup.name if latest_backup else 'ещё не создана')}</b>",
        "",
        "Проверка локальная: внешние платные запросы к GenAPI и ЮKassa не выполнялись.",
    ])
    await callback.answer()
    await _edit(callback, "\n".join(lines), admin_back_keyboard())


@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminBroadcastStates.waiting_text)
    await callback.answer()
    await _edit(callback, "<b>📣 Рассылка</b>\n\nОтправьте текст сообщения. Он будет показан как обычный безопасный текст без HTML-разметки.", admin_back_keyboard())


@router.message(AdminBroadcastStates.waiting_text, F.text)
async def admin_broadcast_preview(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if not text or len(text) > 3500:
        await message.answer("Текст должен содержать от 1 до 3500 символов.")
        return
    await state.update_data(broadcast_text=text)
    await state.set_state(AdminBroadcastStates.waiting_confirmation)
    async with db_manager.connection() as conn:
        count = int((await (await conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE COALESCE(is_blocked,0)=0"
        )).fetchone())["c"])
    await message.answer(
        f"<b>Предпросмотр рассылки</b>\n\n{_safe(text)}\n\nПолучателей: <b>{count}</b>",
        reply_markup=broadcast_preview_keyboard(),
    )


@router.callback_query(F.data == "admin:broadcast_cancel")
async def admin_broadcast_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Рассылка отменена")
    await _edit(callback, "Рассылка отменена.", admin_back_keyboard())


@router.callback_query(F.data == "admin:broadcast_confirm")
async def admin_broadcast_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    text = str(data.get("broadcast_text") or "")
    if not text:
        await callback.answer("Текст рассылки потерян", show_alert=True)
        return
    await state.clear()
    async with db_manager.connection() as conn:
        users = await (await conn.execute(
            "SELECT telegram_id FROM users WHERE COALESCE(is_blocked,0)=0 ORDER BY id"
        )).fetchall()
        cursor = await conn.execute(
            """INSERT INTO admin_broadcasts (admin_id, text, target_count, status)
               VALUES (?, ?, ?, 'sending')""",
            (callback.from_user.id, text, len(users)),
        )
        broadcast_id = int(cursor.lastrowid)
        await conn.commit()
    await callback.answer("Рассылка запущена")
    await _edit(callback, f"⏳ Рассылка запущена. Получателей: <b>{len(users)}</b>.")
    sent = 0
    failed = 0
    escaped = html.escape(text)
    for index, row in enumerate(users, start=1):
        user_id = int(row["telegram_id"])
        try:
            await bot.send_message(user_id, escaped)
            sent += 1
        except TelegramRetryAfter as exc:
            await asyncio.sleep(float(exc.retry_after))
            try:
                await bot.send_message(user_id, escaped)
                sent += 1
            except Exception:
                failed += 1
        except (TelegramForbiddenError, TelegramBadRequest):
            failed += 1
        except Exception:
            failed += 1
            logger.exception("Ошибка рассылки пользователю %s", user_id)
        if index % 25 == 0:
            await asyncio.sleep(1)
    async with db_manager.connection() as conn:
        await conn.execute(
            """UPDATE admin_broadcasts
               SET sent_count=?, failed_count=?, status='finished', finished_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (sent, failed, broadcast_id),
        )
        await conn.commit()
    await _audit(callback.from_user.id, "broadcast", details=f"id={broadcast_id}; sent={sent}; failed={failed}")
    await callback.message.answer(
        f"<b>✅ Рассылка завершена</b>\n\nОтправлено: <b>{sent}</b>\nОшибок: <b>{failed}</b>",
        reply_markup=admin_back_keyboard(),
    )


@router.callback_query(F.data == "admin:audit")
async def admin_audit(callback: CallbackQuery) -> None:
    rows = await db_manager.get_admin_audit(30)
    lines = ["<b>📜 Журнал действий</b>"]
    for row in rows:
        target = f" → <code>{row['target_user_id']}</code>" if row.get("target_user_id") else ""
        details_value = str(row.get("details") or "")
        if len(details_value) > 180:
            details_value = details_value[:177] + "…"
        details = f"\n{_safe(details_value)}" if details_value else ""
        lines.append(f"<code>{str(row['created_at'])[:16]}</code> · <code>{row['admin_id']}</code>\n<b>{_safe(row['action'])}</b>{target}{details}")
    if not rows:
        lines.append("\nЖурнал пока пуст.")
    await callback.answer()
    await _edit(callback, "\n\n".join(lines), admin_back_keyboard())
