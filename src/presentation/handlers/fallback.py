from aiogram import Router
from aiogram.types import Message

from src.application.get_user import GetUser
from src.domain.entities import DEFAULT_LANGUAGE
from src.infrastructure.i18n.translator import Translator
from src.presentation.keyboards import contact_keyboard, language_keyboard


def build_router() -> Router:
    router = Router(name="fallback")

    @router.message()
    async def unknown_message(message: Message, get_user: GetUser, translator: Translator) -> None:
        user = await get_user.execute(message.from_user.id)

        if user is None:
            # Telefon qo'lda yozilgan bo'lishi mumkin, uni qabul qilmaymiz: faqat tugma orqali
            await message.answer(
                translator.get(DEFAULT_LANGUAGE, "confirm_phone_by_button"),
                reply_markup=contact_keyboard(translator, DEFAULT_LANGUAGE),
            )
        elif not user.is_onboarded:
            await message.answer(
                translator.get(DEFAULT_LANGUAGE, "choose_language"),
                reply_markup=language_keyboard(),
            )
        else:
            await message.answer(translator.get(user.language, "help"))

    return router
