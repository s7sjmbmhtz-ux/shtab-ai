"""Покупка токенов и управление платёжными заказами."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from generation_keyboards import get_token_packages_keyboard
from model_catalog import TOKEN_PACKAGES
from services.payment_service import PaymentError, payment_service
from settings import settings

router = Router(name="payment_router")


def _is_admin(user_id: int) -> bool:
    return user_id == settings.ADMIN_TELEGRAM_ID


@router.callback_query(F.data.startswith("buytokens:"))
async def create_payment_order(callback: CallbackQuery) -> None:
    if not callback.from_user:
        return
    package_key = callback.data.split(":", 1)[1]
    package = TOKEN_PACKAGES.get(package_key)
    if not package:
        await callback.answer("Пакет не найден", show_alert=True)
        return
    try:
        order = await payment_service.create_order(callback.from_user.id, package_key)
    except PaymentError as exc:
        await callback.answer(str(exc), show_alert=True)
        return

    await callback.answer()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить заказ", callback_data=f"cancelorder:{order.public_id}")],
            [InlineKeyboardButton(text="⬅️ Другой пакет", callback_data="payment:packages")],
        ]
    )
    await callback.message.answer(
        "<b>Заказ создан</b>\n\n"
        f"Номер: <code>{order.public_id}</code>\n"
        f"Пакет: <b>{package['title']}</b>\n"
        f"Начисление: <b>{order.tokens} 💎</b>\n"
        f"Сумма: <b>{order.amount_rub} ₽</b>\n\n"
        "Сейчас включён ручной режим подтверждения. После выбора платёжного провайдера "
        "здесь появится кнопка автоматической оплаты.",
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "payment:packages")
async def return_to_packages(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer("Выберите пакет токенов:", reply_markup=get_token_packages_keyboard())


@router.callback_query(F.data.startswith("cancelorder:"))
async def cancel_order(callback: CallbackQuery) -> None:
    public_id = callback.data.split(":", 1)[1]
    cancelled = await payment_service.cancel_order(public_id, callback.from_user.id)
    await callback.answer("Заказ отменён" if cancelled else "Заказ уже обработан", show_alert=not cancelled)
    if cancelled:
        await callback.message.edit_text(f"Заказ <code>{public_id}</code> отменён.")


@router.message(Command("orders"))
async def list_orders(message: Message) -> None:
    if not message.from_user:
        return
    orders = await payment_service.get_user_orders(message.from_user.id)
    if not orders:
        await message.answer("У вас пока нет заказов.")
        return
    labels = {"pending": "ожидает", "paid": "оплачен", "cancelled": "отменён", "failed": "ошибка"}
    lines = ["<b>Последние заказы</b>"]
    for order in orders:
        status = labels.get(order.status, order.status)
        lines.append(
            f"<code>{order.public_id}</code> — {order.tokens} 💎 / {order.amount_rub} ₽ — <b>{status}</b>"
        )
    await message.answer("\n".join(lines))


@router.message(Command("confirm_payment"))
async def confirm_manual_payment(message: Message, command: CommandObject) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        return
    public_id = (command.args or "").strip().upper()
    if not public_id:
        await message.answer("Использование: <code>/confirm_payment НОМЕР_ЗАКАЗА</code>")
        return
    try:
        order = await payment_service.confirm_order(public_id)
    except PaymentError as exc:
        await message.answer(f"Ошибка: {exc}")
        return
    await message.answer(
        f"Заказ <code>{order.public_id}</code> подтверждён. "
        f"Пользователю <code>{order.user_id}</code> начислено <b>{order.tokens} 💎</b>."
    )
