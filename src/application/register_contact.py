from src.application.ports import Clock
from src.domain.entities import User
from src.domain.repositories import UserRepository


class RegisterContact:
    """Telefon raqamini saqlaydi. Foydalanuvchi oldin ro'yxatdan o'tgan bo'lsa,
    faqat raqami va ismi yangilanadi (tili va roziligi saqlanib qoladi)."""

    def __init__(self, users: UserRepository, clock: Clock) -> None:
        self._users = users
        self._clock = clock

    async def execute(self, telegram_id: int, phone_number: str, first_name: str) -> User:
        return await self._users.upsert_contact(
            telegram_id=telegram_id,
            phone_number=_normalize_phone(phone_number),
            first_name=first_name,
            now=self._clock.now(),
        )


def _normalize_phone(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    return f"+{digits}"
