import pytest

from src.application.change_language import ChangeLanguage, UserNotFound
from src.application.register_contact import RegisterContact
from src.domain.entities import Language


async def test_register_contact_creates_user_and_normalizes_phone(users, clock):
    use_case = RegisterContact(users, clock)

    user = await use_case.execute(1, "998901234567", "Jasur")

    assert user.phone_number == "+998901234567"
    assert user.first_name == "Jasur"
    assert user.language is None
    assert await users.get(1) is user


async def test_register_contact_twice_keeps_single_user(users, clock):
    use_case = RegisterContact(users, clock)
    await use_case.execute(1, "+998901234567", "Jasur")

    await use_case.execute(1, "+998907654321", "Jasur")

    assert len(users.items) == 1
    assert users.items[1].phone_number == "+998907654321"


async def test_first_language_choice_is_marked(users, clock):
    await RegisterContact(users, clock).execute(1, "+998901234567", "Jasur")
    change_language = ChangeLanguage(users)

    first = await change_language.execute(1, Language.RU)
    second = await change_language.execute(1, Language.EN)

    assert first.is_first_choice is True
    assert second.is_first_choice is False
    assert users.items[1].language is Language.EN


async def test_change_language_for_unknown_user_fails(users):
    with pytest.raises(UserNotFound):
        await ChangeLanguage(users).execute(42, Language.UZ)
