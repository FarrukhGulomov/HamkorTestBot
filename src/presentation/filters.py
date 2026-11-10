from aiogram.filters import BaseFilter
from aiogram.types import Message

from src.infrastructure.i18n.translator import Translator


class TextKey(BaseFilter):
    """Xabar matni berilgan kalitning istalgan tildagi tarjimasiga teng bo'lsa o'tadi."""

    def __init__(self, key: str) -> None:
        self.key = key

    async def __call__(self, message: Message, translator: Translator) -> bool:
        return message.text in translator.all_translations(self.key)
