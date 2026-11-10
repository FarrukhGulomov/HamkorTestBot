from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


class UtcDateTime(TypeDecorator):
    """SQLite timezone'ni saqlamaydi, shuning uchun o'qiganda UTC qo'shib beramiz."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        return value.astimezone(UTC) if value is not None else None

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class Base(DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    phone_number: Mapped[str] = mapped_column(String(32))
    first_name: Mapped[str] = mapped_column(String(255))
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
    last_message_at: Mapped[datetime] = mapped_column(UtcDateTime(), index=True)
    consent_status: Mapped[str] = mapped_column(String(16), default="pending")
    consent_requested_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    consent_answered_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
