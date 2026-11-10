from dataclasses import dataclass

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

        is_first_choice = not user.is_onboarded
        user.choose_language(language)
        await self._users.save(user)
        return LanguageChangeResult(user=user, is_first_choice=is_first_choice)
