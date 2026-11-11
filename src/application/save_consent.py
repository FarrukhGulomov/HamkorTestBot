from dataclasses import dataclass

from src.application.change_language import UserNotFound
from src.application.ports import Clock
from src.domain.entities import ConsentStatus, User
from src.domain.repositories import InteractionRepository, UserRepository


@dataclass(frozen=True)
class ConsentResult:
    user: User
    recorded: bool
    """Javob aynan shu chaqiruvda saqlandimi (False: avval berilgan, masalan tugma ikki marta bosilgan)."""


class SaveConsent:
    """Foydalanuvchi javobini saqlaydi. Javob berilgan bo'lsa, o'zgartirilmaydi.

    Rozilik rad etilsa, telefon raqami, ism va avval saqlangan savol matnlari o'chiriladi.
    O'chirish takrorlanganda ham zarar qilmaydi: jarayon o'rtada to'xtab qolgan bo'lsa,
    keyingi bosishda yakunlanadi."""

    def __init__(
        self, users: UserRepository, interactions: InteractionRepository, clock: Clock
    ) -> None:
        self._users = users
        self._interactions = interactions
        self._clock = clock

    async def execute(self, telegram_id: int, agreed: bool) -> ConsentResult:
        if await self._users.get(telegram_id) is None:
            raise UserNotFound(telegram_id)

        recorded = await self._users.record_consent(telegram_id, agreed, self._clock.now())

        user = await self._users.get(telegram_id)
        if user is None:
            raise UserNotFound(telegram_id)

        if user.consent_status is ConsentStatus.DECLINED:
            await self._users.erase_personal_data(telegram_id)
            await self._interactions.redact_questions(telegram_id)
            user = await self._users.get(telegram_id) or user
        return ConsentResult(user=user, recorded=recorded)
