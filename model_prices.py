"""
Стоимость моделей AI для расчёта расходов.
Цены указаны за 1 млн токенов в RUB.
"""

MODEL_COSTS = {
    # ============================================================
    # DEEPSEEK (Provod.ai)
    # ============================================================
    "deepseek/deepseek-v4-flash": {
        "input": 11.11,
        "output": 22.22,
    },
    "deepseek/deepseek-v4-pro": {
        "input": 34.52,
        "output": 69.04,
    },

    # ============================================================
    # OPENAI
    # ============================================================
    "openai/gpt-5.4-mini": {
        "input": 59.52,
        "output": 357.11,
    },
    "openai/gpt-5.5": {
        "input": 396.79,
        "output": 2380.71,
    },

    # ============================================================
    # GOOGLE (Gemini Image)
    # ============================================================
    "google/gemini-3.1-flash-lite-image": {
        "image_cost": 2.55,
    },
    "google/gemini-3.1-flash-image": {
        "image_cost": 5.09,
    },
    "google/gemini-3-pro-image": {
        "image_cost": 10.17,
    },
}


def get_model_cost(model: str) -> float:
    """Возвращает стоимость за 1 млн токенов (input)."""
    costs = MODEL_COSTS.get(model)
    if not costs:
        return 0.0
    return costs.get("input", 0.0)


def get_model_output_cost(model: str) -> float:
    """Возвращает стоимость за 1 млн токенов (output)."""
    costs = MODEL_COSTS.get(model)
    if not costs:
        return 0.0
    return costs.get("output", 0.0)


def get_image_cost(model: str) -> float:
    """Возвращает стоимость одной генерации изображения."""
    costs = MODEL_COSTS.get(model)
    if not costs:
        return 0.0
    return costs.get("image_cost", 0.0)