from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from src.infrastructure.db.models import Base, UserModel


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)


async def create_tables(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(_add_missing_columns)


def _add_missing_columns(connection: Connection) -> None:
    """create_all mavjud jadvalga yangi ustun qo'shmaydi. Eski bazalar ishlashda
    davom etishi uchun yetishmayotgan ustunlarni qo'lda qo'shamiz."""
    table = UserModel.__table__
    existing = {column["name"] for column in inspect(connection).get_columns(table.name)}

    for column in table.columns:
        if column.name in existing:
            continue
        column_type = column.type.compile(dialect=connection.dialect)
        default = f" NOT NULL DEFAULT {column.server_default.arg}" if column.server_default else ""
        connection.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {column.name} {column_type}{default}"))
