"""
Идентификаторы инструментов для использования во всём проекте.
"""

from enum import Enum


class ToolNames(str, Enum):
    SALES_SCRIPT = "sales_script"
    MARKETING_POST = "marketing_post"
    IMAGE_CREATIVE = "image_creative"
    TEXT_EDITOR = "text_editor"
    DOCUMENT_ANALYZER = "document_analyzer"
    ASSISTANT = "assistant"
    MARKETPLACE = "marketplace"