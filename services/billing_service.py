"""Атомарное списание внутренних токенов и бесплатных попыток."""
from dataclasses import dataclass
from enum import StrEnum

from database import db_manager
from model_catalog import GenerationKind, get_model


class ChargeSource(StrEnum):
    FREE_TRIAL = "free_trial"
    TOKENS = "tokens"


@dataclass(frozen=True, slots=True)
class Charge:
    user_id: int
    model_key: str
    kind: GenerationKind
    amount: int
    source: ChargeSource


class InsufficientBalanceError(RuntimeError):
    def __init__(self, required: int, balance: int):
        super().__init__(f"Недостаточно токенов: требуется {required}, доступно {balance}")
        self.required = required
        self.balance = balance


class BillingService:
    async def reserve(self, user_id: int, model_key: str) -> Charge:
        model = get_model(model_key)
        result = await db_manager.reserve_generation(
            user_id=user_id,
            generation_kind=model.kind.value,
            model_key=model.key,
            token_cost=model.token_cost,
        )
        if result["source"] == "insufficient":
            raise InsufficientBalanceError(model.token_cost, result["balance"])
        return Charge(
            user_id=user_id,
            model_key=model.key,
            kind=model.kind,
            amount=result["amount"],
            source=ChargeSource(result["source"]),
        )

    async def refund(self, charge: Charge, reason: str) -> None:
        await db_manager.refund_generation(
            user_id=charge.user_id,
            generation_kind=charge.kind.value,
            model_key=charge.model_key,
            amount=charge.amount,
            source=charge.source.value,
            reason=reason,
        )


billing_service = BillingService()
