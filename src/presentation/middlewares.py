from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Dispatcher
from aiogram.enums import ChatType
from aiogram.types import CallbackQuery, Message, TelegramObject

from src.application.ports import RateLimiter
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


class ThrottlingMiddleware(BaseMiddleware):
    """Foydalanuvchi bo'yicha tezlik cheklovi: limitdan oshgan xabarlar va tugma bosishlar
    e'tiborsiz qoldiriladi (bazaga ham tegilmaydi)."""

    def __init__(self, rate_limiter: RateLimiter) -> None:
        self._rate_limiter = rate_limiter

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = event.from_user if isinstance(event, Message | CallbackQuery) else None
        if user is not None and not self._rate_limiter.allow(user.id):
            if isinstance(event, CallbackQuery):
                await event.answer()  # tugmadagi "yuklanmoqda" belgisi yo'qolishi uchun
            return None
        return await handler(event, data)


def install_middlewares(
    dispatcher: Dispatcher, track_activity: TrackActivity, rate_limiter: RateLimiter
) -> None:
    """Tartib muhim: avval chat turi, keyin tezlik cheklovi, oxirida faollikni yozish."""
    private_only = PrivateChatOnlyMiddleware()
    throttling = ThrottlingMiddleware(rate_limiter)
    for observer in (dispatcher.message, dispatcher.callback_query):
        observer.outer_middleware(private_only)
        observer.outer_middleware(throttling)
    dispatcher.message.outer_middleware(ActivityMiddleware(track_activity))
