from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Language(StrEnum):
    UZ = "uz"
    UZ_CYRL = "uz_cyrl"
    RU = "ru"
    EN = "en"
    KAA = "kaa"
    ZH = "zh"


DEFAULT_LANGUAGE = Language.UZ


class ConsentStatus(StrEnum):
    PENDING = "pending"
    AGREED = "agreed"
    DECLINED = "declined"


@dataclass
class User:
    telegram_id: int
    phone_number: str
    first_name: str
    created_at: datetime
    last_message_at: datetime
    language: Language | None = None
    consent_status: ConsentStatus = ConsentStatus.PENDING
    consent_requested_at: datetime | None = None
    consent_answered_at: datetime | None = None
    consent_claimed_at: datetime | None = None
    consent_attempts: int = 0

    @property
    def is_onboarded(self) -> bool:
        return self.language is not None

    @property
    def effective_language(self) -> Language:
        return self.language or DEFAULT_LANGUAGE
