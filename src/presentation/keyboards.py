from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.domain.entities import Language
from src.infrastructure.i18n.translator import Translator
from src.presentation.callbacks import CONSENT_DONE, ConsentCallback, LanguageCallback

LANGUAGE_LABELS: dict[Language, str] = {
    Language.UZ: "O'zbekcha",
    Language.UZ_CYRL: "Ўзбекча",
    Language.RU: "Русский",
    Language.EN: "English",
    Language.KAA: "Qaraqalpaqsha",
    Language.ZH: "中文",
}


def contact_keyboard(translator: Translator, language: Language) -> ReplyKeyboardMarkup:
    button = KeyboardButton(
        text=translator.get(language, "share_phone_button"),
        request_contact=True,
    )
    return ReplyKeyboardMarkup(keyboard=[[button]], resize_keyboard=True, one_time_keyboard=True)


def language_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for language, label in LANGUAGE_LABELS.items():
        builder.button(text=label, callback_data=LanguageCallback(language=language))
    builder.adjust(2)
    return builder.as_markup()


def main_menu_keyboard(translator: Translator, language: Language) -> ReplyKeyboardMarkup:
    button = KeyboardButton(text=translator.get(language, "settings_button"))
    return ReplyKeyboardMarkup(keyboard=[[button]], resize_keyboard=True)


def consent_keyboard(translator: Translator, language: Language) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=translator.get(language, "consent_yes"),
        callback_data=ConsentCallback(agreed=True),
    )
    builder.button(
        text=translator.get(language, "consent_no"),
        callback_data=ConsentCallback(agreed=False),
    )
    builder.adjust(2)
    return builder.as_markup()


def consent_answered_keyboard(
    translator: Translator, language: Language, agreed: bool
) -> InlineKeyboardMarkup:
    """Javob berilgandan keyin tanlangan tugma ✓ belgisi bilan ko'rsatiladi."""
    yes = translator.get(language, "consent_yes")
    no = translator.get(language, "consent_no")
    buttons = [
        InlineKeyboardButton(text=f"✓ {yes}" if agreed else yes, callback_data=CONSENT_DONE),
        InlineKeyboardButton(text=no if agreed else f"✓ {no}", callback_data=CONSENT_DONE),
    ]
    return InlineKeyboardMarkup(inline_keyboard=[buttons])
