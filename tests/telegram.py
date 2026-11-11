"""Soxta Telegram: yuborilgan so'rovlar ro'yxatga yig'iladi, yangilanishlar qo'lda yaratiladi."""
from datetime import UTC, datetime

from aiogram.client.session.base import BaseSession
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import EditMessageReplyMarkup, SendMessage, TelegramMethod
from aiogram.types import CallbackQuery, Chat, Contact, Message, Update
from aiogram.types import User as TgUser

CHAT = Chat(id=7, type="private")
TG_USER = TgUser(id=7, is_bot=False, first_name="Jasur")
GROUP = Chat(id=-100500, type="supergroup", title="Guruh")

_NEVER_EDITED = object()


class RecordingSession(BaseSession):
    """Telegram o'rniga turadi. `strict=True` bo'lsa, Telegram kabi bir xil klaviaturani
    qayta o'rnatishni "message is not modified" xatosi bilan rad etadi."""

    def __init__(self, strict: bool = False) -> None:
        super().__init__()
        self.requests: list[TelegramMethod] = []
        self._strict = strict
        self._markups: dict[tuple, object] = {}

    async def close(self) -> None: ...

    async def make_request(self, bot, method, timeout=None):
        self.requests.append(method)
        if self._strict and isinstance(method, EditMessageReplyMarkup):
            key = (method.chat_id, method.message_id)
            if self._markups.get(key, _NEVER_EDITED) == method.reply_markup:
                raise TelegramBadRequest(method=method, message="Bad Request: message is not modified")
            self._markups[key] = method.reply_markup
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

    def of_type(self, name: str) -> list[TelegramMethod]:
        return [m for m in self.requests if type(m).__name__ == name]


_update_id = 0


def next_id() -> int:
    global _update_id
    _update_id += 1
    return _update_id


def text_update(text: str, chat: Chat = CHAT) -> Update:
    message = Message(message_id=next_id(), date=datetime.now(UTC), chat=chat, from_user=TG_USER, text=text)
    return Update(update_id=next_id(), message=message)


def contact_update(phone: str, user_id: int = 7) -> Update:
    contact = Contact(phone_number=phone, first_name="Jasur", user_id=user_id)
    message = Message(message_id=next_id(), date=datetime.now(UTC), chat=CHAT, from_user=TG_USER, contact=contact)
    return Update(update_id=next_id(), message=message)


def callback_update(data: str, message_id: int | None = None) -> Update:
    """`message_id` berilsa, callback shu xabarga tegishli bo'ladi (bir xabardagi tugmani ikki marta bosish uchun)."""
    origin = Message(message_id=message_id or next_id(), date=datetime.now(UTC), chat=CHAT, text="...")
    callback = CallbackQuery(
        id=str(next_id()), from_user=TG_USER, chat_instance="x", data=data, message=origin
    )
    return Update(update_id=next_id(), callback_query=callback)
