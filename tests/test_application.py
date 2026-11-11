"""Haqiqiy ulash (composition root) va haqiqiy SQLite bazasi: boshidan oxirigacha."""
from datetime import timedelta

import pytest
from aiogram import Bot

from src.config import Settings
from src.domain.entities import ConsentStatus, Language, Rating
from src.infrastructure.db.interaction_repository import SqlAlchemyInteractionRepository
from src.infrastructure.db.session import create_session_factory
from src.infrastructure.db.user_repository import SqlAlchemyUserRepository
from src.infrastructure.i18n.translator import JsonTranslator
from src.main import build_application
from src.presentation.callbacks import ConsentCallback, LanguageCallback, RatingCallback
from tests.fakes import FakeClock
from tests.telegram import RecordingSession, callback_update, contact_update, text_update

USER_ID = 7


@pytest.fixture
def session() -> RecordingSession:
    return RecordingSession(strict=True)


@pytest.fixture
def bot(session) -> Bot:
    return Bot("123456:TEST", session=session)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
async def app(tmp_path, bot, clock):
    settings = Settings(
        _env_file=None,
        bot_token="123456:TEST",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'app.db'}",
        rate_limit_max_messages=1000,
    )
    application = await build_application(settings, bot, clock)
    yield application
    await application.engine.dispose()


@pytest.fixture
def users(app) -> SqlAlchemyUserRepository:
    return SqlAlchemyUserRepository(create_session_factory(app.engine))


@pytest.fixture
def interactions(app) -> SqlAlchemyInteractionRepository:
    return SqlAlchemyInteractionRepository(create_session_factory(app.engine))


async def feed(app, bot, update) -> None:
    await app.dispatcher.feed_update(bot, update)


async def onboard(app, bot, language: Language = Language.UZ) -> None:
    await feed(app, bot, text_update("/start"))
    await feed(app, bot, contact_update("998901234567"))
    await feed(app, bot, callback_update(LanguageCallback(language=language).pack()))


async def test_user_journey_from_start_to_agreed_consent(app, bot, session, clock, users, interactions):
    translator = JsonTranslator()
    await onboard(app, bot)
    await feed(app, bot, text_update("Omonat ochmoqchiman, foizi qancha?"))
    interaction_id = 1
    await feed(app, bot, callback_update(RatingCallback(interaction_id=interaction_id, positive=True).pack()))

    clock.advance(minutes=4)
    await app.jobs[0].run_once()  # rozilik so'rovlari
    assert session.sent_texts()[-1] == translator.get(Language.UZ, "consent_question")
    await feed(app, bot, callback_update(ConsentCallback(agreed=True).pack()))

    user = await users.get(USER_ID)
    assert user.phone_number == "+998901234567"
    assert user.language is Language.UZ
    assert user.consent_status is ConsentStatus.AGREED
    assert user.consent_requested_at is not None
    stored = await interactions.get(interaction_id)
    assert stored.question == "Omonat ochmoqchiman, foizi qancha?"
    assert stored.rating is Rating.LIKE


async def test_consent_is_not_requested_before_three_minutes(app, bot, session, clock):
    await onboard(app, bot)
    sent_before = len(session.sent_texts())

    clock.advance(minutes=2, seconds=59)
    await app.jobs[0].run_once()

    assert len(session.sent_texts()) == sent_before


async def test_declining_in_the_real_database_erases_personal_data(app, bot, clock, users, interactions):
    await onboard(app, bot)
    await feed(app, bot, text_update("Mening kartam 8600 1234 5678 9012"))
    clock.advance(minutes=4)
    await app.jobs[0].run_once()

    await feed(app, bot, callback_update(ConsentCallback(agreed=False).pack()))
    await feed(app, bot, text_update("Kredit olmoqchiman"))

    user = await users.get(USER_ID)
    assert user.consent_status is ConsentStatus.DECLINED
    assert user.phone_number == "" and user.first_name == ""
    assert (await interactions.get(1)).question == ""
    assert (await interactions.get(2)).question == ""


async def test_old_interactions_are_purged_by_the_background_job(app, bot, clock, interactions):
    await onboard(app, bot)
    await feed(app, bot, text_update("Omonat ochmoqchiman"))
    clock.advance(days=20)
    await feed(app, bot, text_update("Kredit olmoqchiman"))

    clock.advance(days=11)
    await app.jobs[1].run_once()  # eski savollarni o'chirish (30 kun)

    assert await interactions.get(1) is None
    assert await interactions.get(2) is not None


async def test_flood_is_limited_with_the_real_wiring(tmp_path, bot, session, clock):
    settings = Settings(
        _env_file=None,
        bot_token="123456:TEST",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'flood.db'}",
        rate_limit_max_messages=3,
        rate_limit_window_seconds=10,
    )
    application = await build_application(settings, bot, clock)
    await application.dispatcher.feed_update(bot, contact_update("998901234567"))
    await application.dispatcher.feed_update(bot, callback_update(LanguageCallback(language=Language.UZ).pack()))
    interactions = SqlAlchemyInteractionRepository(create_session_factory(application.engine))

    for _ in range(10):
        await application.dispatcher.feed_update(bot, text_update("Omonat ochmoqchiman"))

    assert await interactions.get(1) is not None
    assert await interactions.get(2) is None  # 3 ta harakatdan 2 tasi onboarding'ga ketgan
    await application.engine.dispose()


async def test_application_exposes_both_background_jobs(app):
    assert len(app.jobs) == 2
    assert app.dispatcher is not None and timedelta(seconds=1)
