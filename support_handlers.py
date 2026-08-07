"""Обращения пользователей и обработка заявок администраторами."""
from __future__ import annotations

import contextlib
import html

from aiogram import Bot, F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database import db_manager, user_repository
from settings import settings
from support_states import AdminSupportStates, SupportStates
from utils import logger

router = Router(name="support_router")
admin_router = Router(name="support_admin_router")

CATEGORIES = {
    "generation": "🎨 Проблема с генерацией",
    "payment": "💳 Оплата",
    "balance": "💎 Баланс",
    "model": "🤖 Работа модели",
    "other": "📝 Другое",
}
STATUS_LABELS = {
    "new": "🆕 новое",
    "in_progress": "🛠 в работе",
    "resolved": "✅ решено",
}


class AdminFilter(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        return bool(event.from_user and settings.is_admin(event.from_user.id))


admin_router.message.filter(AdminFilter())
admin_router.callback_query.filter(AdminFilter())


def support_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Написать о проблеме", callback_data="support:new")],
        [InlineKeyboardButton(text="📨 Мои обращения", callback_data="support:mine")],
    ])


def category_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=title, callback_data=f"support:category:{key}")]
        for key, title in CATEGORIES.items()
    ]
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="support:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def attachment_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Отправить без вложения", callback_data="support:skip")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="support:cancel")],
    ])


def admin_ticket_keyboard(ticket_id: int, status: str, has_attachment: bool) -> InlineKeyboardMarkup:
    rows = []
    if has_attachment:
        rows.append([InlineKeyboardButton(text="📎 Показать вложение", callback_data=f"admin:ticket_file:{ticket_id}")])
    if status == "new":
        rows.append([InlineKeyboardButton(text="🙋 Взять в работу", callback_data=f"admin:ticket_take:{ticket_id}")])
    if status != "resolved":
        rows.append([InlineKeyboardButton(text="💬 Ответить", callback_data=f"admin:ticket_reply:{ticket_id}")])
        rows.append([InlineKeyboardButton(text="✅ Отметить решённым", callback_data=f"admin:ticket_resolve:{ticket_id}")])
    rows.append([InlineKeyboardButton(text="⬅️ К обращениям", callback_data="admin:tickets")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_ticket_list_keyboard(rows: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for row in rows:
        icon = "🆕" if row["status"] == "new" else "🛠" if row["status"] == "in_progress" else "✅"
        buttons.append([
            InlineKeyboardButton(
                text=f"{icon} {row['public_id']} · {row['user_id']}",
                callback_data=f"admin:ticket:{row['id']}",
            )
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ В админ-панель", callback_data="admin:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def _support_home(message: Message) -> None:
    await message.answer(
        "<b>🆘 Поддержка</b>\n\n"
        "Если возникла проблема, напишите, что произошло. Наша команда "
        "обязательно проверит обращение и поможет решить проблему.",
        reply_markup=support_menu_keyboard(),
    )


@router.message(Command("support"))
@router.message(F.text == "🆘 Поддержка")
async def support_home(message: Message, state: FSMContext) -> None:
    await state.clear()
    await user_repository.add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
    )
    await _support_home(message)


@router.callback_query(F.data == "support:new")
async def support_new(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await callback.message.answer(
        "Выберите тему обращения:",
        reply_markup=category_keyboard(),
    )


@router.callback_query(F.data.startswith("support:category:"))
async def support_category(callback: CallbackQuery, state: FSMContext) -> None:
    category = callback.data.rsplit(":", 1)[1]
    if category not in CATEGORIES:
        await callback.answer("Некорректная тема", show_alert=True)
        return
    await state.set_state(SupportStates.waiting_description)
    await state.update_data(support_category=category)
    await callback.answer()
    await callback.message.answer(
        "Опишите, что произошло: что вы делали, какую модель выбрали и какой "
        "результат получили. Не отправляйте пароли, данные карты и API-ключи."
    )


@router.message(SupportStates.waiting_description, F.text)
async def support_description(message: Message, state: FSMContext) -> None:
    description = (message.text or "").strip()
    if not 10 <= len(description) <= 4000:
        await message.answer("Описание должно содержать от 10 до 4000 символов.")
        return
    await state.update_data(support_description=description)
    await state.set_state(SupportStates.waiting_attachment)
    await message.answer(
        "При необходимости отправьте один скриншот или документ. "
        "На нём не должно быть паролей и платёжных данных.",
        reply_markup=attachment_keyboard(),
    )


async def _create_ticket(
    message: Message,
    state: FSMContext,
    bot: Bot,
    *,
    user_id: int | None = None,
    file_id: str | None = None,
    attachment_type: str | None = None,
) -> None:
    owner_id = int(user_id or message.chat.id)
    allowed, retry_after = await db_manager.check_rate_limit(
        owner_id,
        "support_tickets",
        limit=3,
        window_seconds=3600,
    )
    if not allowed:
        await state.clear()
        await message.answer(
            f"Слишком много обращений. Новое можно создать через {retry_after // 60 + 1} мин."
        )
        return
    data = await state.get_data()
    ticket = await db_manager.create_support_ticket(
        user_id=owner_id,
        category=str(data.get("support_category") or "other"),
        description=str(data.get("support_description") or ""),
        attachment_file_id=file_id,
        attachment_type=attachment_type,
    )
    await state.clear()
    await message.answer(
        f"✅ Обращение <code>{ticket['public_id']}</code> принято.\n\n"
        "Наша команда обязательно проверит, что произошло, и поможет решить проблему. "
        "Ответ придёт прямо в этот чат."
    )
    admin_text = (
        f"<b>🆕 Новое обращение {ticket['public_id']}</b>\n"
        f"Пользователь: <code>{ticket['user_id']}</code>\n"
        f"Тема: <b>{html.escape(CATEGORIES.get(ticket['category'], ticket['category']))}</b>\n\n"
        f"{html.escape(ticket['description'][:1500])}"
    )
    for admin_id in settings.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                admin_text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="Открыть обращение", callback_data=f"admin:ticket:{ticket['id']}")
                ]]),
            )
        except Exception:
            logger.exception("Не удалось уведомить администратора %s", admin_id)


