from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from src.application.get_user import GetUser
from src.application.register_contact import RegisterContact
from src.domain.entities import DEFAULT_LANGUAGE
from src.infrastructure.i18n.translator import Translator
from src.presentation.keyboards import contact_keyboard, language_keyboard, main_menu_keyboard


def build_router() -> Router:
    router = Router(name="start")

    @router.message(CommandStart())
    async def start(message: Message, get_user: GetUser, translator: Translator) -> None:
        user = await get_user.execute(message.from_user.id)

        if user is None:
            await message.answer(
                translator.get(DEFAULT_LANGUAGE, "ask_phone"),
                reply_markup=contact_keyboard(translator, DEFAULT_LANGUAGE),
            )
        elif not user.is_onboarded:
            await message.answer(
                translator.get(DEFAULT_LANGUAGE, "choose_language"),
                reply_markup=language_keyboard(),
            )
        else:
            await message.answer(
                translator.get(user.language, "welcome"),
                reply_markup=main_menu_keyboard(translator, user.language),
            )


    @router.message(F.contact)
    async def receive_contact(
        message: Message, register_contact: RegisterContact, translator: Translator
    ) -> None:
        contact = message.contact
        if contact.user_id != message.from_user.id:
            await message.answer(
                translator.get(DEFAULT_LANGUAGE, "phone_not_own"),
                reply_markup=contact_keyboard(translator, DEFAULT_LANGUAGE),
            )
            return

        user = await register_contact.execute(
            telegram_id=message.from_user.id,
            phone_number=contact.phone_number,
            first_name=message.from_user.first_name,
        )

        if user.is_onboarded:
            await message.answer(
                translator.get(user.language, "welcome"),
                reply_markup=main_menu_keyboard(translator, user.language),
            )
            return

        await message.answer(
            translator.get(DEFAULT_LANGUAGE, "choose_language"),
            reply_markup=language_keyboard(),
        )

    return router
