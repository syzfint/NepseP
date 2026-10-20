"""
PostgreSQL / SQLite Async & Sync SQLAlchemy Engine & Session Factory for Apex Wealth PMS.
Supports institutional PostgreSQL (`postgresql+asyncpg://...`) with lazy async engine
instantiation, built-in `sqlite3` synchronous fallback, and a zero-dependency in-memory
fallback so models and the server run in any Python environment even when `sqlalchemy`
is not installed.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional

try:
    from sqlalchemy import create_engine
    from sqlalchemy.ext.asyncio import (
        AsyncEngine,
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )
    from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

    HAS_SQLALCHEMY = True

    class Base(DeclarativeBase):
        """Declarative base for all Apex Wealth ORM domain models."""
        pass

except ImportError:
    HAS_SQLALCHEMY = False
    AsyncEngine = Any  # type: ignore[assignment,misc]
    AsyncSession = Any  # type: ignore[assignment,misc]
    Session = Any  # type: ignore[assignment,misc]

    class _DummyMetadata:
        @staticmethod
        def create_all(*args: Any, **kwargs: Any) -> None:
            pass

    class Base:  # type: ignore[no-redef]
        """Lightweight fallback base class when SQLAlchemy is not installed."""
        metadata = _DummyMetadata()

        def __init__(self, **kwargs: Any) -> None:
            for k, v in kwargs.items():
                setattr(self, k, v)


DEFAULT_ASYNC_DATABASE_URL = os.getenv(
    "APEX_WEALTH_DATABASE_URL",
    "postgresql+asyncpg://apex:apex@localhost:5432/apex_wealth",
)

DEFAULT_SYNC_DATABASE_URL = os.getenv(
    "APEX_WEALTH_SYNC_DATABASE_URL",
    "sqlite:///./apex_wealth_pms.db",
)


def build_async_engine(database_url: str = DEFAULT_ASYNC_DATABASE_URL) -> Optional[Any]:
    """Create an AsyncEngine configured for PostgreSQL (asyncpg) or SQLite (aiosqlite)."""
    if not HAS_SQLALCHEMY:
        return None
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    try:
        return create_async_engine(
            database_url,
            echo=False,
            future=True,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
    except Exception:
        return None


def build_sync_engine(database_url: str = DEFAULT_SYNC_DATABASE_URL) -> Optional[Any]:
    """Create a synchronous SQLAlchemy Engine using standard library sqlite3 or psycopg2."""
    if not HAS_SQLALCHEMY:
        return None
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_engine(
        database_url,
        echo=False,
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


async_engine: Optional[Any] = build_async_engine()
AsyncSessionLocal = (
    async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    if (HAS_SQLALCHEMY and async_engine is not None)
    else None
)

sync_engine = build_sync_engine()
SyncSessionLocal = (
    sessionmaker(
        bind=sync_engine,
        class_=Session,
        expire_on_commit=False,
        autoflush=False,
    )
    if (HAS_SQLALCHEMY and sync_engine is not None)
    else None
)


def init_sync_db(engine: Any = sync_engine) -> None:
    """Initialize all database tables synchronously."""
    from . import models  # noqa: F401

    if HAS_SQLALCHEMY and engine is not None:
        Base.metadata.create_all(bind=engine)


async def init_db(engine: Optional[Any] = async_engine) -> None:
    """Initialize all database tables defined on Base.metadata (with sync/in-memory fallback)."""
    from . import models  # noqa: F401

    if not HAS_SQLALCHEMY:
        return
    if engine is not None:
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            return
        except Exception:
            pass
    init_sync_db(sync_engine)


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[Any, None]:
    """Async context manager yielding a transactional AsyncSession."""
    if AsyncSessionLocal is None:
        raise RuntimeError("Async DB driver not installed; use SyncSessionLocal or install asyncpg/aiosqlite.")
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db() -> AsyncGenerator[Any, None]:
    """FastAPI dependency injection generator for AsyncSession."""
    async with get_db_session() as session:
        yield session
