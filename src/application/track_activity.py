from src.application.ports import Clock
from src.domain.repositories import UserRepository


class TrackActivity:
    """Foydalanuvchining oxirgi yozgan vaqtini yangilaydi."""

    def __init__(self, users: UserRepository, clock: Clock) -> None:
        self._users = users
        self._clock = clock

    async def execute(self, telegram_id: int) -> None:
        user = await self._users.get(telegram_id)
        if user is None:
            return
        user.touch(self._clock.now())
        await self._users.save(user)
