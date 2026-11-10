from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from src.domain.entities import Interaction, Language, Rating, User


@dataclass(frozen=True)
class ConsentRequestCriteria:
    """Rozilik so'rovi yuborilishi mumkin bo'lgan foydalanuvchilarni tanlash shartlari."""

    idle_since: datetime
    """Oxirgi xabari shu vaqtdan oldin yozilgan bo'lishi kerak."""
    stale_claim_before: datetime
    """Shu vaqtdan oldin egallangan, ammo yakunlanmagan so'rov eskirgan hisoblanadi."""
    max_attempts: int
    """Shuncha marta uringandan keyin foydalanuvchiga qayta urinilmaydi."""


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
    async def find_awaiting_consent(self, criteria: ConsentRequestCriteria) -> list[User]:
        """Til tanlagan, roziligi hali so'ralmagan va shartlarga mos foydalanuvchilar."""

    @abstractmethod
    async def claim_consent_request(
        self, telegram_id: int, criteria: ConsentRequestCriteria, now: datetime
    ) -> bool:
        """Rozilik so'rovini yuborish huquqini atomar egallaydi va urinishlar sonini oshiradi.
        Shartlar hamon bajarilsa True qaytaradi (foydalanuvchi shu orada yozgan, javob bergan
        yoki boshqa jarayon egallagan bo'lsa False). Egallash vaqtincha: yakunlanmasa,
        `stale_claim_before` dan keyin so'rov qayta olinadi."""

    @abstractmethod
    async def complete_consent_request(self, telegram_id: int, now: datetime) -> None:
        """So'rov yetkazilganini belgilaydi."""

    @abstractmethod
    async def abandon_consent_request(self, telegram_id: int, max_attempts: int) -> None:
        """Yetkazib bo'lmaydigan so'rovga qayta urinishni to'xtatadi."""

    @abstractmethod
    async def record_consent(self, telegram_id: int, agreed: bool, now: datetime) -> bool:
        """Javobni faqat hali javob berilmagan bo'lsa saqlaydi. Saqlangan bo'lsa True."""


class InteractionRepository(ABC):
    @abstractmethod
    async def add(self, telegram_id: int, question: str, answer: str, now: datetime) -> Interaction: ...

    @abstractmethod
    async def get(self, interaction_id: int) -> Interaction | None: ...

    @abstractmethod
    async def record_rating(
        self, interaction_id: int, telegram_id: int, rating: Rating, now: datetime
    ) -> bool:
        """Bahoni faqat shu foydalanuvchining hali baholanmagan javobiga yozadi.
        Saqlangan bo'lsa True qaytaradi."""
