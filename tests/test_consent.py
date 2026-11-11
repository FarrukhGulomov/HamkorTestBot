from datetime import timedelta

import pytest

from src.application.answer_question import AnswerQuestion
from src.application.change_language import ChangeLanguage, UserNotFound
from src.application.ports import PermanentDeliveryError
from src.application.register_contact import RegisterContact
from src.application.request_consent import RequestConsent
from src.application.save_consent import SaveConsent
from src.application.track_activity import TrackActivity
from src.domain.entities import ConsentStatus, Language, Rating
from src.domain.repositories import ConsentRequestCriteria
from tests.fakes import FakeAnswerProvider, RecordingNotifier

IDLE = timedelta(minutes=3)


async def onboard(users, clock, telegram_id: int = 1) -> None:
    await RegisterContact(users, clock).execute(telegram_id, "+998901234567", "Jasur")
    await ChangeLanguage(users).execute(telegram_id, Language.UZ)


LEASE = timedelta(minutes=1)


def make_request_consent(users, clock, notifier, max_attempts: int = 5) -> RequestConsent:
    return RequestConsent(users, notifier, clock, IDLE, claim_lease=LEASE, max_attempts=max_attempts)


def criteria_at(clock, max_attempts: int = 5) -> ConsentRequestCriteria:
    now = clock.now()
    return ConsentRequestCriteria(now - IDLE, now - LEASE, max_attempts)


async def test_no_request_before_three_minutes(users, clock):
    await onboard(users, clock)
    notifier = RecordingNotifier()
    clock.advance(minutes=2, seconds=59)

    sent = await make_request_consent(users, clock, notifier).execute()

    assert sent == 0
    assert notifier.sent_to == []


async def test_request_sent_after_three_minutes_only_once(users, clock):
    await onboard(users, clock)
    notifier = RecordingNotifier()
    use_case = make_request_consent(users, clock, notifier)
    clock.advance(minutes=3)

    await use_case.execute()
    clock.advance(minutes=10)
    await use_case.execute()

    assert notifier.sent_to == [1]
    assert users.items[1].consent_requested_at is not None


async def test_new_message_postpones_the_request(users, clock):
    await onboard(users, clock)
    notifier = RecordingNotifier()
    clock.advance(minutes=2)
    await TrackActivity(users, clock).execute(1)
    clock.advance(minutes=2)

    await make_request_consent(users, clock, notifier).execute()
    assert notifier.sent_to == []

    clock.advance(minutes=1)
    await make_request_consent(users, clock, notifier).execute()
    assert notifier.sent_to == [1]


async def test_user_without_language_is_not_asked(users, clock):
    await RegisterContact(users, clock).execute(1, "+998901234567", "Jasur")
    notifier = RecordingNotifier()
    clock.advance(minutes=5)

    await make_request_consent(users, clock, notifier).execute()

    assert notifier.sent_to == []


async def test_transient_failure_is_retried_after_the_lease_expires(users, clock):
    await onboard(users, clock)
    notifier = RecordingNotifier(error=RuntimeError("network is down"))
    use_case = make_request_consent(users, clock, notifier)
    clock.advance(minutes=3)

    assert await use_case.execute() == 0
    notifier.error = None
    assert await use_case.execute() == 0  # egallash muddati hali tugamagan

    clock.advance(minutes=1, seconds=1)
    assert await use_case.execute() == 1
    assert notifier.sent_to == [1]
    assert users.items[1].consent_requested_at is not None
    assert users.items[1].consent_claimed_at is None


async def test_attempts_are_limited_even_across_restarts(users, clock):
    await onboard(users, clock)
    notifier = RecordingNotifier(error=RuntimeError("network is down"))
    clock.advance(minutes=3)

    for _ in range(3):
        # Har safar yangi obyekt: jarayon qayta ishga tushgandek
        await make_request_consent(users, clock, notifier, max_attempts=3).execute()
        clock.advance(minutes=2)

    notifier.error = None
    await make_request_consent(users, clock, notifier, max_attempts=3).execute()

    assert users.items[1].consent_attempts == 3
    assert notifier.sent_to == []


async def test_permanent_failure_is_not_retried(users, clock):
    await onboard(users, clock)
    notifier = RecordingNotifier(error=PermanentDeliveryError("bot was blocked"))
    use_case = make_request_consent(users, clock, notifier)
    clock.advance(minutes=3)

    await use_case.execute()
    notifier.error = None
    clock.advance(minutes=5)
    await use_case.execute()

    assert notifier.sent_to == []


