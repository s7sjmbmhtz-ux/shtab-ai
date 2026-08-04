from aiogram.fsm.state import State, StatesGroup


class BusinessToolStates(StatesGroup):
    collecting = State()


class MarketplaceStates(StatesGroup):
    waiting_photo = State()
    choosing_product_type = State()
    waiting_product_name = State()
    choosing_features_action = State()
    choosing_category = State()
    waiting_features = State()
    choosing_goal = State()
    choosing_platform = State()
    choosing_style = State()
    confirming = State()
    generating = State()
