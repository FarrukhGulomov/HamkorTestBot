from dataclasses import dataclass, replace

from src.domain.entities import Language, User
from src.domain.repositories import UserRepository


class UserNotFound(Exception):
    pass


@dataclass(frozen=True)
class LanguageChangeResult:
    user: User
    is_first_choice: bool


class ChangeLanguage:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def execute(self, telegram_id: int, language: Language) -> LanguageChangeResult:
        user = await self._users.get(telegram_id)
        if user is None:
            raise UserNotFound(telegram_id)

        if not await self._users.set_language(telegram_id, language):
            raise UserNotFound(telegram_id)

        return LanguageChangeResult(
            user=replace(user, language=language),
            is_first_choice=not user.is_onboarded,
        )
