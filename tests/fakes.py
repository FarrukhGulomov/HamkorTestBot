from datetime import UTC, datetime, timedelta

from src.application.ports import Clock, ConsentNotifier
from src.domain.entities import ConsentStatus, User
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
        return self.items.get(telegram_id)

    async def save(self, user: User) -> None:
        self.items[user.telegram_id] = user

    async def find_awaiting_consent(self, idle_since: datetime) -> list[User]:
        return [
            u
            for u in self.items.values()
            if u.is_onboarded
            and u.consent_status is ConsentStatus.PENDING
            and u.consent_requested_at is None
            and u.last_message_at <= idle_since
        ]


class RecordingNotifier(ConsentNotifier):
    def __init__(self, fail: bool = False) -> None:
        self.sent_to: list[int] = []
        self._fail = fail

    async def send_consent_request(self, user: User) -> None:
        if self._fail:
            raise RuntimeError("telegram is down")
        self.sent_to.append(user.telegram_id)
