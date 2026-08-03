"""FSM-состояния нового универсального интерфейса генераций."""
from aiogram.fsm.state import State, StatesGroup


class TextGenerationStates(StatesGroup):
    chatting = State()


class ImageGenerationStates(StatesGroup):
    choosing_input = State()
    waiting_image = State()
    waiting_prompt = State()
    processing = State()


class VideoGenerationStates(StatesGroup):
    choosing_input = State()
    waiting_image = State()
    waiting_prompt = State()
    processing = State()
