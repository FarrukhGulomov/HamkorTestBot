from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.domain.entities import ConsentStatus, Language, User
from src.domain.repositories import UserRepository
from src.infrastructure.db.models import UserModel


class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def get(self, telegram_id: int) -> User | None:
        async with self._session_factory() as session:
            model = await session.get(UserModel, telegram_id)
            return _to_entity(model) if model else None

    async def save(self, user: User) -> None:
        async with self._session_factory() as session:
            model = await session.get(UserModel, user.telegram_id)
            if model is None:
                model = UserModel(telegram_id=user.telegram_id)
                session.add(model)
            _fill_model(model, user)
            await session.commit()

    async def find_awaiting_consent(self, idle_since: datetime) -> list[User]:
        query = select(UserModel).where(
            UserModel.language.is_not(None),
            UserModel.consent_status == ConsentStatus.PENDING.value,
            UserModel.consent_requested_at.is_(None),
            UserModel.last_message_at <= idle_since,
        )
        async with self._session_factory() as session:
            result = await session.scalars(query)
            return [_to_entity(model) for model in result]


def _to_entity(model: UserModel) -> User:
    return User(
        telegram_id=model.telegram_id,
        phone_number=model.phone_number,
        first_name=model.first_name,
        created_at=model.created_at,
        last_message_at=model.last_message_at,
        language=Language(model.language) if model.language else None,
        consent_status=ConsentStatus(model.consent_status),
        consent_requested_at=model.consent_requested_at,
        consent_answered_at=model.consent_answered_at,
    )


def _fill_model(model: UserModel, user: User) -> None:
    model.phone_number = user.phone_number
    model.first_name = user.first_name
    model.language = user.language.value if user.language else None
    model.created_at = user.created_at
    model.last_message_at = user.last_message_at
    model.consent_status = user.consent_status.value
    model.consent_requested_at = user.consent_requested_at
    model.consent_answered_at = user.consent_answered_at
