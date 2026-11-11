from datetime import datetime

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.domain.entities import Interaction, Rating
from src.domain.repositories import InteractionRepository
from src.infrastructure.db.models import InteractionModel


class SqlAlchemyInteractionRepository(InteractionRepository):
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def add(self, telegram_id: int, question: str, answer: str, now: datetime) -> Interaction:
        async with self._session_factory() as session:
            model = InteractionModel(
                telegram_id=telegram_id, question=question, answer=answer, created_at=now
            )
            session.add(model)
            await session.commit()
            return _to_entity(model)

    async def get(self, interaction_id: int) -> Interaction | None:
        async with self._session_factory() as session:
            model = await session.get(InteractionModel, interaction_id)
            return _to_entity(model) if model else None

    async def record_rating(
        self, interaction_id: int, telegram_id: int, rating: Rating, now: datetime
    ) -> bool:
        async with self._session_factory() as session:
            result = await session.execute(
                update(InteractionModel)
                .where(
                    InteractionModel.id == interaction_id,
                    InteractionModel.telegram_id == telegram_id,
                    InteractionModel.rating.is_(None),
                )
                .values(rating=rating.value, rated_at=now)
            )
            await session.commit()
            return result.rowcount > 0

    async def redact_questions(self, telegram_id: int) -> None:
        await self._execute(
            update(InteractionModel)
            .where(InteractionModel.telegram_id == telegram_id)
            .values(question="")
        )

    async def delete_older_than(self, cutoff: datetime) -> int:
        return await self._execute(delete(InteractionModel).where(InteractionModel.created_at < cutoff))

    async def _execute(self, statement) -> int:
        async with self._session_factory() as session:
            result = await session.execute(statement)
            await session.commit()
            return result.rowcount


def _to_entity(model: InteractionModel) -> Interaction:
    return Interaction(
        id=model.id,
        telegram_id=model.telegram_id,
        question=model.question,
        answer=model.answer,
        created_at=model.created_at,
        rating=Rating(model.rating) if model.rating else None,
    )
