"""ЮKassa: создание, проверка и однократное зачисление токенов."""
from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from database import db_manager, user_repository
from model_catalog import TOKEN_PACKAGES
from settings import settings
from utils import logger


class PaymentError(RuntimeError):
    pass


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
    confirmation_url: str | None = None
    external_payment_id: str | None = None


class PaymentService:
    def _ensure_configured(self) -> None:
        if not settings.YOOKASSA_SHOP_ID or not settings.YOOKASSA_SECRET_KEY:
            raise PaymentError("ЮKassa не настроена: проверьте YOOKASSA_SHOP_ID и YOOKASSA_SECRET_KEY")

    async def _request(self, method: str, path: str, *, json_data: dict[str, Any] | None = None,
                       idempotence_key: str | None = None) -> dict[str, Any]:
        self._ensure_configured()
        headers = {"Accept": "application/json"}
        if idempotence_key:
            headers["Idempotence-Key"] = idempotence_key
        try:
            async with httpx.AsyncClient(
                base_url=settings.YOOKASSA_API_URL,
                auth=(settings.YOOKASSA_SHOP_ID, settings.YOOKASSA_SECRET_KEY),
                timeout=httpx.Timeout(30.0),
            ) as client:
                response = await client.request(method, path, json=json_data, headers=headers)
        except httpx.HTTPError as exc:
            raise PaymentError(f"ЮKassa недоступна: {exc}") from exc
        try:
            data = response.json()
        except ValueError as exc:
            raise PaymentError(f"ЮKassa вернула некорректный ответ ({response.status_code})") from exc
        if response.status_code >= 400:
            description = data.get("description") or data.get("code") or str(data)
            raise PaymentError(f"Ошибка ЮKassa: {description}")
        if not isinstance(data, dict):
            raise PaymentError("Некорректный формат ответа ЮKassa")
        return data

    async def create_order(self, user_id: int, package_key: str) -> PaymentOrder:
        package = db_manager.get_token_package_cached(package_key)
        if not package:
            raise PaymentError("Пакет токенов не найден")
        if not bool(package.get("enabled")):
            raise PaymentError("Этот пакет временно отключён")
        if not db_manager.is_token_package_safe(package):
            raise PaymentError("Пакет временно недоступен: цена ниже защитного порога")
        self._ensure_configured()
        await user_repository.add_user(user_id, None, None)
        public_id = secrets.token_hex(6).upper()
        tokens = int(package["tokens"])
        amount = int(package["price_rub"])
        metadata = {"public_id": public_id, "package_key": package_key, "tokens": tokens}

        async with db_manager.connection() as conn:
            cursor = await conn.execute(
                """INSERT INTO payments
                   (user_id, provider, provider_payment_id, tariff, amount, currency, status, metadata)
                   VALUES (?, 'yookassa', ?, ?, ?, 'RUB', 'creating', ?)""",
                (user_id, public_id, package_key, amount, json.dumps(metadata, ensure_ascii=False)),
            )
            await conn.commit()
            order_id = int(cursor.lastrowid)

        body = {
            "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
            "capture": True,
            "confirmation": {"type": "redirect", "return_url": settings.YOOKASSA_RETURN_URL},
            "description": f"Shtab AI: {tokens} токенов, заказ {public_id}",
            "metadata": {"public_id": public_id, "user_id": str(user_id), "package_key": package_key},
        }
        try:
            payment = await self._request("POST", "/payments", json_data=body, idempotence_key=public_id)
            external_id = str(payment.get("id") or "")
            confirmation_url = (payment.get("confirmation") or {}).get("confirmation_url")
            if not external_id or not confirmation_url:
                raise PaymentError("ЮKassa не вернула ссылку на оплату")
            metadata.update({"external_payment_id": external_id, "confirmation_url": confirmation_url})
            async with db_manager.connection() as conn:
                await conn.execute(
                    "UPDATE payments SET status='pending', metadata=? WHERE id=?",
                    (json.dumps(metadata, ensure_ascii=False), order_id),
                )
                await conn.commit()
        except Exception:
            async with db_manager.connection() as conn:
                await conn.execute("UPDATE payments SET status='failed' WHERE id=?", (order_id,))
                await conn.commit()
            raise
        return await self._get_by_id(order_id)

    async def _get_by_id(self, order_id: int) -> PaymentOrder:
        async with db_manager.connection() as conn:
            row = await (await conn.execute("SELECT * FROM payments WHERE id=?", (order_id,))).fetchone()
        if not row:
            raise PaymentError("Заказ не найден")
        return self._row_to_order(dict(row))

    async def get_order(self, public_id: str) -> PaymentOrder | None:
        async with db_manager.connection() as conn:
            row = await (await conn.execute(
                "SELECT * FROM payments WHERE provider_payment_id=?", (public_id.upper(),)
            )).fetchone()
        return self._row_to_order(dict(row)) if row else None

    async def get_order_by_external_id(
        self,
        external_payment_id: str,
    ) -> PaymentOrder | None:
        async with db_manager.connection() as conn:
            row = await (await conn.execute(
                """SELECT * FROM payments
                   WHERE json_extract(metadata, '$.external_payment_id')=?
                   ORDER BY id DESC LIMIT 1""",
                (external_payment_id,),
            )).fetchone()
        return self._row_to_order(dict(row)) if row else None

    async def get_user_orders(self, user_id: int, limit: int = 10) -> list[PaymentOrder]:
        async with db_manager.connection() as conn:
            rows = await (await conn.execute(
                "SELECT * FROM payments WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit)
            )).fetchall()
        return [self._row_to_order(dict(row)) for row in rows]

    async def check_and_credit(self, public_id: str, user_id: int) -> PaymentOrder:
        order = await self.get_order(public_id)
        if not order or order.user_id != user_id:
            raise PaymentError("Заказ не найден")
        if order.status == "paid":
            return order
        if not order.external_payment_id:
            raise PaymentError("У заказа отсутствует ID ЮKassa")
        payment = await self._request("GET", f"/payments/{order.external_payment_id}")
        status = str(payment.get("status") or "")
        if status == "succeeded" and bool(payment.get("paid")):
            self._verify_payment(order, payment)
            confirmed, _ = await self._credit_verified_order_once(public_id)
            return confirmed
        if status == "canceled":
            async with db_manager.connection() as conn:
                await conn.execute(
                    "UPDATE payments SET status='failed' WHERE provider_payment_id=? AND status!='paid'",
                    (public_id.upper(),),
                )
                await conn.commit()
            raise PaymentError("Платёж отменён")
        raise PaymentError("Оплата пока не подтверждена. Завершите платёж и проверьте снова")

    def _verify_payment(self, order: PaymentOrder, payment: dict[str, Any]) -> None:
        if str(payment.get("id") or "") != str(order.external_payment_id or ""):
            raise PaymentError("ID платежа ЮKassa не совпадает с заказом")
        amount = payment.get("amount") or {}
        try:
            actual = Decimal(str(amount.get("value")))
        except (InvalidOperation, TypeError) as exc:
            raise PaymentError("ЮKassa вернула некорректную сумму") from exc
        if amount.get("currency") != "RUB" or actual != Decimal(order.amount_rub):
            raise PaymentError("Сумма или валюта платежа не совпадает с заказом")
        metadata = payment.get("metadata") or {}
        if str(metadata.get("public_id") or "").upper() != order.public_id.upper():
            raise PaymentError("Метаданные платежа не совпадают с заказом")
        if str(metadata.get("user_id") or "") != str(order.user_id):
            raise PaymentError("Пользователь платежа не совпадает с заказом")
        if str(metadata.get("package_key") or "") != order.package_key:
            raise PaymentError("Пакет платежа не совпадает с заказом")

    async def _credit_verified_order_once(
        self,
        public_id: str,
    ) -> tuple[PaymentOrder, bool]:
        """Однократно начисляет токены после проверки объекта через ЮKassa."""
        credited_now = False
        async with db_manager.connection() as conn:
            await conn.execute("BEGIN IMMEDIATE")
            row = await (await conn.execute(
                "SELECT * FROM payments WHERE provider_payment_id=?", (public_id.upper(),)
            )).fetchone()
            if not row:
                await conn.rollback(); raise PaymentError("Заказ не найден")
            data = dict(row)
            if data["status"] == "paid":
                await conn.commit()
                return self._row_to_order(data), False
            metadata = self._metadata(data)
            tokens = int(metadata.get("tokens", 0))
            if tokens <= 0:
                await conn.rollback()
                raise PaymentError("В заказе указано некорректное количество токенов")
            update = await conn.execute(
                "UPDATE payments SET status='paid', paid_at=CURRENT_TIMESTAMP WHERE id=? AND status!='paid'",
                (data["id"],),
            )
            if update.rowcount != 1:
                await conn.rollback(); raise PaymentError("Заказ уже обрабатывается")
            credited_now = True
            await conn.execute("UPDATE users SET tokens=tokens+? WHERE telegram_id=?", (tokens, data["user_id"]))
            await conn.execute(
                """INSERT INTO token_transactions (user_id, amount, type, description, package)
                   VALUES (?, ?, 'purchase', ?, ?)""",
                (data["user_id"], tokens, f"ЮKassa, заказ {public_id}", metadata.get("package_key")),
            )
            await conn.commit()
        confirmed = await self.get_order(public_id)
        if not confirmed:
            raise PaymentError("Не удалось получить оплаченный заказ")
        return confirmed, credited_now

    async def process_webhook(
        self,
        payload: dict[str, Any],
    ) -> tuple[PaymentOrder | None, bool]:
        """Проверяет уведомление повторным GET к ЮKassa и безопасно зачисляет."""
        event = str(payload.get("event") or "")
        if event not in {"payment.succeeded", "payment.canceled"}:
            return None, False
        obj = payload.get("object")
        if not isinstance(obj, dict):
            raise PaymentError("В webhook отсутствует объект платежа")
        external_id = str(obj.get("id") or "")
        if not external_id:
            raise PaymentError("В webhook отсутствует ID платежа")

        order = await self.get_order_by_external_id(external_id)
        if order is None:
            # У магазина могут быть платежи из других проектов.
            return None, False

        payment = await self._request("GET", f"/payments/{external_id}")
        status = str(payment.get("status") or "")
        if status == "succeeded" and bool(payment.get("paid")):
            self._verify_payment(order, payment)
            return await self._credit_verified_order_once(order.public_id)
        if status == "canceled":
            async with db_manager.connection() as conn:
                await conn.execute(
                    """UPDATE payments SET status='failed'
                       WHERE provider_payment_id=? AND status!='paid'""",
                    (order.public_id.upper(),),
                )
                await conn.commit()
            return await self.get_order(order.public_id), False
        raise PaymentError("Статус платежа ещё не финальный")

    async def get_pending_orders(self, limit: int = 25) -> list[PaymentOrder]:
        async with db_manager.connection() as conn:
            rows = await (await conn.execute(
                """SELECT * FROM payments
                   WHERE status IN ('pending','processing')
                     AND created_at >= datetime('now', '-2 days')
                   ORDER BY id DESC LIMIT ?""",
                (max(1, min(100, int(limit))),),
            )).fetchall()
        return [self._row_to_order(dict(row)) for row in rows]

    async def reconcile_pending(self, limit: int = 25) -> list[PaymentOrder]:
        """Проверяет незавершённые оплаты и возвращает новые начисления."""
        credited: list[PaymentOrder] = []
        for order in await self.get_pending_orders(limit):
            if not order.external_payment_id:
                continue
            try:
                confirmed = await self.check_and_credit(order.public_id, order.user_id)
            except PaymentError as exc:
                # pending и canceled являются обычными состояниями проверки.
                lowered = str(exc).lower()
                if "пока не подтверждена" not in lowered and "отменён" not in lowered:
                    logger.warning(
                        "Платёж %s не прошёл автоматическую проверку: %s",
                        order.public_id,
                        exc,
                    )
                continue
            except Exception:
                logger.exception("Ошибка фоновой сверки платежа %s", order.public_id)
                continue
            if confirmed.status == "paid":
                credited.append(confirmed)
        return credited

    @staticmethod
    def _metadata(row: dict[str, Any]) -> dict[str, Any]:
        try:
            value = json.loads(row.get("metadata") or "{}")
            return value if isinstance(value, dict) else {}
        except (TypeError, json.JSONDecodeError):
            return {}

    def _row_to_order(self, row: dict[str, Any]) -> PaymentOrder:
        metadata = self._metadata(row)
        package_key = str(metadata.get("package_key") or row.get("tariff") or "")
        package = db_manager.get_token_package_cached(package_key) or TOKEN_PACKAGES.get(package_key, {})
        return PaymentOrder(
            id=int(row["id"]), public_id=str(row.get("provider_payment_id") or ""),
            user_id=int(row["user_id"]), package_key=package_key,
            tokens=int(metadata.get("tokens") or package.get("tokens") or 0),
            amount_rub=int(Decimal(str(row.get("amount") or 0))),
            status=str(row.get("status") or "pending"), provider=str(row.get("provider") or "yookassa"),
            confirmation_url=metadata.get("confirmation_url"),
            external_payment_id=metadata.get("external_payment_id"),
        )


payment_service = PaymentService()
