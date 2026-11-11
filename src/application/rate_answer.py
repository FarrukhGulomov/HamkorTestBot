from dataclasses import dataclass

from src.application.ports import Clock
from src.domain.entities import Interaction, Rating
from src.domain.repositories import InteractionRepository


class InteractionNotFound(Exception):
    pass


@dataclass(frozen=True)
class RatingResult:
    interaction: Interaction
    recorded: bool
    """Baho aynan shu chaqiruvda saqlandimi (False: avval berilgan, masalan tugma ikki marta bosilgan)."""


class RateAnswer:
    """Foydalanuvchi bahosini saqlaydi. Baho berilgan bo'lsa, o'zgartirilmaydi."""

    def __init__(self, interactions: InteractionRepository, clock: Clock) -> None:
        self._interactions = interactions
        self._clock = clock

    async def execute(self, telegram_id: int, interaction_id: int, rating: Rating) -> RatingResult:
        interaction = await self._interactions.get(interaction_id)
        if interaction is None or interaction.telegram_id != telegram_id:
            raise InteractionNotFound(interaction_id)

        recorded = await self._interactions.record_rating(
            interaction_id, telegram_id, rating, self._clock.now()
        )

        rated = await self._interactions.get(interaction_id)
        if rated is None:
            raise InteractionNotFound(interaction_id)
        return RatingResult(interaction=rated, recorded=recorded)
