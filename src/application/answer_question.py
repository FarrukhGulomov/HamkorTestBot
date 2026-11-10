from src.application.change_language import UserNotFound
from src.application.ports import AnswerProvider, Clock
from src.domain.entities import Interaction
from src.domain.repositories import InteractionRepository, UserRepository


class AnswerQuestion:
    """Savolga foydalanuvchi tilida qisqa javob beradi va suhbatni baholash uchun saqlaydi."""

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

        answer = await self._provider.answer(question, user.language)
        return await self._interactions.add(telegram_id, question, answer, self._clock.now())
