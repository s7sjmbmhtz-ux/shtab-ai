"""Платёжные заказы и безопасное начисление внутренних токенов."""
from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from typing import Any

from database import db_manager, token_repository, user_repository
from model_catalog import TOKEN_PACKAGES


class PaymentError(RuntimeError):
    """Ошибка платёжного сценария."""


@dataclass(frozen=True, slots=True)
class PaymentOrder:
    id: int
    public_id: str
    user_id: int
    package_key: str
    tokens: int
    amount_rub: int
    status: str
    provider: str


class PaymentService:
    """Создаёт заказы и гарантирует однократное начисление токенов."""

    async def create_order(self, user_id: int, package_key: str) -> PaymentOrder:
        package = TOKEN_PACKAGES.get(package_key)
        if not package:
            raise PaymentError("Пакет токенов не найден")

        await user_repository.add_user(user_id, None, None)
        public_id = secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:12].upper()
        metadata = {
            "public_id": public_id,
            "package_key": package_key,
            "tokens": int(package["tokens"]),
        }
        async with db_manager.connection() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO payments (
                    user_id, provider, provider_payment_id, tariff,
                    amount, currency, status, metadata
                ) VALUES (?, 'manual', ?, ?, ?, 'RUB', 'pending', ?)
                """,
                (
                    user_id,
                    public_id,
                    package_key,
                    int(package["price_rub"]),
                    json.dumps(metadata, ensure_ascii=False),
                ),
            )
            await conn.commit()
            order_id = int(cursor.lastrowid)

        return PaymentOrder(
            id=order_id,
            public_id=public_id,
            user_id=user_id,
            package_key=package_key,
            tokens=int(package["tokens"]),
            amount_rub=int(package["price_rub"]),
            status="pending",
            provider="manual",
        )

    async def get_order(self, public_id: str) -> PaymentOrder | None:
        async with db_manager.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM payments WHERE provider_payment_id = ?",
                (public_id,),
            )
            row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_order(dict(row))

    async def get_user_orders(self, user_id: int, limit: int = 10) -> list[PaymentOrder]:
        async with db_manager.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT * FROM payments
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, limit),
            )
            rows = await cursor.fetchall()
        return [self._row_to_order(dict(row)) for row in rows]

    async def confirm_order(self, public_id: str, *, provider_payment_id: str | None = None) -> PaymentOrder:
        """Подтверждает заказ ровно один раз и начисляет купленные токены."""
        async with db_manager.connection() as conn:
            await conn.execute("BEGIN IMMEDIATE")
            cursor = await conn.execute(
                "SELECT * FROM payments WHERE provider_payment_id = ?",
                (public_id,),
            )
            row = await cursor.fetchone()
            if not row:
                await conn.rollback()
                raise PaymentError("Заказ не найден")
            data = dict(row)
            if data["status"] == "paid":
                await conn.commit()
                return self._row_to_order(data)
            if data["status"] not in {"pending", "processing"}:
                await conn.rollback()
                raise PaymentError(f"Заказ нельзя подтвердить: статус {data['status']}")

            metadata = self._metadata(data)
            tokens = int(metadata.get("tokens", 0))
            if tokens <= 0:
                await conn.rollback()
                raise PaymentError("В заказе отсутствует количество токенов")

            update = await conn.execute(
                """
                UPDATE payments
                SET status = 'paid', paid_at = CURRENT_TIMESTAMP,
                    metadata = ?
                WHERE id = ? AND status IN ('pending', 'processing')
                """,
                (
                    json.dumps({**metadata, "external_payment_id": provider_payment_id}, ensure_ascii=False),
                    data["id"],
                ),
            )
            if update.rowcount != 1:
                await conn.rollback()
                raise PaymentError("Заказ уже обрабатывается")

            await conn.execute(
                "UPDATE users SET tokens = tokens + ? WHERE telegram_id = ?",
                (tokens, data["user_id"]),
            )
            await conn.execute(
                """
                INSERT INTO token_transactions (user_id, amount, type, description, package)
                VALUES (?, ?, 'purchase', ?, ?)
                """,
                (
                    data["user_id"],
                    tokens,
                    f"Оплата заказа {public_id}",
                    metadata.get("package_key"),
                ),
            )
            await conn.commit()

        confirmed = await self.get_order(public_id)
        if not confirmed:
            raise PaymentError("Не удалось получить подтверждённый заказ")
        return confirmed

    async def cancel_order(self, public_id: str, user_id: int) -> bool:
        async with db_manager.connection() as conn:
            cursor = await conn.execute(
                """
                UPDATE payments SET status = 'cancelled'
                WHERE provider_payment_id = ? AND user_id = ? AND status = 'pending'
                """,
                (public_id, user_id),
            )
            await conn.commit()
            return cursor.rowcount == 1

    @staticmethod
    def _metadata(row: dict[str, Any]) -> dict[str, Any]:
        raw = row.get("metadata")
        if not raw:
            return {}
        try:
            value = json.loads(raw)
            return value if isinstance(value, dict) else {}
        except (TypeError, json.JSONDecodeError):
            return {}

    def _row_to_order(self, row: dict[str, Any]) -> PaymentOrder:
        metadata = self._metadata(row)
        package_key = str(metadata.get("package_key") or row.get("tariff") or "")
        package = TOKEN_PACKAGES.get(package_key, {})
        return PaymentOrder(
            id=int(row["id"]),
            public_id=str(row.get("provider_payment_id") or ""),
            user_id=int(row["user_id"]),
            package_key=package_key,
            tokens=int(metadata.get("tokens") or package.get("tokens") or 0),
            amount_rub=int(float(row.get("amount") or 0)),
            status=str(row.get("status") or "pending"),
            provider=str(row.get("provider") or "manual"),
        )


payment_service = PaymentService()
