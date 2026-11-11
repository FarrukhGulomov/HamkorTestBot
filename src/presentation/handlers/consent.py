from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from src.application.change_language import UserNotFound
from src.application.ports import Translator
from src.application.save_consent import SaveConsent
from src.domain.entities import DEFAULT_LANGUAGE, ConsentStatus
from src.presentation.callbacks import CONSENT_DONE, ConsentCallback
from src.presentation.keyboards import consent_answered_keyboard
from src.presentation.messages import set_reply_markup


def build_router() -> Router:
    router = Router(name="consent")

    @router.callback_query(ConsentCallback.filter())
    async def answer_consent(
        callback: CallbackQuery,
        callback_data: ConsentCallback,
        save_consent: SaveConsent,
        translator: Translator,
    ) -> None:
        try:
            result = await save_consent.execute(callback.from_user.id, callback_data.agreed)
        except UserNotFound:
            await callback.answer(translator.get(DEFAULT_LANGUAGE, "need_start"), show_alert=True)
            return

        user = result.user
        language = user.effective_language
        agreed = user.consent_status is ConsentStatus.AGREED
        thanks_key = "consent_thanks_yes" if agreed else "consent_thanks_no"

        await callback.answer()
        if isinstance(callback.message, Message):
            await set_reply_markup(
                callback.message, consent_answered_keyboard(translator, language, agreed)
            )
            if result.recorded:  # tugma ikki marta bosilsa, "Rahmat" bir marta yuboriladi
                await callback.message.answer(translator.get(language, thanks_key))

    @router.callback_query(F.data == CONSENT_DONE)
    async def consent_already_answered(callback: CallbackQuery) -> None:
        await callback.answer()

    return router
