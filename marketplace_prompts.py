"""Профессиональные промпты для карточек маркетплейсов."""
from __future__ import annotations

STYLE = {
    "minimal": "light minimal studio, white and pale beige palette, soft realistic shadow",
    "premium": "premium commercial studio, elegant dark background, controlled highlights",
    "cozy": "cozy realistic interior, warm natural light, authentic everyday context",
    "bright": "bright modern advertising composition, energetic clean color accents",
    "technical": "precise technical catalog style, neutral background, crisp detail",
    "natural": "natural daylight, realistic materials and colors, restrained composition",
}
GOAL = {
    "sales": "high-conversion marketplace composition with a strong visual hierarchy",
    "premium": "premium brand presentation with refined commercial lighting",
    "catalog": "clean trustworthy catalog presentation focused on the product",
    "social": "dynamic advertising composition suitable for social media",
}
PLATFORM = {
    "wb": "Wildberries-oriented visual: highly noticeable in a crowded feed, clear focal point, bold but clean accents",
    "ozon": "Ozon-oriented visual: clean catalog presentation, restrained premium composition, strong product focus",
    "yandex": "Yandex Market-oriented visual: informative neutral catalog style, realistic color and minimal decoration",
    "all": "universal marketplace visual suitable for Wildberries, Ozon and Yandex Market",
}

def build_prompts(kind: str, product: str, features: str, style: str, goal: str, platform: str, *, has_photo: bool) -> list[str]:
    identity = (
        "Preserve the exact product identity from the reference image: shape, proportions, construction, materials, colors, logos and every visible detail. "
        "Do not redesign the product and do not place any letters, labels or typography on the product. "
        if has_photo else
        "Create a realistic product concept that follows the description exactly. "
    )
    base = (
        f"Professional marketplace product photography. Product: {product}. Verified features only: {features}. "
        f"{identity}{GOAL.get(goal, GOAL['catalog'])}. {PLATFORM.get(platform, PLATFORM['all'])}. "
        f"Style: {STYLE.get(style, STYLE['minimal'])}. Vertical 4:5 composition, realistic scale and materials, high detail. "
        "No watermark, no readable text, no random letters, no labels on the product, no distorted geometry, no duplicate product parts. "
    )
    if kind == "main":
        return [base + "Hero main image, centered product, clear silhouette, clean background, generous empty space, realistic contact shadow."]
    if kind == "lifestyle":
        return [base + "Lifestyle scene showing the product naturally in use. Keep the product dominant and physically realistic."]
    if kind == "infographic":
        return [base + "Infographic base only: product on one side and three clean empty callout zones. Do not generate words; leave blank panels for later text overlay."]
    return [
        base + "Hero main image, centered product, clean marketplace catalog quality.",
        base + "Lifestyle scene showing the product naturally in use, realistic environment and scale.",
        base + "Detailed close-up showing construction and useful real features, with clean empty space for later annotations.",
    ]
