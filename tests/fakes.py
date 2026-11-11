from datetime import UTC, datetime, timedelta

from src.application.ports import AnswerProvider, Clock, ConsentNotifier
from src.domain.entities import ConsentStatus, Interaction, Language, Rating, User
from src.domain.repositories import ConsentRequestCriteria, InteractionRepository, UserRepository


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

    async def erase_personal_data(self, telegram_id: int) -> None:
        user = self.items.get(telegram_id)
        if user:
            user.phone_number = ""
            user.first_name = ""

    async def set_language(self, telegram_id: int, language: Language) -> bool:
        if telegram_id not in self.items:
            return False
        self.items[telegram_id].language = language
        return True

    @staticmethod
    def _is_awaiting(user: User, criteria: ConsentRequestCriteria) -> bool:
        return (
            user.is_onboarded
            and user.consent_status is ConsentStatus.PENDING
            and user.consent_requested_at is None
            and user.consent_attempts < criteria.max_attempts
            and user.last_message_at <= criteria.idle_since
            and (
                user.consent_claimed_at is None
                or user.consent_claimed_at <= criteria.stale_claim_before
            )
        )

    async def find_awaiting_consent(self, criteria: ConsentRequestCriteria) -> list[User]:
        return [User(**vars(u)) for u in self.items.values() if self._is_awaiting(u, criteria)]

    async def claim_consent_request(
        self, telegram_id: int, criteria: ConsentRequestCriteria, now: datetime
    ) -> bool:
        user = self.items.get(telegram_id)
        if user is None or not self._is_awaiting(user, criteria):
            return False
        user.consent_claimed_at = now
        user.consent_attempts += 1
        return True

    async def complete_consent_request(self, telegram_id: int, now: datetime) -> None:
        user = self.items.get(telegram_id)
        if user and user.consent_requested_at is None:
            user.consent_requested_at = now
            user.consent_claimed_at = None

    async def abandon_consent_request(self, telegram_id: int, max_attempts: int) -> None:
        user = self.items.get(telegram_id)
        if user and user.consent_requested_at is None:
            user.consent_attempts = max_attempts
            user.consent_claimed_at = None

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


class InMemoryInteractionRepository(InteractionRepository):
    def __init__(self) -> None:
        self.items: dict[int, Interaction] = {}

    async def add(self, telegram_id: int, question: str, answer: str, now: datetime) -> Interaction:
        interaction = Interaction(
            id=len(self.items) + 1,
            telegram_id=telegram_id,
            question=question,
            answer=answer,
            created_at=now,
        )
        self.items[interaction.id] = interaction
        return Interaction(**vars(interaction))

    async def get(self, interaction_id: int) -> Interaction | None:
        interaction = self.items.get(interaction_id)
        return Interaction(**vars(interaction)) if interaction else None

    async def record_rating(
        self, interaction_id: int, telegram_id: int, rating: Rating, now: datetime
    ) -> bool:
        interaction = self.items.get(interaction_id)
        if interaction is None or interaction.telegram_id != telegram_id or interaction.rating:
            return False
        interaction.rating = rating
        return True

    async def redact_questions(self, telegram_id: int) -> None:
        for interaction in self.items.values():
            if interaction.telegram_id == telegram_id:
                interaction.question = ""

    async def delete_older_than(self, cutoff: datetime) -> int:
        old = [i for i, item in self.items.items() if item.created_at < cutoff]
        for interaction_id in old:
            del self.items[interaction_id]
        return len(old)


class FakeAnswerProvider(AnswerProvider):
    def __init__(self) -> None:
        self.calls: list[tuple[str, Language]] = []

    async def answer(self, question: str, language: Language) -> str:
        self.calls.append((question, language))
        return f"answer[{language.value}]: {question}"
