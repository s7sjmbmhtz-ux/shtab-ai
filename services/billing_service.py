"""Атомарное списание внутренних токенов и бесплатных попыток."""
import contextlib
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from database import db_manager
from model_catalog import GenerationKind, get_model
from model_prices import MODEL_COSTS
from settings import settings


class ChargeSource(StrEnum):
    FREE_TRIAL = "free_trial"
    TOKENS = "tokens"
    ADMIN = "admin"


@dataclass(frozen=True, slots=True)
class Charge:
    user_id: int
    model_key: str
    kind: GenerationKind
    amount: int
    source: ChargeSource
    ledger_id: int
    provider_cost_rub: float | None = None


class InsufficientBalanceError(RuntimeError):
    def __init__(self, required: int, balance: int):
        super().__init__(f"Недостаточно токенов: требуется {required}, доступно {balance}")
        self.required = required
        self.balance = balance


class BillingService:
    @staticmethod
    def _free_model_for(kind: GenerationKind) -> str:
        """Возвращает единственную модель, доступную по бесплатной попытке."""
        mapping = {
            GenerationKind.TEXT: settings.FREE_TEXT_MODEL,
            GenerationKind.IMAGE: settings.FREE_IMAGE_MODEL,
            GenerationKind.VIDEO: settings.FREE_VIDEO_MODEL,
        }
        return mapping[kind]

    async def reserve(
        self,
        user_id: int,
        model_key: str,
        *,
        amount: int | None = None,
        provider_cost_rub: float | None = None,
    ) -> Charge:
        model = get_model(model_key)
        if not db_manager.is_model_enabled_cached(model.key):
            raise ValueError("Модель временно отключена администратором")
        token_cost = model.token_cost if amount is None else int(amount)
        if token_cost <= 0:
            raise ValueError("Стоимость генерации должна быть больше нуля")
        estimated_cost = (
            db_manager.get_model_provider_cost_cached(model.key)
            if provider_cost_rub is None
            else float(provider_cost_rub)
        )
        db_manager.assert_generation_price_safe(
            model.key,
            token_cost,
            provider_cost_rub=estimated_cost,
        )
        if settings.is_admin(user_id):
            ledger_id = await db_manager.create_admin_generation_ledger(
                user_id,
                model.kind.value,
                model.key,
                estimated_cost,
            )
            return Charge(
                user_id,
                model.key,
                model.kind,
                0,
                ChargeSource.ADMIN,
                ledger_id,
                estimated_cost,
            )

        # Бесплатная попытка относится не ко всему разделу, а только к
        # одной заранее выбранной базовой модели. Премиальная модель всегда
        # оплачивается токенами, даже если бесплатная попытка этого типа ещё
        # не использована.
        allow_free_trial = model.key == self._free_model_for(model.kind)
        result = await db_manager.reserve_generation(
            user_id=user_id,
            generation_kind=model.kind.value,
            model_key=model.key,
            token_cost=token_cost,
            allow_free_trial=allow_free_trial,
            use_supplied_cost=amount is not None,
            provider_cost_rub=estimated_cost,
        )
        if result["source"] == "insufficient":
            raise InsufficientBalanceError(int(result["amount"]), result["balance"])
        return Charge(
            user_id=user_id,
            model_key=model.key,
            kind=model.kind,
            amount=result["amount"],
            source=ChargeSource(result["source"]),
            ledger_id=int(result["ledger_id"]),
            provider_cost_rub=result.get("provider_cost_rub"),
        )

    async def refund(
        self,
        charge: Charge,
        reason: str,
        *,
        count_failure: bool = True,
    ) -> bool:
        refunded = await db_manager.refund_generation(
            user_id=charge.user_id,
            generation_kind=charge.kind.value,
            model_key=charge.model_key,
            amount=charge.amount,
            source=charge.source.value,
            reason=reason,
            ledger_id=charge.ledger_id,
        )
        if refunded and count_failure:
            with contextlib.suppress(Exception):
                await db_manager.record_model_outcome(
                    charge.model_key,
                    success=False,
                    error_message=reason,
                )
        return refunded

    async def complete(
        self,
        charge: Charge,
        *,
        result: dict[str, Any] | None = None,
        provider_request_id: str | None = None,
        provider_cost_rub: float | None = None,
    ) -> bool:
        actual_cost = provider_cost_rub
        if actual_cost is None and result:
            actual_cost = self._extract_actual_cost(charge.model_key, result)
        completed = await db_manager.complete_generation(
            charge.ledger_id,
            provider_cost_rub=actual_cost,
            provider_request_id=provider_request_id,
        )
        if completed:
            with contextlib.suppress(Exception):
                await db_manager.record_model_outcome(charge.model_key, success=True)
        return completed

    @staticmethod
    def _extract_actual_cost(
        model_key: str,
        result: dict[str, Any],
    ) -> float | None:
        """Извлекает рублёвую стоимость или считает её по usage текста."""
        candidates = [result]
        for key in ("data", "result", "request", "billing"):
            value = result.get(key)
            if isinstance(value, dict):
                candidates.append(value)
        for payload in candidates:
            for key in ("provider_cost_rub", "cost_rub", "price_rub"):
                value = payload.get(key)
                try:
                    parsed = float(value)
                except (TypeError, ValueError):
                    continue
                if parsed >= 0:
                    return parsed

        usage = result.get("usage")
        if not isinstance(usage, dict):
            return None
        aliases = {
            "deepseek-v4-flash": "deepseek/deepseek-v4-flash",
            "deepseek-v4-pro": "deepseek/deepseek-v4-pro",
            "gpt-5.4-mini": "openai/gpt-5.4-mini",
            "gpt-5-5": "openai/gpt-5.5",
        }
        # Бизнес-инструменты используют DeepSeek V4 Flash.
        cost_key = aliases.get(model_key)
        if cost_key is None and model_key.startswith(("business-", "marketplace-seo")):
            cost_key = "deepseek/deepseek-v4-flash"
        prices = MODEL_COSTS.get(cost_key or "")
        if not prices:
            return None
        try:
            input_tokens = int(
                usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0
            )
            output_tokens = int(
                usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0
            )
        except (TypeError, ValueError):
            return None
        return round(
            input_tokens * float(prices.get("input", 0)) / 1_000_000
            + output_tokens * float(prices.get("output", 0)) / 1_000_000,
            6,
        )


billing_service = BillingService()
