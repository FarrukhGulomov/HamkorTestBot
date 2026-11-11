from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.enums import ChatType
from aiogram.types import CallbackQuery, Message, TelegramObject

from src.application.track_activity import TrackActivity


class PrivateChatOnlyMiddleware(BaseMiddleware):
    """Bot faqat shaxsiy suhbatda ishlaydi: guruh va kanallardagi xabarlar e'tiborsiz qoldiriladi.
    Telefon raqamini ulashish tugmasi ham faqat shaxsiy suhbatda ishlaydi."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if _chat_type(event) != ChatType.PRIVATE:
            return None
        return await handler(event, data)


def _chat_type(event: TelegramObject) -> ChatType | None:
    if isinstance(event, Message):
        return event.chat.type
    if isinstance(event, CallbackQuery) and event.message is not None:
        return event.message.chat.type
    return None


class ActivityMiddleware(BaseMiddleware):
    """Foydalanuvchi har safar yozganda oxirgi faollik vaqtini yangilaydi."""

    def __init__(self, track_activity: TrackActivity) -> None:
        self._track_activity = track_activity

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        if event.from_user is not None:
            await self._track_activity.execute(event.from_user.id)
        return await handler(event, data)