@router.callback_query(SupportStates.waiting_attachment, F.data == "support:skip")
async def support_skip(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await callback.answer()
    await _create_ticket(callback.message, state, bot, user_id=callback.from_user.id)


@router.message(SupportStates.waiting_attachment, F.photo)
async def support_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    await _create_ticket(
        message,
        state,
        bot,
        user_id=message.from_user.id,
        file_id=message.photo[-1].file_id,
        attachment_type="photo",
    )


@router.message(SupportStates.waiting_attachment, F.document)
async def support_document(message: Message, state: FSMContext, bot: Bot) -> None:
    await _create_ticket(
        message,
        state,
        bot,
        user_id=message.from_user.id,
        file_id=message.document.file_id,
        attachment_type="document",
    )


@router.message(SupportStates.waiting_attachment)
async def support_attachment_required(message: Message) -> None:
    await message.answer("Отправьте фото или документ либо нажмите «Отправить без вложения».")


@router.callback_query(F.data == "support:cancel")
async def support_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Отменено")
    await callback.message.answer("Создание обращения отменено.")


@router.callback_query(F.data == "support:mine")
async def support_mine(callback: CallbackQuery) -> None:
    rows = await db_manager.list_support_tickets(user_id=callback.from_user.id, limit=10)
    if not rows:
        await callback.answer("Обращений пока нет", show_alert=True)
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{STATUS_LABELS.get(row['status'], row['status'])} · {row['public_id']}",
            callback_data=f"support:view:{row['id']}",
        )]
        for row in rows
    ])
    await callback.answer()
    await callback.message.answer("<b>📨 Мои обращения</b>", reply_markup=keyboard)


@router.callback_query(F.data.startswith("support:view:"))
async def support_view(callback: CallbackQuery) -> None:
    ticket_id = int(callback.data.rsplit(":", 1)[1])
    ticket = await db_manager.get_support_ticket(ticket_id)
    if not ticket or int(ticket["user_id"]) != callback.from_user.id:
        await callback.answer("Обращение не найдено", show_alert=True)
        return
    messages = await db_manager.list_support_messages(ticket_id, 10)
    lines = [
        f"<b>{ticket['public_id']}</b> · {STATUS_LABELS.get(ticket['status'], ticket['status'])}",
        f"Тема: {html.escape(CATEGORIES.get(ticket['category'], ticket['category']))}",
    ]
    for item in messages:
        author = "Вы" if item["sender_type"] == "user" else "Команда"
        lines.append(f"\n<b>{author}:</b> {html.escape(str(item['message'])[:1200])}")
    await callback.answer()
    await callback.message.answer("\n".join(lines))


@admin_router.callback_query(F.data == "admin:tickets")
async def admin_tickets(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    rows = await db_manager.list_support_tickets(limit=30)
    await callback.answer()
    await callback.message.edit_text(
        "<b>🆘 Обращения пользователей</b>\n\n"
        + ("Выберите обращение:" if rows else "Обращений пока нет."),
        reply_markup=admin_ticket_list_keyboard(rows),
    )


async def _show_admin_ticket(callback: CallbackQuery, ticket_id: int) -> None:
    ticket = await db_manager.get_support_ticket(ticket_id)
    if not ticket:
        await callback.answer("Обращение не найдено", show_alert=True)
        return
    messages = await db_manager.list_support_messages(ticket_id, 8)
    lines = [
        f"<b>🆘 {ticket['public_id']}</b>",
        f"Пользователь: <code>{ticket['user_id']}</code>",
        f"Статус: <b>{STATUS_LABELS.get(ticket['status'], ticket['status'])}</b>",
        f"Тема: {html.escape(CATEGORIES.get(ticket['category'], ticket['category']))}",
    ]
    for item in messages:
        author = "Пользователь" if item["sender_type"] == "user" else "Администратор"
        lines.append(f"\n<b>{author}:</b> {html.escape(str(item['message'])[:1000])}")
    await callback.answer()
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=admin_ticket_keyboard(
            ticket_id,
            str(ticket["status"]),
            bool(ticket.get("attachment_file_id")),
        ),
    )


