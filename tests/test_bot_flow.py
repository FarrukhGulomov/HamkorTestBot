"""Handlerlar, middleware va use case'lar birga ishlashini tekshiradi.
Telegram o'rniga soxta sessiya ishlatiladi: yuborilgan so'rovlar ro'yxatga yig'iladi."""
from datetime import UTC, datetime, timedelta

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.methods import SendMessage, TelegramMethod
from aiogram.types import Chat, Contact, Message, Update, User as TgUser, CallbackQuery

from src.application.answer_question import AnswerQuestion
from src.application.change_language import ChangeLanguage
from src.application.get_user import GetUser
from src.application.rate_answer import RateAnswer
from src.application.register_contact import RegisterContact
from src.application.request_consent import RequestConsent
from src.application.save_consent import SaveConsent
from src.application.track_activity import TrackActivity
from src.domain.entities import ConsentStatus, Language, Rating
from src.infrastructure.faq.answer_provider import FaqAnswerProvider
from src.infrastructure.i18n.translator import JsonTranslator
from src.presentation.callbacks import ConsentCallback, LanguageCallback, RatingCallback
from src.presentation.handlers import build_root_router
from src.infrastructure.rate_limiter import InMemoryRateLimiter
from src.presentation.middlewares import install_middlewares
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
def translator() -> JsonTranslator:
    return JsonTranslator()


@pytest.fixture
def dispatcher(users, interactions, clock, translator) -> Dispatcher:
    dp = Dispatcher()
    dp.workflow_data.update(
        translator=translator,
        get_user=GetUser(users),
        register_contact=RegisterContact(users, clock),
        change_language=ChangeLanguage(users),
        save_consent=SaveConsent(users, interactions, clock),
        answer_question=AnswerQuestion(users, interactions, FaqAnswerProvider(), clock),
        rate_answer=RateAnswer(interactions, clock),
    )
    generous_limiter = InMemoryRateLimiter(clock, max_events=1000, window=timedelta(seconds=10))
    install_middlewares(dp, TrackActivity(users, clock), generous_limiter)
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


async def test_typed_phone_number_is_rejected_and_button_is_requested(
    dispatcher, bot, session, users, translator
):
    await dispatcher.feed_update(bot, text_update("/start"))

    await dispatcher.feed_update(bot, text_update("+656565"))

    assert session.sent_texts()[-1] == translator.get(Language.UZ, "confirm_phone_by_button")
    assert session.requests[-1].reply_markup.keyboard[0][0].request_contact is True
    assert users.items == {}


async def test_text_before_choosing_language_shows_language_choice(
    dispatcher, bot, session, translator
):
    await dispatcher.feed_update(bot, contact_update("998901234567"))

    await dispatcher.feed_update(bot, text_update("salom"))

    assert session.sent_texts()[-1] == translator.get(Language.UZ, "choose_language")


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


async def onboard(dispatcher, bot, language: Language) -> None:
    await dispatcher.feed_update(bot, contact_update("998901234567"))
    await dispatcher.feed_update(bot, callback_update(LanguageCallback(language=language).pack()))


async def test_question_gets_short_answer_with_rating_buttons(
    dispatcher, bot, session, interactions, translator
):
    await onboard(dispatcher, bot, Language.UZ)

    await dispatcher.feed_update(bot, text_update("Omonat ochmoqchiman, foizi qancha?"))

    answer = session.sent_texts()[-1]
    assert "Hamkorbankda bir nechta omonat turi mavjud" in answer
    buttons = session.requests[-1].reply_markup.inline_keyboard[0]
    assert [b.text for b in buttons] == ["👍", "👎"]
    assert len(interactions.items) == 1


async def test_answer_follows_the_selected_language(dispatcher, bot, session):
    await onboard(dispatcher, bot, Language.RU)

    await dispatcher.feed_update(bot, text_update("Omonat ochmoqchiman"))

    assert "видов вкладов" in session.sent_texts()[-1]


async def test_rating_is_saved_and_confirmed(dispatcher, bot, session, interactions):
    await onboard(dispatcher, bot, Language.UZ)
    await dispatcher.feed_update(bot, text_update("Kredit olmoqchiman"))
    interaction_id = next(iter(interactions.items))

    await dispatcher.feed_update(
        bot, callback_update(RatingCallback(interaction_id=interaction_id, positive=False).pack())
    )

    assert interactions.items[interaction_id].rating is Rating.DISLIKE
    toast = [m for m in session.requests if type(m).__name__ == "AnswerCallbackQuery"][-1]
    assert toast.text == "Rahmat, bahoyingiz qabul qilindi!"
    edited = [m for m in session.requests if type(m).__name__ == "EditMessageReplyMarkup"][-1]
    assert [b.text for b in edited.reply_markup.inline_keyboard[0]] == ["👍", "✓ 👎"]


