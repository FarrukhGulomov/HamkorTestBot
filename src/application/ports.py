from abc import ABC, abstractmethod
from datetime import datetime

from src.domain.entities import User


class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime:
        """Joriy vaqt (UTC, timezone bilan)."""


class PermanentDeliveryError(Exception):
    """Xabarni yetkazib bo'lmaydi va qayta urinish foyda bermaydi (masalan, bot bloklangan)."""


class ConsentNotifier(ABC):
    @abstractmethod
    async def send_consent_request(self, user: User) -> None:
        """Foydalanuvchiga rozilik so'rovini yuboradi.
        Qayta urinish foyda bermaydigan xatoda PermanentDeliveryError ko'taradi."""
