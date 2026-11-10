from aiogram import Bot

from src.application.ports import ConsentNotifier
from src.domain.entities import User
from src.infrastructure.i18n.translator import Translator
from src.presentation.keyboards import consent_keyboard


class TelegramConsentNotifier(ConsentNotifier):
    def __init__(self, bot: Bot, translator: Translator) -> None:
        self._bot = bot
        self._translator = translator

    async def send_consent_request(self, user: User) -> None:
        language = user.effective_language
        await self._bot.send_message(
            chat_id=user.telegram_id,
            text=self._translator.get(language, "consent_question"),
            reply_markup=consent_keyboard(self._translator, language),
        )
