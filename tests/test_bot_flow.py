"""Handlerlar, middleware va use case'lar birga ishlashini tekshiradi.
Telegram o'rniga soxta sessiya ishlatiladi: yuborilgan so'rovlar ro'yxatga yig'iladi."""
from datetime import UTC, datetime, timedelta

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.methods import SendMessage, TelegramMethod
from aiogram.types import Chat, Contact, Message, Update, User as TgUser, CallbackQuery

from src.application.change_language import ChangeLanguage
from src.application.get_user import GetUser
from src.application.register_contact import RegisterContact
from src.application.request_consent import RequestConsent
from src.application.save_consent import SaveConsent
from src.application.track_activity import TrackActivity
from src.domain.entities import ConsentStatus, Language
from src.infrastructure.i18n.translator import Translator
from src.presentation.callbacks import ConsentCallback, LanguageCallback
from src.presentation.handlers import build_root_router
from src.presentation.middlewares import ActivityMiddleware
from src.presentation.notifier import TelegramConsentNotifier

CHAT = Chat(id=7, type="private")
TG_USER = TgUser(id=7, is_bot=False, first_name="Jasur")


class RecordingSession(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list[TelegramMethod] = []

    async def close(self) -> None: ...

    async def make_request(self, bot, method, timeout=None):
        self.requests.append(method)
        if isinstance(method, SendMessage):
            return Message(
                message_id=len(self.requests),
                date=datetime.now(UTC),
                chat=CHAT,
                text=method.text,
            )
        return True

    async def stream_content(self, *args, **kwargs):
        yield b""

    def sent_texts(self) -> list[str]:
        return [m.text for m in self.requests if isinstance(m, SendMessage)]


@pytest.fixture
def session() -> RecordingSession:
    return RecordingSession()


@pytest.fixture
def bot(session) -> Bot:
    return Bot("123456:TEST", session=session)


@pytest.fixture
def translator() -> Translator:
    return Translator()


@pytest.fixture
def dispatcher(users, clock, translator) -> Dispatcher:
    dp = Dispatcher()
    dp.workflow_data.update(
        translator=translator,
        get_user=GetUser(users),
        register_contact=RegisterContact(users, clock),
        change_language=ChangeLanguage(users),
        save_consent=SaveConsent(users, clock),
    )
    dp.message.outer_middleware(ActivityMiddleware(TrackActivity(users, clock)))
    dp.include_router(build_root_router())
    return dp


_update_id = 0


def _next_id() -> int:
    global _update_id
    _update_id += 1
    return _update_id


def text_update(text: str) -> Update:
    message = Message(message_id=_next_id(), date=datetime.now(UTC), chat=CHAT, from_user=TG_USER, text=text)
    return Update(update_id=_next_id(), message=message)


def contact_update(phone: str, user_id: int = 7) -> Update:
    contact = Contact(phone_number=phone, first_name="Jasur", user_id=user_id)
    message = Message(message_id=_next_id(), date=datetime.now(UTC), chat=CHAT, from_user=TG_USER, contact=contact)
    return Update(update_id=_next_id(), message=message)


def callback_update(data: str) -> Update:
    origin = Message(message_id=_next_id(), date=datetime.now(UTC), chat=CHAT, text="...")
    callback = CallbackQuery(id=str(_next_id()), from_user=TG_USER, chat_instance="x", data=data, message=origin)
    return Update(update_id=_next_id(), callback_query=callback)


async def test_full_onboarding_flow(dispatcher, bot, session, users, translator):
    await dispatcher.feed_update(bot, text_update("/start"))
    first_message = session.sent_texts()[-1]
    assert first_message.startswith(translator.get(Language.UZ, "start_greeting"))
    assert first_message.endswith(translator.get(Language.UZ, "ask_phone"))

    await dispatcher.feed_update(bot, contact_update("998901234567"))
    assert session.sent_texts()[-1] == translator.get(Language.UZ, "choose_language")
    assert users.items[7].phone_number == "+998901234567"

    await dispatcher.feed_update(bot, callback_update(LanguageCallback(language=Language.RU).pack()))
    assert session.sent_texts()[-1] == translator.get(Language.RU, "welcome")
    assert users.items[7].language is Language.RU


async def test_foreign_contact_is_rejected(dispatcher, bot, session, users, translator):
    await dispatcher.feed_update(bot, contact_update("998901234567", user_id=999))

    assert session.sent_texts()[-1] == translator.get(Language.UZ, "phone_not_own")
    assert users.items == {}


async def test_language_can_be_changed_from_settings(dispatcher, bot, session, users, translator):
    await dispatcher.feed_update(bot, contact_update("998901234567"))
    await dispatcher.feed_update(bot, callback_update(LanguageCallback(language=Language.UZ).pack()))

    await dispatcher.feed_update(bot, text_update(translator.get(Language.UZ, "settings_button")))
    assert session.sent_texts()[-1] == translator.get(Language.UZ, "settings_title")

    await dispatcher.feed_update(bot, callback_update(LanguageCallback(language=Language.EN).pack()))
    assert session.sent_texts()[-1] == translator.get(Language.EN, "language_changed")
    assert users.items[7].language is Language.EN


async def test_settings_command_works_too(dispatcher, bot, session, users, translator):
    await dispatcher.feed_update(bot, contact_update("998901234567"))
    await dispatcher.feed_update(bot, callback_update(LanguageCallback(language=Language.ZH).pack()))

    await dispatcher.feed_update(bot, text_update("/settings"))

    assert session.sent_texts()[-1] == translator.get(Language.ZH, "settings_title")


async def test_idle_user_gets_consent_request_and_answer_is_saved(
    dispatcher, bot, session, users, clock, translator
):
    await dispatcher.feed_update(bot, contact_update("998901234567"))
    await dispatcher.feed_update(bot, callback_update(LanguageCallback(language=Language.UZ).pack()))
    clock.advance(minutes=3, seconds=1)

    request_consent = RequestConsent(
        users, TelegramConsentNotifier(bot, translator), clock, timedelta(minutes=3)
    )
    await request_consent.execute()
    assert session.sent_texts()[-1] == translator.get(Language.UZ, "consent_question")

    await dispatcher.feed_update(bot, callback_update(ConsentCallback(agreed=True).pack()))

    assert users.items[7].consent_status is ConsentStatus.AGREED
    assert session.sent_texts()[-1] == translator.get(Language.UZ, "consent_thanks_yes")


async def test_message_from_unregistered_user_asks_to_start(dispatcher, bot, session, translator):
    await dispatcher.feed_update(bot, text_update("salom"))

    assert session.sent_texts()[-1] == translator.get(Language.UZ, "need_start")


async def test_start_for_registered_user_greets_in_their_language(
    dispatcher, bot, session, translator
):
    await dispatcher.feed_update(bot, contact_update("998901234567"))
    await dispatcher.feed_update(bot, callback_update(LanguageCallback(language=Language.RU).pack()))

    await dispatcher.feed_update(bot, text_update("/start"))

    assert session.sent_texts()[-2:] == [
        translator.get(Language.RU, "start_greeting"),
        translator.get(Language.RU, "welcome"),
    ]
