from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from src.application.ports import ConsentNotifier, PermanentDeliveryError, Translator
from src.domain.entities import User
from src.presentation.keyboards import consent_keyboard


class TelegramConsentNotifier(ConsentNotifier):
    def __init__(self, bot: Bot, translator: Translator) -> None:
        self._bot = bot
        self._translator = translator

    async def send_consent_request(self, user: User) -> None:
        language = user.effective_language
        try:
            await self._bot.send_message(
                chat_id=user.telegram_id,
                text=self._translator.get(language, "consent_question"),
                reply_markup=consent_keyboard(self._translator, language),
            )
        except (TelegramForbiddenError, TelegramBadRequest) as error:
            # Bot bloklangan yoki chat topilmadi: qayta urinish foyda bermaydi
            raise PermanentDeliveryError(str(error)) from error
