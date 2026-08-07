"""Оплата внутренних токенов через ЮKassa."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database import db_manager
from generation_keyboards import get_token_packages_keyboard
from services.payment_service import PaymentError, payment_service
from services.funnel_service import funnel_service
from settings import settings

router = Router(name="payment_router")


def _payment_keyboard(public_id: str, url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить в ЮKassa", url=url)],
        [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"checkpay:{public_id}")],
    ])


@router.callback_query(F.data.startswith("buytokens:"))
async def create_payment_order(callback: CallbackQuery) -> None:
    package_key = callback.data.split(":", 1)[1]
    package = db_manager.get_token_package_cached(package_key)
    if (
        not package
        or not bool(package.get("enabled"))
        or not db_manager.is_token_package_safe(package)
    ):
        await callback.answer("Пакет не найден или временно отключён", show_alert=True); return
    try:
        order = await payment_service.create_order(callback.from_user.id, package_key)
    except PaymentError as exc:
        await callback.answer(str(exc), show_alert=True); return
    await callback.answer()
    await callback.message.answer(
        "<b>Заказ создан</b>\n\n"
        f"Номер: <code>{order.public_id}</code>\n"
        f"Пакет: <b>{package['title']}</b>\n"
        f"Начисление: <b>{order.tokens} 💎</b>\n"
        f"Сумма: <b>{order.amount_rub} ₽</b>\n\n"
        "Нажмите «Оплатить», завершите платёж и затем нажмите «Проверить оплату».",
        reply_markup=_payment_keyboard(order.public_id, order.confirmation_url or settings.YOOKASSA_RETURN_URL),
    )


@router.callback_query(F.data.startswith("checkpay:"))
async def check_payment(callback: CallbackQuery) -> None:
    public_id = callback.data.split(":", 1)[1]
    try:
        order = await payment_service.check_and_credit(public_id, callback.from_user.id)
    except PaymentError as exc:
        await callback.answer(str(exc), show_alert=True); return
    await callback.answer("Оплата подтверждена")
    await callback.message.edit_text(
        f"✅ Оплата подтверждена. На баланс начислено <b>{order.tokens} 💎</b>.\n"
        f"Заказ: <code>{order.public_id}</code>"
    )


@router.callback_query(F.data == "payment:packages")
async def return_to_packages(callback: CallbackQuery) -> None:
    await funnel_service.track(callback.from_user.id, "packages_open")
    await callback.answer()
    await callback.message.answer("Выберите пакет токенов:", reply_markup=get_token_packages_keyboard())


@router.callback_query(F.data.startswith("cancelorder:"))
async def cancel_order(callback: CallbackQuery) -> None:
    """Обрабатывает старые кнопки без локальной отмены платежа.

    Локальная отмена опасна: пользователь мог уже завершить оплату в ЮKassa.
    Поэтому сначала сверяем статус, а незавершённый заказ просто оставляем как есть.
    """
    public_id = callback.data.split(":", 1)[1]
    try:
        order = await payment_service.check_and_credit(
            public_id,
            callback.from_user.id,
        )
    except PaymentError as exc:
        text = str(exc)
        if "пока не подтверждена" in text.lower():
            text = "Чтобы отказаться от заказа, просто не оплачивайте его — деньги не спишутся."
        await callback.answer(text, show_alert=True)
        return

    await callback.answer("Оплата уже подтверждена", show_alert=True)
    await callback.message.edit_text(
        f"✅ Оплата подтверждена. Начислено <b>{order.tokens} 💎</b>.\n"
        f"Заказ: <code>{order.public_id}</code>"
    )


@router.message(Command("orders"))
async def list_orders(message: Message) -> None:
    orders = await payment_service.get_user_orders(message.from_user.id)
    if not orders:
        await message.answer("У вас пока нет заказов."); return
    labels = {"creating":"создаётся", "pending":"ожидает оплаты", "paid":"оплачен", "cancelled":"отменён", "failed":"ошибка"}
    lines = ["<b>Последние заказы</b>"]
    for order in orders:
        lines.append(f"<code>{order.public_id}</code> — {order.tokens} 💎 / {order.amount_rub} ₽ — <b>{labels.get(order.status, order.status)}</b>")
    await message.answer("\n".join(lines))


@router.message(Command("confirm_payment"))
async def emergency_confirm(message: Message, command: CommandObject) -> None:
    if not settings.is_admin(message.from_user.id):
        return
    public_id = (command.args or "").strip().upper()
    if not public_id:
        await message.answer("Использование: <code>/confirm_payment НОМЕР_ЗАКАЗА</code>"); return
    try:
        existing = await payment_service.get_order(public_id)
        if not existing:
            raise PaymentError("Заказ не найден")
        order = await payment_service.check_and_credit(public_id, existing.user_id)
    except PaymentError as exc:
        await message.answer(f"Ошибка: {exc}"); return
    await message.answer(
        f"Заказ <code>{order.public_id}</code> проверен через ЮKassa, "
        f"начислено {order.tokens} 💎."
    )
