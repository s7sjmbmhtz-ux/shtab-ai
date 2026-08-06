"""FSM-состояния полноценной Telegram-админки."""
from aiogram.fsm.state import State, StatesGroup


class AdminUserStates(StatesGroup):
    waiting_query = State()
    waiting_token_amount = State()
    waiting_token_comment = State()
    waiting_block_reason = State()


class AdminPackageStates(StatesGroup):
    waiting_tokens = State()
    waiting_price = State()


class AdminBroadcastStates(StatesGroup):
    waiting_text = State()
    waiting_confirmation = State()
