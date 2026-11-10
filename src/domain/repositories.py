from abc import ABC, abstractmethod
from datetime import datetime

from src.domain.entities import User


class UserRepository(ABC):
    @abstractmethod
    async def get(self, telegram_id: int) -> User | None: ...

    @abstractmethod
    async def save(self, user: User) -> None:
        """Foydalanuvchini yaratadi yoki yangilaydi."""

    @abstractmethod
    async def find_awaiting_consent(self, idle_since: datetime) -> list[User]:
        """Til tanlagan, oxirgi xabari `idle_since` dan oldin yozilgan
        va hali roziligi so'ralmagan foydalanuvchilar."""
