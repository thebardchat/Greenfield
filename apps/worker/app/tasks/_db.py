"""Shared database session factory for arq worker tasks."""

import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_engine = None
_Session: async_sessionmaker[AsyncSession] | None = None

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://claimcruncher:claimcruncher@localhost:5433/claimcruncher",
)


def get_session() -> async_sessionmaker[AsyncSession]:
    global _engine, _Session
    if _Session is None:
        _engine = create_async_engine(DATABASE_URL, pool_size=5, max_overflow=10)
        _Session = async_sessionmaker(_engine, expire_on_commit=False)
    return _Session
