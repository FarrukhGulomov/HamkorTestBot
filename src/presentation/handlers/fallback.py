from aiogram import Router
from aiogram.types import Message

from src.application.get_user import GetUser
from src.domain.entities import DEFAULT_LANGUAGE
from src.infrastructure.i18n.translator import Translator


def build_router() -> Router:
    router = Router(name="fallback")

    @router.message()
    async def unknown_message(message: Message, get_user: GetUser, translator: Translator) -> None:
        user = await get_user.execute(message.from_user.id)
        if user is None or not user.is_onboarded:
            await message.answer(translator.get(DEFAULT_LANGUAGE, "need_start"))
            return

        await message.answer(translator.get(user.language, "help"))

    return router