@admin_router.callback_query(F.data.startswith("admin:ticket:"))
async def admin_ticket_card(callback: CallbackQuery) -> None:
    await _show_admin_ticket(callback, int(callback.data.rsplit(":", 1)[1]))


@admin_router.callback_query(F.data.startswith("admin:ticket_take:"))
async def admin_ticket_take(callback: CallbackQuery) -> None:
    ticket_id = int(callback.data.rsplit(":", 1)[1])
    await db_manager.update_support_ticket(ticket_id, status="in_progress", admin_id=callback.from_user.id)
    await _show_admin_ticket(callback, ticket_id)


@admin_router.callback_query(F.data.startswith("admin:ticket_reply:"))
async def admin_ticket_reply_start(callback: CallbackQuery, state: FSMContext) -> None:
    ticket_id = int(callback.data.rsplit(":", 1)[1])
    ticket = await db_manager.get_support_ticket(ticket_id)
    if not ticket:
        await callback.answer("Обращение не найдено", show_alert=True)
        return
    await state.set_state(AdminSupportStates.waiting_reply)
    await state.update_data(support_ticket_id=ticket_id)
    await callback.answer()
    await callback.message.answer("Введите ответ пользователю. Не передавайте пароли и секретные ключи.")


@admin_router.message(AdminSupportStates.waiting_reply, F.text)
async def admin_ticket_reply_send(message: Message, state: FSMContext, bot: Bot) -> None:
    reply = (message.text or "").strip()
    if not 2 <= len(reply) <= 4000:
        await message.answer("Ответ должен содержать от 2 до 4000 символов.")
        return
    data = await state.get_data()
    ticket_id = int(data.get("support_ticket_id") or 0)
    ticket = await db_manager.get_support_ticket(ticket_id)
    if not ticket:
        await state.clear()
        await message.answer("Обращение не найдено.")
        return
    await db_manager.add_support_message(
        ticket_id,
        sender_type="admin",
        sender_id=message.from_user.id,
        message=reply,
    )
    await db_manager.update_support_ticket(ticket_id, status="in_progress", admin_id=message.from_user.id)
    await state.clear()
    try:
        await bot.send_message(
            int(ticket["user_id"]),
            f"<b>💬 Ответ по обращению {ticket['public_id']}</b>\n\n{html.escape(reply)}",
        )
    except Exception:
        logger.exception("Не удалось доставить ответ по обращению %s", ticket["public_id"])
        await message.answer(
            "⚠️ Ответ сохранён, но Telegram не доставил сообщение пользователю."
        )
        return
    await message.answer("✅ Ответ отправлен пользователю.")


@admin_router.callback_query(F.data.startswith("admin:ticket_resolve:"))
async def admin_ticket_resolve(callback: CallbackQuery, bot: Bot) -> None:
    ticket_id = int(callback.data.rsplit(":", 1)[1])
    ticket = await db_manager.get_support_ticket(ticket_id)
    if not ticket:
        await callback.answer("Обращение не найдено", show_alert=True)
        return
    await db_manager.update_support_ticket(ticket_id, status="resolved", admin_id=callback.from_user.id)
    with contextlib.suppress(Exception):
        await bot.send_message(
            int(ticket["user_id"]),
            f"✅ Обращение <code>{ticket['public_id']}</code> отмечено решённым. "
            "Если проблема осталась, создайте новое обращение в разделе поддержки.",
        )
    await _show_admin_ticket(callback, ticket_id)


@admin_router.callback_query(F.data.startswith("admin:ticket_file:"))
async def admin_ticket_file(callback: CallbackQuery, bot: Bot) -> None:
    ticket_id = int(callback.data.rsplit(":", 1)[1])
    ticket = await db_manager.get_support_ticket(ticket_id)
    if not ticket or not ticket.get("attachment_file_id"):
        await callback.answer("Вложения нет", show_alert=True)
        return
    await callback.answer()
    if ticket.get("attachment_type") == "photo":
        await bot.send_photo(callback.message.chat.id, ticket["attachment_file_id"])
    else:
        await bot.send_document(callback.message.chat.id, ticket["attachment_file_id"])
