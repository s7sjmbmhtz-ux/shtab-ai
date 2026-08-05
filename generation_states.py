"""FSM-состояния нового универсального интерфейса генераций."""
from aiogram.fsm.state import State, StatesGroup


class TextGenerationStates(StatesGroup):
    chatting = State()


class ImageGenerationStates(StatesGroup):
    choosing_mode = State()
    choosing_model = State()
    choosing_input = State()
    waiting_image = State()
    choosing_cartoon_strength = State()
    waiting_prompt = State()
    confirming = State()
    processing = State()


class VideoGenerationStates(StatesGroup):
    choosing_duration = State()
    choosing_input = State()
    waiting_image = State()
    waiting_prompt = State()
    confirming = State()
    processing = State()
