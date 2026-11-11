from abc import ABC, abstractmethod
from datetime import datetime

from src.domain.entities import Language, User


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


class Translator(ABC):
    @abstractmethod
    def get(self, language: Language, key: str, **params: object) -> str:
        """Kalitning berilgan tildagi matni; topilmasa standart tildagisi."""

    @abstractmethod
    def all_translations(self, key: str) -> set[str]:
        """Bitta kalitning barcha tillardagi matnlari (tugma matnini aniqlash uchun)."""


class AnswerProvider(ABC):
    """Savolga qisqa javob beruvchi manba (hozir FAQ, keyin LLM bilan almashtirish mumkin)."""

    @abstractmethod
    async def answer(self, question: str, language: Language) -> str: ...


class RateLimiter(ABC):
    @abstractmethod
    def allow(self, key: int) -> bool:
        """Kalit (foydalanuvchi) uchun yana bir harakatga ruxsat bormi.
        Ruxsat berilsa, harakat hisobga olinadi."""
