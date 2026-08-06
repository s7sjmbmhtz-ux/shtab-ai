"""Атомарное списание внутренних токенов и бесплатных попыток."""
from dataclasses import dataclass
from enum import StrEnum

from database import db_manager
from model_catalog import GenerationKind, get_model
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

    async def reserve(self, user_id: int, model_key: str, *, amount: int | None = None) -> Charge:
        model = get_model(model_key)
        token_cost = model.token_cost if amount is None else max(0, int(amount))
        if user_id == settings.ADMIN_TELEGRAM_ID:
            return Charge(user_id, model.key, model.kind, 0, ChargeSource.ADMIN)

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
        )
        if result["source"] == "insufficient":
            raise InsufficientBalanceError(int(result["amount"]), result["balance"])
        return Charge(
            user_id=user_id,
            model_key=model.key,
            kind=model.kind,
            amount=result["amount"],
            source=ChargeSource(result["source"]),
        )

    async def refund(self, charge: Charge, reason: str) -> None:
        if charge.source == ChargeSource.ADMIN:
            return
        await db_manager.refund_generation(
            user_id=charge.user_id,
            generation_kind=charge.kind.value,
            model_key=charge.model_key,
            amount=charge.amount,
            source=charge.source.value,
            reason=reason,
        )


billing_service = BillingService()
