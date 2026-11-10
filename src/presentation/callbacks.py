from aiogram.filters.callback_data import CallbackData

from src.domain.entities import Language


class LanguageCallback(CallbackData, prefix="lang"):
    language: Language


class ConsentCallback(CallbackData, prefix="consent"):
    agreed: bool


CONSENT_DONE = "consent_done"
