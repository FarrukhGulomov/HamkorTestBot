import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from src.application.ports import ConsentNotifier
from src.application.request_consent import RequestConsent
from src.domain.entities import ConsentStatus, Language, User
from src.infrastructure.db.session import create_engine, create_session_factory, create_tables
from src.infrastructure.db.user_repository import SqlAlchemyUserRepository
from tests.fakes import FakeClock

NOW = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)


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


async def test_claim_is_exclusive_and_release_allows_retry(repository):
    await repository.upsert_contact(1, "+998901234567", "Jasur", NOW)
    await repository.set_language(1, Language.UZ)
    idle_since = NOW + timedelta(minutes=1)

    assert await repository.claim_consent_request(1, idle_since, NOW) is True
    assert await repository.claim_consent_request(1, idle_since, NOW) is False

    await repository.release_consent_request(1)
    assert await repository.claim_consent_request(1, idle_since, NOW) is True


async def test_claim_fails_when_user_wrote_after_selection(repository):
    await repository.upsert_contact(1, "+998901234567", "Jasur", NOW)
    await repository.set_language(1, Language.UZ)
    await repository.touch(1, NOW + timedelta(minutes=2))

    assert await repository.claim_consent_request(1, NOW + timedelta(minutes=1), NOW) is False


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
    use_case = RequestConsent(repository, notifier, clock, timedelta(minutes=3))

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
    await repository.claim_consent_request(4, NOW, NOW)
    await add(5, Language.UZ, old)
    await repository.record_consent(5, True, NOW)

    found = await repository.find_awaiting_consent(NOW)

    assert [user.telegram_id for user in found] == [1]
