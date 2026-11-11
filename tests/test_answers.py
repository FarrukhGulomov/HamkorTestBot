from datetime import timedelta

import pytest

from src.application.answer_question import MAX_QUESTION_LENGTH, AnswerQuestion
from src.application.purge_old_interactions import PurgeOldInteractions
from src.application.change_language import ChangeLanguage, UserNotFound
from src.application.rate_answer import InteractionNotFound, RateAnswer
from src.application.register_contact import RegisterContact
from src.domain.entities import Language, Rating


async def onboard(users, clock, telegram_id: int = 1, language: Language = Language.RU) -> None:
    await RegisterContact(users, clock).execute(telegram_id, "+998901234567", "Jasur")
    await ChangeLanguage(users).execute(telegram_id, language)


async def test_answer_is_given_in_the_users_language_and_stored(users, interactions, provider, clock):
    await onboard(users, clock, language=Language.RU)
    use_case = AnswerQuestion(users, interactions, provider, clock)

    interaction = await use_case.execute(1, "Omonat ochmoqchiman")

    assert provider.calls == [("Omonat ochmoqchiman", Language.RU)]
    assert interaction.answer == "answer[ru]: Omonat ochmoqchiman"
    assert interaction.rating is None
    assert interactions.items[interaction.id].question == "Omonat ochmoqchiman"


async def test_user_without_language_cannot_ask(users, interactions, provider, clock):
    await RegisterContact(users, clock).execute(1, "+998901234567", "Jasur")

    with pytest.raises(UserNotFound):
        await AnswerQuestion(users, interactions, provider, clock).execute(1, "salom")


async def test_unknown_user_cannot_ask(users, interactions, provider, clock):
    with pytest.raises(UserNotFound):
        await AnswerQuestion(users, interactions, provider, clock).execute(404, "salom")


async def test_rating_is_saved(users, interactions, provider, clock):
    await onboard(users, clock)
    interaction = await AnswerQuestion(users, interactions, provider, clock).execute(1, "q")

    rated = await RateAnswer(interactions, clock).execute(1, interaction.id, Rating.LIKE)

    assert rated.rating is Rating.LIKE


async def test_rating_cannot_be_changed(users, interactions, provider, clock):
    await onboard(users, clock)
    interaction = await AnswerQuestion(users, interactions, provider, clock).execute(1, "q")
    rate = RateAnswer(interactions, clock)
    await rate.execute(1, interaction.id, Rating.LIKE)

    rated = await rate.execute(1, interaction.id, Rating.DISLIKE)

    assert rated.rating is Rating.LIKE


async def test_user_cannot_rate_someone_elses_answer(users, interactions, provider, clock):
    await onboard(users, clock, telegram_id=1)
    interaction = await AnswerQuestion(users, interactions, provider, clock).execute(1, "q")

    with pytest.raises(InteractionNotFound):
        await RateAnswer(interactions, clock).execute(2, interaction.id, Rating.DISLIKE)

    assert interactions.items[interaction.id].rating is None


async def test_rating_unknown_answer_fails(interactions, clock):
    with pytest.raises(InteractionNotFound):
        await RateAnswer(interactions, clock).execute(1, 999, Rating.LIKE)


async def test_overlong_question_is_truncated_before_storing(users, interactions, provider, clock):
    await onboard(users, clock)

    interaction = await AnswerQuestion(users, interactions, provider, clock).execute(1, "a" * 5000)

    assert len(interactions.items[interaction.id].question) == MAX_QUESTION_LENGTH
    assert len(provider.calls[0][0]) == MAX_QUESTION_LENGTH


async def test_old_interactions_are_purged_and_recent_ones_kept(users, interactions, provider, clock):
    await onboard(users, clock)
    answer = AnswerQuestion(users, interactions, provider, clock)
    old = await answer.execute(1, "eski savol")
    clock.advance(days=20)
    recent = await answer.execute(1, "yangi savol")
    clock.advance(days=11)  # eski savol 31 kunlik, yangisi 11 kunlik

    purged = await PurgeOldInteractions(interactions, clock, timedelta(days=30)).execute()

    assert purged == 1
    assert old.id not in interactions.items
    assert recent.id in interactions.items


async def test_purge_with_nothing_to_delete_returns_zero(interactions, clock):
    assert await PurgeOldInteractions(interactions, clock, timedelta(days=30)).execute() == 0
