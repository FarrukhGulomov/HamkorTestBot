import pytest

from tests.fakes import FakeClock, InMemoryUserRepository


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def users() -> InMemoryUserRepository:
    return InMemoryUserRepository()
