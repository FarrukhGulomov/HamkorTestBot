from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    bot_token: str
    database_url: str = "sqlite+aiosqlite:///./hamkor_bot.db"
    consent_idle_seconds: int = 180
    consent_check_interval_seconds: int = 5
