from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message

from src.application.track_activity import TrackActivity


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
