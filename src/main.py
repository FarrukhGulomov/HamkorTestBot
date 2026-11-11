import asyncio
import logging
from datetime import timedelta

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from src.application.answer_question import AnswerQuestion
from src.application.change_language import ChangeLanguage
from src.application.get_user import GetUser
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
from src.infrastructure.scheduler import ConsentScheduler
from src.presentation.handlers import build_root_router
from src.presentation.middlewares import ActivityMiddleware, PrivateChatOnlyMiddleware
from src.presentation.notifier import TelegramConsentNotifier


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
        save_consent=SaveConsent(users, clock),
        answer_question=AnswerQuestion(users, interactions, FaqAnswerProvider(), clock),
        rate_answer=RateAnswer(interactions, clock),
    )
    private_only = PrivateChatOnlyMiddleware()
    dispatcher.message.outer_middleware(private_only)
    dispatcher.callback_query.outer_middleware(private_only)
    dispatcher.message.outer_middleware(ActivityMiddleware(track_activity))
    dispatcher.include_router(build_root_router())

    scheduler = ConsentScheduler(request_consent, settings.consent_check_interval_seconds)
    scheduler.start()
    try:
        await dispatcher.start_polling(bot)
    finally:
        await scheduler.stop()
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
