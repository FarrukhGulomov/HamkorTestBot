from src.domain.entities import User
from src.domain.repositories import UserRepository


class GetUser:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def execute(self, telegram_id: int) -> User | None:
        return await self._users.get(telegram_id)
