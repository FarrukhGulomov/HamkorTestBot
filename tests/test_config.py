import pytest
from pydantic import ValidationError

from src.config import Settings

TOKEN = "123456789:AAH-valid_token"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in (
        "BOT_TOKEN", "DATABASE_URL", "CONSENT_IDLE_SECONDS", "CONSENT_CHECK_INTERVAL_SECONDS",
        "INTERACTION_RETENTION_DAYS", "RATE_LIMIT_MAX_MESSAGES", "RATE_LIMIT_WINDOW_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)


def make_settings(**overrides) -> Settings:
    return Settings(_env_file=None, **{"bot_token": TOKEN, **overrides})


def test_defaults_match_the_requirements():
    settings = make_settings()

    assert settings.consent_idle_seconds == 180
    assert settings.consent_check_interval_seconds == 5
    assert settings.interaction_retention_days == 30
    assert settings.rate_limit_max_messages == 5
    assert settings.rate_limit_window_seconds == 10


def test_settings_are_read_from_environment(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", TOKEN)
    monkeypatch.setenv("CONSENT_IDLE_SECONDS", "15")

    settings = Settings(_env_file=None)

    assert settings.bot_token.get_secret_value() == TOKEN
    assert settings.consent_idle_seconds == 15


def test_token_is_hidden_in_repr_and_logs():
    settings = make_settings()

    assert TOKEN not in repr(settings)
    assert TOKEN not in str(settings)


@pytest.mark.parametrize("token", ["", "   ", "not-a-token", "123456:", ":abc", "123456:ab cd", '"123456:abc"'])
def test_malformed_token_is_rejected(token):
    with pytest.raises(ValidationError):
        make_settings(bot_token=token)


def test_missing_token_is_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    "name",
    [
        "consent_idle_seconds",
        "consent_check_interval_seconds",
        "interaction_retention_days",
        "rate_limit_max_messages",
        "rate_limit_window_seconds",
    ],
)
@pytest.mark.parametrize("value", [0, -1])
def test_non_positive_intervals_are_rejected(name, value):
    with pytest.raises(ValidationError):
        make_settings(**{name: value})


def test_invalid_token_is_not_echoed_in_the_error_message():
    with pytest.raises(ValidationError) as error:
        make_settings(bot_token="secret-typo-value")

    assert "secret-typo-value" not in str(error.value)
