from aiogram import Router
from aiogram.types import Message

from src.application.answer_question import AnswerQuestion
from src.application.get_user import GetUser
from src.application.ports import Translator
from src.domain.entities import DEFAULT_LANGUAGE
from src.presentation.keyboards import contact_keyboard, language_keyboard, rating_keyboard


def build_router() -> Router:
    router = Router(name="fallback")

    @router.message()
    async def handle_message(
        message: Message,
        get_user: GetUser,
        answer_question: AnswerQuestion,
        translator: Translator,
    ) -> None:
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
        elif message.text is None:
            await message.answer(translator.get(user.language, "text_only"))
        else:
            interaction = await answer_question.execute(user.telegram_id, message.text)
            await message.answer(interaction.answer, reply_markup=rating_keyboard(interaction.id))

    return router
