import asyncio
import logging
from datetime import timedelta

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from src.application.answer_question import AnswerQuestion
from src.application.change_language import ChangeLanguage
from src.application.get_user import GetUser
from src.application.purge_old_interactions import PurgeOldInteractions
from src.application.rate_answer import RateAnswer
from src.application.register_contact import RegisterContact
from src.application.request_consent import RequestConsent
from src.application.save_consent import SaveConsent
from src.application.track_activity import TrackActivity
from src.config import Settings
from src.infrastructure.clock import SystemClock
from src.infrastructure.db.interaction_repository import SqlAlchemyInteractionRepository
from src.infrastructure.db.session import create_engine, create_session_factory, create_tables
from src.infrastructure.db.user_repository import SqlAlchemyUserRepository
from src.infrastructure.faq.answer_provider import FaqAnswerProvider
from src.infrastructure.i18n.translator import JsonTranslator
from src.infrastructure.rate_limiter import InMemoryRateLimiter
from src.infrastructure.scheduler import PeriodicJob
from src.presentation.handlers import build_root_router
from src.presentation.middlewares import install_middlewares
from src.presentation.notifier import TelegramConsentNotifier

PURGE_INTERVAL_SECONDS = 3600


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = Settings()

    engine = create_engine(settings.database_url)
    await create_tables(engine)

    clock = SystemClock()
    translator = JsonTranslator()
    session_factory = create_session_factory(engine)
    users = SqlAlchemyUserRepository(session_factory)
    interactions = SqlAlchemyInteractionRepository(session_factory)

    bot = Bot(settings.bot_token.get_secret_value(), default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    track_activity = TrackActivity(users, clock)
    request_consent = RequestConsent(
        users=users,
        notifier=TelegramConsentNotifier(bot, translator),
        clock=clock,
        idle_timeout=timedelta(seconds=settings.consent_idle_seconds),
    )

    dispatcher = Dispatcher()
    dispatcher.workflow_data.update(
        translator=translator,
        get_user=GetUser(users),
        register_contact=RegisterContact(users, clock),
        change_language=ChangeLanguage(users),
        save_consent=SaveConsent(users, interactions, clock),
        answer_question=AnswerQuestion(users, interactions, FaqAnswerProvider(), clock),
        rate_answer=RateAnswer(interactions, clock),
    )
    rate_limiter = InMemoryRateLimiter(
        clock,
        max_events=settings.rate_limit_max_messages,
        window=timedelta(seconds=settings.rate_limit_window_seconds),
    )
    install_middlewares(dispatcher, track_activity, rate_limiter)
    dispatcher.include_router(build_root_router())

    purge = PurgeOldInteractions(
        interactions, clock, timedelta(days=settings.interaction_retention_days)
    )
    jobs = [
        PeriodicJob("Rozilik so'rovlari", request_consent.execute, settings.consent_check_interval_seconds),
        PeriodicJob("Eski savollarni o'chirish", purge.execute, PURGE_INTERVAL_SECONDS),
    ]
    for job in jobs:
        job.start()
    try:
        await dispatcher.start_polling(bot)
    finally:
        for job in jobs:
            await job.stop()
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
