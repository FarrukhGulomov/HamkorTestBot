import re

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

TOKEN_PATTERN = re.compile(r"^\d+:[A-Za-z0-9_-]+$")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", hide_input_in_errors=True
    )

    bot_token: SecretStr
    database_url: str = "sqlite+aiosqlite:///./hamkor_bot.db"
    consent_idle_seconds: int = Field(default=180, ge=1)
    consent_check_interval_seconds: int = Field(default=5, ge=1)

    @field_validator("bot_token")
    @classmethod
    def token_must_look_like_a_telegram_token(cls, token: SecretStr) -> SecretStr:
        if not TOKEN_PATTERN.match(token.get_secret_value()):
            raise ValueError("BOT_TOKEN noto'g'ri: '123456789:AAH...' ko'rinishida bo'lishi kerak")
        return token
