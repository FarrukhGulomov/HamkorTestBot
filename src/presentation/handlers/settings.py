from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from src.application.change_language import ChangeLanguage, UserNotFound
from src.application.get_user import GetUser
from src.application.ports import Translator
from src.domain.entities import DEFAULT_LANGUAGE
from src.presentation.callbacks import LanguageCallback
from src.presentation.filters import TextKey
from src.presentation.keyboards import language_keyboard, main_menu_keyboard


def build_router() -> Router:
    router = Router(name="settings")

    @router.message(Command("settings"))
    @router.message(TextKey("settings_button"))
    async def open_settings(message: Message, get_user: GetUser, translator: Translator) -> None:
        user = await get_user.execute(message.from_user.id)
        if user is None:
            await message.answer(translator.get(DEFAULT_LANGUAGE, "need_start"))
            return

        await message.answer(
            translator.get(user.effective_language, "settings_title"),
            reply_markup=language_keyboard(),
        )


    @router.callback_query(LanguageCallback.filter())
    async def choose_language(
        callback: CallbackQuery,
        callback_data: LanguageCallback,
        change_language: ChangeLanguage,
        translator: Translator,
    ) -> None:
        try:
            result = await change_language.execute(callback.from_user.id, callback_data.language)
        except UserNotFound:
            await callback.answer(translator.get(DEFAULT_LANGUAGE, "need_start"), show_alert=True)
            return

        language = callback_data.language
        text_key = "welcome" if result.is_first_choice else "language_changed"

        await callback.answer()
        if isinstance(callback.message, Message):
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer(
                translator.get(language, text_key),
                reply_markup=main_menu_keyboard(translator, language),
            )

    return router
