from datetime import UTC, datetime, timedelta

from src.application.ports import Clock, ConsentNotifier
from src.domain.entities import ConsentStatus, Language, User
from src.domain.repositories import UserRepository


class FakeClock(Clock):
    def __init__(self, now: datetime | None = None) -> None:
        self._now = now or datetime(2025, 1, 1, 12, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self._now

    def advance(self, **kwargs: float) -> None:
        self._now += timedelta(**kwargs)


class InMemoryUserRepository(UserRepository):
    def __init__(self) -> None:
        self.items: dict[int, User] = {}

    async def get(self, telegram_id: int) -> User | None:
        user = self.items.get(telegram_id)
        # Haqiqiy repozitoriy kabi har safar yangi nusxa qaytaramiz
        return User(**vars(user)) if user else None

    async def upsert_contact(
        self, telegram_id: int, phone_number: str, first_name: str, now: datetime
    ) -> User:
        user = self.items.get(telegram_id)
        if user is None:
            user = User(
                telegram_id=telegram_id,
                phone_number=phone_number,
                first_name=first_name,
                created_at=now,
                last_message_at=now,
            )
            self.items[telegram_id] = user
        else:
            user.phone_number = phone_number
            user.first_name = first_name
            user.last_message_at = now
        return User(**vars(user))

    async def touch(self, telegram_id: int, now: datetime) -> None:
        if telegram_id in self.items:
            self.items[telegram_id].last_message_at = now

    async def set_language(self, telegram_id: int, language: Language) -> bool:
        if telegram_id not in self.items:
            return False
        self.items[telegram_id].language = language
        return True

    def _is_awaiting(self, user: User, idle_since: datetime) -> bool:
        return (
            user.is_onboarded
            and user.consent_status is ConsentStatus.PENDING
            and user.consent_requested_at is None
            and user.last_message_at <= idle_since
        )

    async def find_awaiting_consent(self, idle_since: datetime) -> list[User]:
        return [
            User(**vars(u)) for u in self.items.values() if self._is_awaiting(u, idle_since)
        ]

    async def claim_consent_request(
        self, telegram_id: int, idle_since: datetime, now: datetime
    ) -> bool:
        user = self.items.get(telegram_id)
        if user is None or not self._is_awaiting(user, idle_since):
            return False
        user.consent_requested_at = now
        return True

    async def release_consent_request(self, telegram_id: int) -> None:
        user = self.items.get(telegram_id)
        if user and user.consent_status is ConsentStatus.PENDING:
            user.consent_requested_at = None

    async def record_consent(self, telegram_id: int, agreed: bool, now: datetime) -> bool:
        user = self.items.get(telegram_id)
        if user is None or user.consent_status is not ConsentStatus.PENDING:
            return False
        user.consent_status = ConsentStatus.AGREED if agreed else ConsentStatus.DECLINED
        user.consent_answered_at = now
        return True


class RecordingNotifier(ConsentNotifier):
    def __init__(self, error: Exception | None = None) -> None:
        self.sent_to: list[int] = []
        self.error = error

    async def send_consent_request(self, user: User) -> None:
        if self.error is not None:
            raise self.error
        self.sent_to.append(user.telegram_id)
