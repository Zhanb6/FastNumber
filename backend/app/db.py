"""Async SQLAlchemy engine and session factory."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_config

engine = create_async_engine(
    get_config().database_url,
    pool_size=10,
    max_overflow=20,
    pool_timeout=60,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session() as session:
        yield session
