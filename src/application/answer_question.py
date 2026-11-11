from src.application.change_language import UserNotFound
from src.application.ports import AnswerProvider, Clock
from src.domain.entities import ConsentStatus, Interaction
from src.domain.repositories import InteractionRepository, UserRepository

MAX_QUESTION_LENGTH = 1000


class AnswerQuestion:
    """Savolga foydalanuvchi tilida qisqa javob beradi va suhbatni baholash uchun saqlaydi.

    Savol matni MAX_QUESTION_LENGTH belgigacha qisqartiriladi. Rozilik rad etgan foydalanuvchining
    savol matni saqlanmaydi (bot unga javob berishda davom etadi)."""

    def __init__(
        self,
        users: UserRepository,
        interactions: InteractionRepository,
        provider: AnswerProvider,
        clock: Clock,
    ) -> None:
        self._users = users
        self._interactions = interactions
        self._provider = provider
        self._clock = clock

    async def execute(self, telegram_id: int, question: str) -> Interaction:
        user = await self._users.get(telegram_id)
        if user is None or user.language is None:
            raise UserNotFound(telegram_id)

        question = question[:MAX_QUESTION_LENGTH]
        answer = await self._provider.answer(question, user.language)
        stored_question = "" if user.consent_status is ConsentStatus.DECLINED else question
        return await self._interactions.add(telegram_id, stored_question, answer, self._clock.now())
