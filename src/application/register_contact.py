from src.application.ports import Clock
from src.domain.entities import User
from src.domain.repositories import UserRepository


class RegisterContact:
    """Telefon raqamini saqlaydi. Foydalanuvchi oldin ro'yxatdan o'tgan bo'lsa,
    mavjud yozuvni qaytaradi va raqamini yangilaydi."""

    def __init__(self, users: UserRepository, clock: Clock) -> None:
        self._users = users
        self._clock = clock

    async def execute(self, telegram_id: int, phone_number: str, first_name: str) -> User:
        now = self._clock.now()
        user = await self._users.get(telegram_id)

        if user is None:
            user = User(
                telegram_id=telegram_id,
                phone_number=_normalize_phone(phone_number),
                first_name=first_name,
                created_at=now,
                last_message_at=now,
            )
        else:
            user.phone_number = _normalize_phone(phone_number)
            user.first_name = first_name
            user.touch(now)

        await self._users.save(user)
        return user


def _normalize_phone(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    return f"+{digits}"
