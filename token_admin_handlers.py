"""История токенов и административное управление экономикой бота."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from database import db_manager, token_repository, user_repository
from model_catalog import MODELS, get_model
from settings import settings
from utils import logger

router = Router(name="token_admin_router")


def _is_admin(user_id: int) -> bool:
    return settings.is_admin(user_id)


def _format_transaction(item: dict) -> str:
    amount = int(item.get("amount", 0))
    sign = "+" if amount > 0 else ""
    created_at = str(item.get("created_at", ""))[:16]
    description = item.get("description") or item.get("type") or "Операция"
    return f"<code>{created_at}</code>  <b>{sign}{amount} 💎</b>\n{description}"


@router.message(Command("history"))
@router.message(F.text == "📜 История операций")
async def token_history(message: Message) -> None:
    if not message.from_user:
        return
    await user_repository.add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
    )
    rows = await token_repository.get_token_transactions(message.from_user.id, limit=15)
    if not rows:
        await message.answer("История операций пока пуста.")
        return
    text = "<b>Последние операции</b>\n\n" + "\n\n".join(_format_transaction(row) for row in rows)
    await message.answer(text)


@router.message(Command("grant"))
async def grant_tokens(message: Message, command: CommandObject) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        return
    parts = (command.args or "").split(maxsplit=2)
    if len(parts) < 2:
        await message.answer("Использование: <code>/grant TELEGRAM_ID КОЛИЧЕСТВО [причина]</code>")
        return
    try:
        target_id = int(parts[0])
        amount = int(parts[1])
    except ValueError:
        await message.answer("ID и количество должны быть целыми числами.")
        return
    if amount <= 0:
        await message.answer("Количество должно быть больше нуля.")
        return
    reason = parts[2] if len(parts) == 3 else "Начисление администратором"
    await user_repository.add_user(target_id, None, None)
    ok = await token_repository.add_tokens(target_id, amount, reason)
    if not ok:
        await message.answer("Не удалось начислить токены.")
        return
    balance = await token_repository.get_user_tokens(target_id)
    logger.info("Администратор %s начислил %s токенов пользователю %s", message.from_user.id, amount, target_id)
    await message.answer(f"Готово. Пользователю <code>{target_id}</code> начислено <b>{amount} 💎</b>. Баланс: <b>{balance} 💎</b>.")


@router.message(Command("price"))
async def set_model_price(message: Message, command: CommandObject) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        return
    parts = (command.args or "").split()
    if len(parts) != 2:
        await message.answer("Использование: <code>/price MODEL_KEY ЦЕНА_В_ТОКЕНАХ</code>")
        return
    model_key = parts[0]
    try:
        model = get_model(model_key)
        token_cost = int(parts[1])
    except ValueError as exc:
        await message.answer(str(exc))
        return
    if token_cost < 0:
        await message.answer("Цена не может быть отрицательной.")
        return
    await db_manager.set_model_price(model_key, token_cost, enabled=True)
    await message.answer(f"Цена <b>{model.title}</b> изменена на <b>{token_cost} 💎</b>.")


@router.message(Command("models"))
async def admin_models(message: Message) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        return
    lines = ["<b>Модели и базовые цены</b>"]
    for spec in MODELS.values():
        lines.append(f"<code>{spec.key}</code> — {spec.title}: {spec.token_cost} 💎")
    await message.answer("\n".join(lines))

@router.message(Command("stats"))
@router.message(F.text == "👑 Статистика")
async def admin_stats(message: Message) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        return
    async with db_manager.connection() as conn:
        total_users = int((await (await conn.execute("SELECT COUNT(*) AS c FROM users")).fetchone())["c"])
        new_today = int((await (await conn.execute("SELECT COUNT(*) AS c FROM users WHERE date(created_at)=date('now')")).fetchone())["c"])
        paid = await (await conn.execute("SELECT COUNT(*) AS c, COALESCE(SUM(amount),0) AS revenue FROM payments WHERE status='paid'")).fetchone()
        generations = int((await (await conn.execute("SELECT COUNT(*) AS c FROM token_transactions WHERE type IN ('spend','free_trial')")).fetchone())["c"])
        rows = await (await conn.execute("""
            SELECT description, COUNT(*) AS c
            FROM token_transactions
            WHERE type IN ('spend','free_trial')
            GROUP BY description ORDER BY c DESC LIMIT 10
        """)).fetchall()
    popular = "\n".join(f"• {r['description']}: <b>{r['c']}</b>" for r in rows) or "Пока нет данных"
    await message.answer(
        "<b>👑 Статистика Shtab AI</b>\n\n"
        f"Пользователей: <b>{total_users}</b>\n"
        f"Новых сегодня: <b>{new_today}</b>\n"
        f"Генераций: <b>{generations}</b>\n"
        f"Успешных оплат: <b>{int(paid['c'])}</b>\n"
        f"Выручка: <b>{float(paid['revenue']):.2f} ₽</b>\n\n"
        "<b>Популярные операции:</b>\n" + popular
    )
