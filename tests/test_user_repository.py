from datetime import UTC, datetime, timedelta

import pytest

from src.domain.entities import ConsentStatus, Language, User
from src.infrastructure.db.session import create_engine, create_session_factory, create_tables
from src.infrastructure.db.user_repository import SqlAlchemyUserRepository

NOW = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
async def repository():
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    await create_tables(engine)
    yield SqlAlchemyUserRepository(create_session_factory(engine))
    await engine.dispose()


def make_user(telegram_id: int = 1, **overrides) -> User:
    fields = dict(
        telegram_id=telegram_id,
        phone_number="+998901234567",
        first_name="Jasur",
        created_at=NOW,
        last_message_at=NOW,
    )
    return User(**{**fields, **overrides})


async def test_save_and_get_roundtrip(repository):
    await repository.save(make_user(language=Language.ZH))

    user = await repository.get(1)

    assert user.language is Language.ZH
    assert user.last_message_at == NOW
    assert user.consent_status is ConsentStatus.PENDING


async def test_get_unknown_user_returns_none(repository):
    assert await repository.get(404) is None


async def test_save_updates_existing_user(repository):
    user = make_user()
    await repository.save(user)
    user.choose_language(Language.RU)
    user.answer_consent(True, NOW)

    await repository.save(user)

    stored = await repository.get(1)
    assert stored.language is Language.RU
    assert stored.consent_status is ConsentStatus.AGREED
    assert stored.consent_answered_at == NOW


async def test_find_awaiting_consent_filters_users(repository):
    idle_since = NOW
    old = NOW - timedelta(minutes=5)
    await repository.save(make_user(1, language=Language.UZ, last_message_at=old))
    await repository.save(make_user(2, language=Language.UZ, last_message_at=NOW + timedelta(minutes=1)))
    await repository.save(make_user(3, language=None, last_message_at=old))
    await repository.save(make_user(4, language=Language.UZ, last_message_at=old, consent_requested_at=old))
    await repository.save(
        make_user(5, language=Language.UZ, last_message_at=old, consent_status=ConsentStatus.AGREED)
    )

    found = await repository.find_awaiting_consent(idle_since)

    assert [user.telegram_id for user in found] == [1]
