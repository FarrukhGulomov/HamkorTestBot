from datetime import timedelta

import pytest

from src.application.change_language import ChangeLanguage, UserNotFound
from src.application.ports import PermanentDeliveryError
from src.application.register_contact import RegisterContact
from src.application.request_consent import RequestConsent
from src.application.save_consent import SaveConsent
from src.application.track_activity import TrackActivity
from src.domain.entities import ConsentStatus, Language
from src.domain.repositories import ConsentRequestCriteria
from tests.fakes import RecordingNotifier

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
async def test_save_consent(users, clock, agreed, expected):
    await onboard(users, clock)

    user = await SaveConsent(users, clock).execute(1, agreed)

    assert user.consent_status is expected
    assert user.consent_answered_at == clock.now()


async def test_answered_consent_is_not_overwritten(users, clock):
    await onboard(users, clock)
    save_consent = SaveConsent(users, clock)
    await save_consent.execute(1, True)

    user = await save_consent.execute(1, False)

    assert user.consent_status is ConsentStatus.AGREED


async def test_save_consent_for_unknown_user_fails(users, clock):
    with pytest.raises(UserNotFound):
        await SaveConsent(users, clock).execute(99, True)
