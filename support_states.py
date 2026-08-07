"""Состояния пользовательской и административной поддержки."""
from aiogram.fsm.state import State, StatesGroup


class SupportStates(StatesGroup):
    waiting_description = State()
    waiting_attachment = State()


class AdminSupportStates(StatesGroup):
    waiting_reply = State()
