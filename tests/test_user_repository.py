import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from src.application.ports import ConsentNotifier
from src.application.request_consent import RequestConsent
from src.domain.entities import ConsentStatus, Language, Rating, User
from src.domain.repositories import ConsentRequestCriteria
from src.infrastructure.db.session import create_engine, create_session_factory, create_tables
from src.infrastructure.db.interaction_repository import SqlAlchemyInteractionRepository
from src.infrastructure.db.user_repository import SqlAlchemyUserRepository
from tests.fakes import FakeClock

NOW = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
LEASE = timedelta(minutes=1)


def criteria(idle_since: datetime, now: datetime = NOW, max_attempts: int = 3) -> ConsentRequestCriteria:
    return ConsentRequestCriteria(idle_since, now - LEASE, max_attempts)


@pytest.fixture
async def repository(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await create_tables(engine)
    yield SqlAlchemyUserRepository(create_session_factory(engine))
    await engine.dispose()


async def test_upsert_and_get_roundtrip(repository):
    await repository.upsert_contact(1, "+998901234567", "Jasur", NOW)
    await repository.set_language(1, Language.ZH)

    user = await repository.get(1)

    assert user.phone_number == "+998901234567"
    assert user.language is Language.ZH
    assert user.last_message_at == NOW
    assert user.consent_status is ConsentStatus.PENDING


async def test_get_unknown_user_returns_none(repository):
    assert await repository.get(404) is None


async def test_upsert_contact_creates_then_updates_only_contact_fields(repository):
    await repository.upsert_contact(1, "+998901234567", "Jasur", NOW)
    await repository.set_language(1, Language.RU)
    await repository.record_consent(1, True, NOW)

    later = NOW + timedelta(minutes=1)
    user = await repository.upsert_contact(1, "+998907654321", "Jasurbek", later)

    assert user.phone_number == "+998907654321"
    assert user.first_name == "Jasurbek"
    assert user.last_message_at == later
    assert user.created_at == NOW
    assert user.language is Language.RU
    assert user.consent_status is ConsentStatus.AGREED


async def test_set_language_for_unknown_user_returns_false(repository):
    assert await repository.set_language(404, Language.UZ) is False


async def test_record_consent_only_once(repository):
    await repository.upsert_contact(1, "+998901234567", "Jasur", NOW)

    assert await repository.record_consent(1, True, NOW) is True
    assert await repository.record_consent(1, False, NOW) is False

    stored = await repository.get(1)
    assert stored.consent_status is ConsentStatus.AGREED
    assert stored.consent_answered_at == NOW


async def test_claim_is_exclusive_until_the_lease_expires(repository):
    await repository.upsert_contact(1, "+998901234567", "Jasur", NOW)
    await repository.set_language(1, Language.UZ)
    idle = NOW + timedelta(minutes=1)

    assert await repository.claim_consent_request(1, criteria(idle), NOW) is True
    assert await repository.claim_consent_request(1, criteria(idle), NOW) is False

    later = NOW + LEASE + timedelta(seconds=1)
    assert await repository.claim_consent_request(1, criteria(idle, later), later) is True
    assert (await repository.get(1)).consent_attempts == 2


async def test_completed_request_is_never_claimed_again(repository):
    await repository.upsert_contact(1, "+998901234567", "Jasur", NOW)
    await repository.set_language(1, Language.UZ)
    idle = NOW + timedelta(minutes=1)
    await repository.claim_consent_request(1, criteria(idle), NOW)

    await repository.complete_consent_request(1, NOW)

    later = NOW + timedelta(hours=1)
    stored = await repository.get(1)
    assert stored.consent_requested_at == NOW
    assert stored.consent_claimed_at is None
    assert await repository.claim_consent_request(1, criteria(idle, later), later) is False


async def test_attempts_are_capped(repository):
    await repository.upsert_contact(1, "+998901234567", "Jasur", NOW)
    await repository.set_language(1, Language.UZ)
    idle = NOW + timedelta(minutes=1)
    moment = NOW

    for _ in range(3):
        assert await repository.claim_consent_request(1, criteria(idle, moment), moment) is True
        moment += LEASE + timedelta(seconds=1)

    assert await repository.claim_consent_request(1, criteria(idle, moment), moment) is False


async def test_abandoned_request_is_not_claimed_again(repository):
    await repository.upsert_contact(1, "+998901234567", "Jasur", NOW)
    await repository.set_language(1, Language.UZ)
    idle = NOW + timedelta(minutes=1)
    await repository.claim_consent_request(1, criteria(idle), NOW)

    await repository.abandon_consent_request(1, max_attempts=3)

    later = NOW + timedelta(hours=1)
    assert await repository.claim_consent_request(1, criteria(idle, later), later) is False


async def test_claim_fails_when_user_wrote_after_selection(repository):
    await repository.upsert_contact(1, "+998901234567", "Jasur", NOW)
    await repository.set_language(1, Language.UZ)
    await repository.touch(1, NOW + timedelta(minutes=2))

    assert await repository.claim_consent_request(1, criteria(NOW + timedelta(minutes=1)), NOW) is False


async def test_old_database_without_new_columns_is_upgraded(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'old.db'}"
    engine = create_engine(url)
    async with engine.begin() as connection:
        await connection.execute(text(
            "CREATE TABLE users (telegram_id BIGINT PRIMARY KEY, phone_number VARCHAR(32), "
            "first_name VARCHAR(255), language VARCHAR(16), created_at DATETIME, "
            "last_message_at DATETIME, consent_status VARCHAR(16), "
            "consent_requested_at DATETIME, consent_answered_at DATETIME)"
        ))
        await connection.execute(text(
            "INSERT INTO users VALUES (1, '+998901234567', 'Jasur', 'uz', "
            "'2025-01-01 12:00:00', '2025-01-01 12:00:00', 'pending', '2025-01-01 12:05:00', NULL)"
        ))

    await create_tables(engine)

    repository = SqlAlchemyUserRepository(create_session_factory(engine))
    user = await repository.get(1)
    assert user.language is Language.UZ
    assert user.consent_requested_at == datetime(2025, 1, 1, 12, 5, tzinfo=UTC)
    assert user.consent_attempts == 0
    assert user.consent_claimed_at is None
    await engine.dispose()


class SlowNotifier(ConsentNotifier):
    """Yuborish davom etayotgan paytni modellashtiradi."""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.finish = asyncio.Event()

    async def send_consent_request(self, user: User) -> None:
        self.started.set()
        await self.finish.wait()


async def test_changes_made_while_request_is_being_sent_are_not_lost(repository):
    clock = FakeClock(NOW + timedelta(minutes=5))
    await repository.upsert_contact(1, "+998901234567", "Jasur", NOW)
    await repository.set_language(1, Language.UZ)
    notifier = SlowNotifier()
    use_case = RequestConsent(repository, notifier, clock, timedelta(minutes=3), claim_lease=LEASE)

    sending = asyncio.create_task(use_case.execute())
    await notifier.started.wait()

    # Xabar yuborilayotgan paytda foydalanuvchi til almashtirdi, yozdi va javob berdi
    later = NOW + timedelta(minutes=6)
    await repository.set_language(1, Language.EN)
    await repository.touch(1, later)
    await repository.record_consent(1, True, later)
    notifier.finish.set()
    await sending

    stored = await repository.get(1)
    assert stored.language is Language.EN
    assert stored.last_message_at == later
    assert stored.consent_status is ConsentStatus.AGREED
    assert stored.consent_answered_at == later


async def test_find_awaiting_consent_filters_users(repository):
    old = NOW - timedelta(minutes=5)

    async def add(telegram_id: int, language, last_message_at):
        await repository.upsert_contact(telegram_id, "+998901234567", "Jasur", last_message_at)
        if language:
            await repository.set_language(telegram_id, language)

    await add(1, Language.UZ, old)
    await add(2, Language.UZ, NOW + timedelta(minutes=1))
    await add(3, None, old)
    await add(4, Language.UZ, old)
    await repository.claim_consent_request(4, criteria(NOW), NOW)
    await add(5, Language.UZ, old)
    await repository.record_consent(5, True, NOW)

    found = await repository.find_awaiting_consent(criteria(NOW))

    assert [user.telegram_id for user in found] == [1]


async def test_interaction_is_stored_and_rated_once(repository, tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'interactions.db'}")
    await create_tables(engine)
    interactions = SqlAlchemyInteractionRepository(create_session_factory(engine))

    created = await interactions.add(7, "Omonat?", "Javob", NOW)
    assert created.id is not None and created.rating is None

    assert await interactions.record_rating(created.id, 7, Rating.LIKE, NOW) is True
    assert await interactions.record_rating(created.id, 7, Rating.DISLIKE, NOW) is False
    assert await interactions.record_rating(created.id, 8, Rating.DISLIKE, NOW) is False

    stored = await interactions.get(created.id)
    assert stored.rating is Rating.LIKE
    assert stored.question == "Omonat?"
    assert await interactions.get(999) is None
    await engine.dispose()


async def test_erase_personal_data_blanks_phone_and_name_only(repository):
    await repository.upsert_contact(1, "+998901234567", "Jasur", NOW)
    await repository.set_language(1, Language.RU)

    await repository.erase_personal_data(1)

    user = await repository.get(1)
    assert user.phone_number == "" and user.first_name == ""
    assert user.language is Language.RU and user.created_at == NOW


async def test_redact_questions_and_delete_older_than(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'retention.db'}")
    await create_tables(engine)
    interactions = SqlAlchemyInteractionRepository(create_session_factory(engine))
    old = await interactions.add(1, "eski savol", "javob", NOW - timedelta(days=40))
    mine = await interactions.add(1, "yangi savol", "javob", NOW)
    other = await interactions.add(2, "boshqaning savoli", "javob", NOW)
    await interactions.record_rating(mine.id, 1, Rating.LIKE, NOW)

    await interactions.redact_questions(1)

    assert (await interactions.get(mine.id)).question == ""
    assert (await interactions.get(mine.id)).rating is Rating.LIKE
    assert (await interactions.get(other.id)).question == "boshqaning savoli"

    deleted = await interactions.delete_older_than(NOW - timedelta(days=30))

    assert deleted == 1
    assert await interactions.get(old.id) is None
    assert await interactions.get(mine.id) is not None
    await engine.dispose()


async def test_simultaneous_first_contacts_create_a_single_user(repository):
    users = await asyncio.gather(
        *(repository.upsert_contact(5, "+998901234567", "Jasur", NOW) for _ in range(8))
    )

    assert all(user.telegram_id == 5 for user in users)
    assert (await repository.get(5)).phone_number == "+998901234567"


async def test_only_one_of_simultaneous_answers_is_recorded(repository):
    await repository.upsert_contact(5, "+998901234567", "Jasur", NOW)

    results = await asyncio.gather(
        repository.record_consent(5, True, NOW),
        repository.record_consent(5, False, NOW),
        repository.record_consent(5, True, NOW),
    )

    assert results.count(True) == 1


async def test_only_one_of_simultaneous_ratings_is_recorded(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'ratings.db'}")
    await create_tables(engine)
    interactions = SqlAlchemyInteractionRepository(create_session_factory(engine))
    created = await interactions.add(1, "q", "a", NOW)

    results = await asyncio.gather(
        *(interactions.record_rating(created.id, 1, Rating.LIKE, NOW) for _ in range(5))
    )

    assert results.count(True) == 1
    await engine.dispose()


def test_postgresql_engine_and_column_types_are_supported():
    from sqlalchemy.dialects import postgresql

    from src.infrastructure.db.models import UtcDateTime

    engine = create_engine("postgresql+asyncpg://user:password@localhost:5432/hamkor_bot")

    assert engine.dialect.name == "postgresql"
    assert "TIMESTAMP" in UtcDateTime().compile(dialect=postgresql.dialect())
