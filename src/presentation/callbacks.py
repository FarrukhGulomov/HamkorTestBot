from aiogram.filters.callback_data import CallbackData

from src.domain.entities import Language


class LanguageCallback(CallbackData, prefix="lang"):
    language: Language


class ConsentCallback(CallbackData, prefix="consent"):
    agreed: bool


class RatingCallback(CallbackData, prefix="rate"):
    interaction_id: int
    positive: bool


CONSENT_DONE = "consent_done"
RATING_DONE = "rating_done"
