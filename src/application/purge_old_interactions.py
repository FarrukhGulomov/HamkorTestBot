from datetime import timedelta

from src.application.ports import Clock
from src.domain.repositories import InteractionRepository


class PurgeOldInteractions:
    """Saqlash muddati o'tgan savol-javoblarni o'chiradi."""

    def __init__(self, interactions: InteractionRepository, clock: Clock, retention: timedelta) -> None:
        self._interactions = interactions
        self._clock = clock
        self._retention = retention

    async def execute(self) -> int:
        """O'chirilgan yozuvlar sonini qaytaradi."""
        return await self._interactions.delete_older_than(self._clock.now() - self._retention)