async def test_request_is_recovered_after_the_process_died_mid_send(users, clock):
    await onboard(users, clock)
    clock.advance(minutes=3)
    # Jarayon so'rovni egalladi-yu, yuborishga ulgurmay to'xtadi
    assert await users.claim_consent_request(1, criteria_at(clock), clock.now()) is True
    notifier = RecordingNotifier()
    use_case = make_request_consent(users, clock, notifier)

    assert await use_case.execute() == 0  # muddat tugamaguncha boshqa jarayon aralashmaydi

    clock.advance(minutes=1, seconds=1)
    assert await use_case.execute() == 1
    assert notifier.sent_to == [1]


async def test_user_who_wrote_after_selection_is_skipped(users, clock):
    await onboard(users, clock)
    notifier = RecordingNotifier()
    use_case = make_request_consent(users, clock, notifier)
    clock.advance(minutes=3)
    criteria = criteria_at(clock)
    candidates = await users.find_awaiting_consent(criteria)
    # Tanlab olingandan keyin foydalanuvchi yozib yubordi
    await users.touch(1, clock.now())

    claimed = await users.claim_consent_request(1, criteria, clock.now())

    assert [u.telegram_id for u in candidates] == [1]
    assert claimed is False
    assert await use_case.execute() == 0


@pytest.mark.parametrize(
    ("agreed", "expected"),
    [(True, ConsentStatus.AGREED), (False, ConsentStatus.DECLINED)],
)
async def test_save_consent(users, interactions, clock, agreed, expected):
    await onboard(users, clock)

    user = await SaveConsent(users, interactions, clock).execute(1, agreed)

    assert user.consent_status is expected
    assert user.consent_answered_at == clock.now()


async def test_answered_consent_is_not_overwritten(users, interactions, clock):
    await onboard(users, clock)
    save_consent = SaveConsent(users, interactions, clock)
    await save_consent.execute(1, True)

    user = await save_consent.execute(1, False)

    assert user.consent_status is ConsentStatus.AGREED


async def test_save_consent_for_unknown_user_fails(users, interactions, clock):
    with pytest.raises(UserNotFound):
        await SaveConsent(users, interactions, clock).execute(99, True)


async def ask_and_answer(users, interactions, clock, question="Omonat ochmoqchiman"):
    await onboard(users, clock)
    return await AnswerQuestion(users, interactions, FakeAnswerProvider(), clock).execute(1, question)


async def test_declining_erases_phone_name_and_stored_questions(users, interactions, clock):
    interaction = await ask_and_answer(users, interactions, clock)
    await interactions.record_rating(interaction.id, 1, Rating.LIKE, clock.now())

    user = await SaveConsent(users, interactions, clock).execute(1, False)

    assert user.consent_status is ConsentStatus.DECLINED
    assert user.phone_number == "" and user.first_name == ""
    stored = interactions.items[interaction.id]
    assert stored.question == ""
    assert stored.rating is Rating.LIKE  # baho va javob statistika uchun qoladi


async def test_agreeing_keeps_personal_data(users, interactions, clock):
    interaction = await ask_and_answer(users, interactions, clock)

    user = await SaveConsent(users, interactions, clock).execute(1, True)

    assert user.phone_number == "+998901234567" and user.first_name == "Jasur"
    assert interactions.items[interaction.id].question == "Omonat ochmoqchiman"


async def test_questions_of_a_user_who_declined_are_not_stored(users, interactions, clock):
    await onboard(users, clock)
    await SaveConsent(users, interactions, clock).execute(1, False)

    interaction = await AnswerQuestion(users, interactions, FakeAnswerProvider(), clock).execute(
        1, "Mening kartam 8600 1234 5678 9012"
    )

    assert interaction.answer.endswith("Mening kartam 8600 1234 5678 9012")  # bot javob berishda davom etadi
    assert interactions.items[interaction.id].question == ""


async def test_sharing_the_contact_again_does_not_restore_declined_data(users, interactions, clock):
    await onboard(users, clock)
    await SaveConsent(users, interactions, clock).execute(1, False)

    user = await RegisterContact(users, clock).execute(1, "+998905556677", "Jasur")

    assert user.phone_number == ""
    assert users.items[1].phone_number == "" and users.items[1].first_name == ""


async def test_erasure_is_completed_by_a_repeated_press_after_an_interrupted_attempt(
    users, interactions, clock
):
    interaction = await ask_and_answer(users, interactions, clock)
    # Javob yozildi-yu, jarayon o'chirishga ulgurmay to'xtadi
    await users.record_consent(1, False, clock.now())
    assert users.items[1].phone_number == "+998901234567"

    await SaveConsent(users, interactions, clock).execute(1, False)

    assert users.items[1].phone_number == ""
    assert interactions.items[interaction.id].question == ""
