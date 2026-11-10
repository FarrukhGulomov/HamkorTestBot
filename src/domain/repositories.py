from abc import ABC, abstractmethod
from datetime import datetime

from src.domain.entities import Language, User


class UserRepository(ABC):
    """Barcha o'zgartiruvchi metodlar faqat o'ziga tegishli maydonlarni yangilaydi.
    Shunda parallel ishlayotgan jarayonlar bir-birining ma'lumotini bosib yozmaydi."""

    @abstractmethod
    async def get(self, telegram_id: int) -> User | None: ...

    @abstractmethod
    async def upsert_contact(
        self, telegram_id: int, phone_number: str, first_name: str, now: datetime
    ) -> User:
        """Yangi foydalanuvchini yaratadi. Mavjud bo'lsa, faqat telefon, ism
        va oxirgi faollik vaqtini yangilaydi."""

    @abstractmethod
    async def touch(self, telegram_id: int, now: datetime) -> None:
        """Oxirgi faollik vaqtini yangilaydi."""

    @abstractmethod
    async def set_language(self, telegram_id: int, language: Language) -> bool:
        """Tilni o'zgartiradi. Foydalanuvchi topilmasa False qaytaradi."""

    @abstractmethod
    async def find_awaiting_consent(self, idle_since: datetime) -> list[User]:
        """Til tanlagan, oxirgi xabari `idle_since` dan oldin yozilgan
        va hali roziligi so'ralmagan foydalanuvchilar."""

    @abstractmethod
    async def claim_consent_request(
        self, telegram_id: int, idle_since: datetime, now: datetime
    ) -> bool:
        """Rozilik so'rovini yuborish huquqini atomar egallaydi.
        Shartlar hamon bajarilsa True qaytaradi (foydalanuvchi shu orada yozgan,
        javob bergan yoki boshqa jarayon egallagan bo'lsa False)."""

    @abstractmethod
    async def release_consent_request(self, telegram_id: int) -> None:
        """Yuborib bo'lmagan so'rovni qaytaradi, keyingi tekshiruvda qayta uriniladi."""

    @abstractmethod
    async def record_consent(self, telegram_id: int, agreed: bool, now: datetime) -> bool:
        """Javobni faqat hali javob berilmagan bo'lsa saqlaydi. Saqlangan bo'lsa True."""
