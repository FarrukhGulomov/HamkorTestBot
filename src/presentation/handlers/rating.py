from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from src.application.get_user import GetUser
from src.application.ports import Translator
from src.application.rate_answer import InteractionNotFound, RateAnswer
from src.domain.entities import DEFAULT_LANGUAGE, Rating
from src.presentation.callbacks import RATING_DONE, RatingCallback
from src.presentation.keyboards import rating_answered_keyboard


def build_router() -> Router:
    router = Router(name="rating")

    @router.callback_query(RatingCallback.filter())
    async def rate_answer(
        callback: CallbackQuery,
        callback_data: RatingCallback,
        rate_answer: RateAnswer,
        get_user: GetUser,
        translator: Translator,
    ) -> None:
        rating = Rating.LIKE if callback_data.positive else Rating.DISLIKE
        try:
            interaction = await rate_answer.execute(
                callback.from_user.id, callback_data.interaction_id, rating
            )
        except InteractionNotFound:
            await callback.answer()
            return

        user = await get_user.execute(callback.from_user.id)
        language = user.effective_language if user else DEFAULT_LANGUAGE

        await callback.answer(translator.get(language, "rating_thanks"))
        if isinstance(callback.message, Message):
            await callback.message.edit_reply_markup(
                reply_markup=rating_answered_keyboard(interaction.rating is Rating.LIKE)
            )

    @router.callback_query(F.data == RATING_DONE)
    async def already_rated(callback: CallbackQuery) -> None:
        await callback.answer()

    return router