async def test_non_text_message_asks_for_text(dispatcher, bot, session, translator):
    await onboard(dispatcher, bot, Language.UZ)
    message = Message(message_id=_next_id(), date=datetime.now(UTC), chat=CHAT, from_user=TG_USER)

    await dispatcher.feed_update(bot, Update(update_id=_next_id(), message=message))

    assert session.sent_texts()[-1] == translator.get(Language.UZ, "text_only")


GROUP = Chat(id=-100500, type="supergroup", title="Guruh")


async def test_messages_in_group_chats_are_ignored(dispatcher, bot, session, users):
    await onboard(dispatcher, bot, Language.UZ)
    requests_before = len(session.requests)
    last_seen = users.items[7].last_message_at

    for text in ("/start", "/settings", "Omonat ochmoqchiman"):
        message = Message(message_id=_next_id(), date=datetime.now(UTC), chat=GROUP, from_user=TG_USER, text=text)
        await dispatcher.feed_update(bot, Update(update_id=_next_id(), message=message))

    assert len(session.requests) == requests_before
    assert users.items[7].last_message_at == last_seen


async def test_button_presses_in_group_chats_are_ignored(dispatcher, bot, session, users, interactions):
    await onboard(dispatcher, bot, Language.UZ)
    requests_before = len(session.requests)
    origin = Message(message_id=_next_id(), date=datetime.now(UTC), chat=GROUP, text="...")
    callback = CallbackQuery(
        id=str(_next_id()), from_user=TG_USER, chat_instance="x", message=origin,
        data=ConsentCallback(agreed=True).pack(),
    )

    await dispatcher.feed_update(bot, Update(update_id=_next_id(), callback_query=callback))

    assert len(session.requests) == requests_before
    assert users.items[7].consent_status is ConsentStatus.PENDING


def build_dispatcher(users, interactions, clock, translator, max_events: int) -> Dispatcher:
    dp = Dispatcher()
    dp.workflow_data.update(
        translator=translator,
        get_user=GetUser(users),
        register_contact=RegisterContact(users, clock),
        change_language=ChangeLanguage(users),
        save_consent=SaveConsent(users, interactions, clock),
        answer_question=AnswerQuestion(users, interactions, FaqAnswerProvider(), clock),
        rate_answer=RateAnswer(interactions, clock),
    )
    limiter = InMemoryRateLimiter(clock, max_events=max_events, window=timedelta(seconds=10))
    install_middlewares(dp, TrackActivity(users, clock), limiter)
    dp.include_router(build_root_router())
    return dp


async def test_flood_of_messages_is_cut_off_by_the_rate_limit(
    bot, session, users, interactions, clock, translator
):
    dp = build_dispatcher(users, interactions, clock, translator, max_events=4)
    await onboard(dp, bot, Language.UZ)  # 2 ta harakat

    for _ in range(10):
        await dp.feed_update(bot, text_update("Omonat ochmoqchiman"))

    assert len(interactions.items) == 2  # limitga 2 ta joy qolgan edi

    clock.advance(seconds=11)
    await dp.feed_update(bot, text_update("Omonat ochmoqchiman"))
    assert len(interactions.items) == 3


async def test_throttled_button_press_is_acknowledged_but_not_processed(
    bot, session, users, interactions, clock, translator
):
    dp = build_dispatcher(users, interactions, clock, translator, max_events=2)
    await onboard(dp, bot, Language.UZ)

    await dp.feed_update(bot, callback_update(ConsentCallback(agreed=False).pack()))

    assert users.items[7].consent_status is ConsentStatus.PENDING
    assert type(session.requests[-1]).__name__ == "AnswerCallbackQuery"


async def test_declining_consent_through_the_bot_erases_the_data(dispatcher, bot, users, interactions):
    await onboard(dispatcher, bot, Language.UZ)
    await dispatcher.feed_update(bot, text_update("Omonat ochmoqchiman"))
    assert next(iter(interactions.items.values())).question == "Omonat ochmoqchiman"

    await dispatcher.feed_update(bot, callback_update(ConsentCallback(agreed=False).pack()))

    assert users.items[7].phone_number == "" and users.items[7].first_name == ""
    assert next(iter(interactions.items.values())).question == ""
