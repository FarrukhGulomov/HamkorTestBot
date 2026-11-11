from datetime import datetime

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.domain.entities import ConsentStatus, Language, User
from src.domain.repositories import ConsentRequestCriteria, UserRepository
from src.infrastructure.db.models import UserModel

PENDING = ConsentStatus.PENDING.value


class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def get(self, telegram_id: int) -> User | None:
        async with self._session_factory() as session:
            model = await session.get(UserModel, telegram_id)
            return _to_entity(model) if model else None

    async def upsert_contact(
        self, telegram_id: int, phone_number: str, first_name: str, now: datetime
    ) -> User:
        try:
            return await self._upsert_contact_once(telegram_id, phone_number, first_name, now)
        except IntegrityError:
            # Bir vaqtda kelgan ikkinchi so'rov yozuvni oldinroq yaratib ulgurdi: endi u mavjud,
            # shuning uchun yangilash sifatida qayta bajariladi
            return await self._upsert_contact_once(telegram_id, phone_number, first_name, now)

    async def _upsert_contact_once(
        self, telegram_id: int, phone_number: str, first_name: str, now: datetime
    ) -> User:
        async with self._session_factory() as session:
            model = await session.get(UserModel, telegram_id)
            if model is None:
                model = UserModel(
                    telegram_id=telegram_id,
                    created_at=now,
                    consent_status=PENDING,
                )
                session.add(model)
            model.phone_number = phone_number
            model.first_name = first_name
            model.last_message_at = now
            await session.commit()
            return _to_entity(model)

    async def touch(self, telegram_id: int, now: datetime) -> None:
        await self._execute(
            update(UserModel).where(UserModel.telegram_id == telegram_id).values(last_message_at=now)
        )

    async def erase_personal_data(self, telegram_id: int) -> None:
        await self._execute(
            update(UserModel)
            .where(UserModel.telegram_id == telegram_id)
            .values(phone_number="", first_name="")
        )

    async def set_language(self, telegram_id: int, language: Language) -> bool:
        result = await self._execute(
            update(UserModel)
            .where(UserModel.telegram_id == telegram_id)
            .values(language=language.value)
        )
        return result > 0

    async def find_awaiting_consent(self, criteria: ConsentRequestCriteria) -> list[User]:
        query = select(UserModel).where(*_awaiting_consent(criteria))
        async with self._session_factory() as session:
            result = await session.scalars(query)
            return [_to_entity(model) for model in result]

    async def claim_consent_request(
        self, telegram_id: int, criteria: ConsentRequestCriteria, now: datetime
    ) -> bool:
        claimed = await self._execute(
            update(UserModel)
            .where(UserModel.telegram_id == telegram_id, *_awaiting_consent(criteria))
            .values(consent_claimed_at=now, consent_attempts=UserModel.consent_attempts + 1)
        )
        return claimed > 0

    async def complete_consent_request(self, telegram_id: int, now: datetime) -> None:
        await self._execute(
            update(UserModel)
            .where(UserModel.telegram_id == telegram_id, UserModel.consent_requested_at.is_(None))
            .values(consent_requested_at=now, consent_claimed_at=None)
        )

    async def abandon_consent_request(self, telegram_id: int, max_attempts: int) -> None:
        await self._execute(
            update(UserModel)
            .where(UserModel.telegram_id == telegram_id, UserModel.consent_requested_at.is_(None))
            .values(consent_attempts=max_attempts, consent_claimed_at=None)
        )

    async def record_consent(self, telegram_id: int, agreed: bool, now: datetime) -> bool:
        status = ConsentStatus.AGREED if agreed else ConsentStatus.DECLINED
        recorded = await self._execute(
            update(UserModel)
            .where(UserModel.telegram_id == telegram_id, UserModel.consent_status == PENDING)
            .values(consent_status=status.value, consent_answered_at=now)
        )
        return recorded > 0

    async def _execute(self, statement) -> int:
        """UPDATE bajaradi va o'zgargan qatorlar sonini qaytaradi."""
        async with self._session_factory() as session:
            result = await session.execute(statement)
            await session.commit()
            return result.rowcount


def _awaiting_consent(criteria: ConsentRequestCriteria) -> tuple:
    return (
        UserModel.language.is_not(None),
        UserModel.consent_status == PENDING,
        UserModel.consent_requested_at.is_(None),
        UserModel.consent_attempts < criteria.max_attempts,
        UserModel.last_message_at <= criteria.idle_since,
        or_(
            UserModel.consent_claimed_at.is_(None),
            UserModel.consent_claimed_at <= criteria.stale_claim_before,
        ),
    )


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
        consent_claimed_at=model.consent_claimed_at,
        consent_attempts=model.consent_attempts or 0,
    )
