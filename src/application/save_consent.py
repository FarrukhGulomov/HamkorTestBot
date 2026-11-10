from src.application.change_language import UserNotFound
from src.application.ports import Clock
from src.domain.entities import User
from src.domain.repositories import UserRepository


class SaveConsent:
    """Foydalanuvchi javobini saqlaydi. Javob berilgan bo'lsa, o'zgartirilmaydi."""

    def __init__(self, users: UserRepository, clock: Clock) -> None:
        self._users = users
        self._clock = clock

    async def execute(self, telegram_id: int, agreed: bool) -> User:
        if await self._users.get(telegram_id) is None:
            raise UserNotFound(telegram_id)

        await self._users.record_consent(telegram_id, agreed, self._clock.now())

        user = await self._users.get(telegram_id)
        if user is None:
            raise UserNotFound(telegram_id)
        return user
