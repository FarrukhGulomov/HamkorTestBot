import pytest

from tests.fakes import FakeAnswerProvider, FakeClock, InMemoryInteractionRepository, InMemoryUserRepository


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def users() -> InMemoryUserRepository:
    return InMemoryUserRepository()


@pytest.fixture
def interactions() -> InMemoryInteractionRepository:
    return InMemoryInteractionRepository()


@pytest.fixture
def provider() -> FakeAnswerProvider:
    return FakeAnswerProvider()
