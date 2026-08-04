"""Категорийные промпты для товарных карточек маркетплейсов."""
from __future__ import annotations

import re


CATEGORY_TITLES = {
    "tools": "Инструменты",
    "kitchen": "Кухня",
    "electronics": "Электроника",
    "cosmetics": "Косметика",
    "clothing": "Одежда",
    "shoes": "Обувь",
    "furniture": "Мебель",
    "kids": "Детские товары",
    "pets": "Зоотовары",
    "other": "Другое",
}

CATEGORY_KEYWORDS = {
    "tools": (
        "молоток", "дрель", "шуруповерт", "отверт", "пила", "топор", "ключ",
        "пассатиж", "плоскогуб", "рулетк", "строительн", "инструмент",
        "перфоратор", "гвоздодер", "гвоздодёр", "стамеск", "болгарк",
    ),
    "kitchen": (
        "кастрюл", "сковород", "нож", "чайник", "тарел", "чашк", "кухон",
        "посуда", "термос", "контейнер", "лопатк", "венчик",
    ),
    "electronics": (
        "телефон", "смартфон", "наушник", "колонк", "кабель", "заряд",
        "мыш", "клавиатур", "ноутбук", "монитор", "электрон",
    ),
    "cosmetics": (
        "крем", "сыворот", "шампун", "космет", "помад", "тушь", "маск",
        "флакон", "парфюм", "гель",
    ),
    "clothing": (
        "футбол", "рубаш", "плать", "куртк", "брюк", "джинс", "одежд",
        "толстов", "худи", "свитер",
    ),
    "shoes": ("кроссов", "ботин", "туфл", "сапог", "обув", "кед", "сандал"),
    "furniture": ("стол", "стул", "кресл", "диван", "шкаф", "полк", "мебел", "тумб"),
    "kids": ("игруш", "детск", "конструктор", "кукл", "машинк", "погремуш"),
    "pets": ("корм", "поводок", "ошейник", "когтеточ", "зоотовар", "миска", "лежанк"),
}

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
    "wb": "Wildberries-oriented visual: noticeable in a crowded feed, clear focal point, bold but clean accents",
    "ozon": "Ozon-oriented visual: clean catalog presentation, restrained premium composition, strong product focus",
    "yandex": "Yandex Market-oriented visual: informative neutral catalog style, realistic color and minimal decoration",
    "all": "universal marketplace visual suitable for Wildberries, Ozon and Yandex Market",
}

CATEGORY_RULES = {
    "tools": (
        "The product is a real hand or power tool. Preserve mechanically plausible geometry, "
        "metal surfaces, functional joints, grip texture and realistic construction. "
        "Do not turn the tool into food, fruit, a bag, decor, a toy or an abstract object."
    ),
    "kitchen": (
        "The product is kitchenware. Preserve usable geometry, food-safe materials, handles, lids "
        "and realistic scale. Do not transform it into food or decorative sculpture."
    ),
    "electronics": (
        "The product is consumer electronics. Preserve ports, buttons, screen, seams and realistic "
        "industrial design. No invented interfaces, extra lenses or random controls."
    ),
    "cosmetics": (
        "The product is a cosmetic item. Preserve bottle, cap, dispenser, package proportions and "
        "material finish. No invented readable labels or altered packaging."
    ),
    "clothing": (
        "The product is clothing. Preserve cut, seams, fabric, color and garment construction. "
        "No extra sleeves, distorted anatomy or altered pattern."
    ),
    "shoes": (
        "The product is footwear. Preserve sole, upper, laces, stitching and left-right anatomy. "
        "No melted geometry or extra shoe parts."
    ),
    "furniture": (
        "The product is furniture. Preserve structural proportions, joints, legs, surfaces and "
        "realistic load-bearing geometry."
    ),
    "kids": (
        "The product is a children's item. Preserve safe, plausible construction and all recognizable parts."
    ),
    "pets": (
        "The product is a pet item. Preserve its practical purpose, material, closures and realistic scale."
    ),
    "other": "Preserve the product as a single recognizable, physically plausible commercial object.",
}

HAMMER_PATTERN = re.compile(r"\\b(молоток|hammer|гвоздод[её]р)\\b", re.IGNORECASE)


def detect_category(product_name: str) -> str | None:
    normalized = product_name.casefold()
    scores: dict[str, int] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in normalized)
        if score:
            scores[category] = score
    return max(scores, key=scores.get) if scores else None


def _object_lock(product: str, category: str) -> str:
    if HAMMER_PATTERN.search(product):
        return (
            "OBJECT LOCK — render exactly one construction claw hammer: a solid steel hammer head, "
            "one flat circular striking face on one side, one curved two-prong nail-pulling claw on "
            "the opposite side, and one straight ergonomic handle. The object must unmistakably be "
            "a functional hammer. No fruit, oranges, mandarins, food, pastries, shopping bags, "
            "baskets, tubes, vases, plants or unrelated props replacing the hammer. "
        )

    return (
        f"OBJECT LOCK — the only main product is exactly: {product}. "
        f"{CATEGORY_RULES.get(category, CATEGORY_RULES['other'])} "
        "Do not substitute the named product with another object. "
    )


def build_prompts(
    kind: str,
    product: str,
    features: str,
    style: str,
    goal: str,
    platform: str,
    category: str,
    *,
    has_photo: bool,
) -> list[str]:
    if has_photo:
        identity = (
            "REFERENCE IMAGE IS AUTHORITATIVE. Preserve the exact product identity from the reference: "
            "silhouette, proportions, construction, materials, colors, grip, head, edges, logos and "
            "every visible detail. Change only background, lighting and surrounding scene. "
        )
    else:
        identity = (
            "Create a faithful commercial visualization of the named product. "
            "The product name has priority over mood, color palette and props. "
        )

    base = (
        "Professional marketplace product photography. "
        f"Product name: {product}. Product category: {CATEGORY_TITLES.get(category, 'Другое')}. "
        f"Verified features only: {features}. "
        f"{_object_lock(product, category)}{identity}"
        f"{GOAL.get(goal, GOAL['catalog'])}. "
        f"{PLATFORM.get(platform, PLATFORM['all'])}. "
        f"Style: {STYLE.get(style, STYLE['minimal'])}. "
        "Vertical 4:5 composition, realistic scale, physically correct materials, sharp commercial detail. "
        "Exactly one main product unless a set is explicitly requested. "
        "No watermark, no readable text, no random letters, no fake brand names, no labels added to the "
        "product, no distorted geometry, no duplicate parts, no object substitution. "
    )

    if kind == "main":
        return [
            base
            + "Hero main image. Product centered and fully visible, clear silhouette, clean background, "
              "realistic contact shadow, generous negative space, no decorative objects covering the product."
        ]
    if kind == "lifestyle":
        return [
            base
            + "Lifestyle scene that demonstrates the product's real use. Keep the product dominant, "
              "fully recognizable and physically realistic. Supporting props must be minimal and relevant."
        ]
    if kind == "infographic":
        return [
            base
            + "Infographic base only. Place the product on one side and create three empty clean callout "
              "zones on the other side. Do not generate words; leave blank panels for later text overlay."
        ]
    return [
        base + "Hero main image, centered product, clean marketplace catalog quality, no unrelated props.",
        base + "Lifestyle scene showing the product in its correct real-world use, minimal relevant environment.",
        base + "Detailed close-up of actual construction and verified useful features, with clean empty space.",
    ]
