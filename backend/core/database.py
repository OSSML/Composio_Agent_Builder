"""Database manager with LangGraph integration"""

import os
from typing import Any

import structlog
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.store.sqlite.aio import AsyncSqliteStore
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from core.config import settings

logger = structlog.get_logger(__name__)


class DatabaseManager:
    """Manages database connections and LangGraph persistence components"""

    def __init__(self) -> None:
        self.engine: AsyncEngine | None = None
        self._checkpointer: AsyncSqliteSaver | None = None
        self._checkpointer_cm: Any = None  # holds the contextmanager so we can close it
        self._store: AsyncSqliteStore | None = None
        self._store_cm: Any = None
        self._database_url = settings.DATABASE_URL

    async def initialize(self) -> None:
        """Initialize database connections and LangGraph components"""
        # SQLAlchemy for our minimal Agent Protocol metadata tables
        self.engine = create_async_engine(
            self._database_url,
        )

        dsn = self._database_url.replace("sqlite+aiosqlite:///", "")
        # Store connection string for creating LangGraph components on demand
        self._langgraph_dsn = dsn
        self.checkpointer = None
        self.store = None
        # Note: LangGraph components will be created as context managers when needed

        # Note: Database schema is now managed by Alembic migrations
        # Run 'alembic upgrade head' to apply migrations

        logger.info("✅ Database and LangGraph components initialized")

    async def close(self) -> None:
        """Close database connections"""
        if self.engine:
            await self.engine.dispose()

        # Close the cached checkpointer if we opened one
        if self._checkpointer_cm is not None:
            await self._checkpointer_cm.__aexit__(None, None, None)
            self._checkpointer_cm = None
            self._checkpointer = None

        if self._store_cm is not None:
            await self._store_cm.__aexit__(None, None, None)
            self._store_cm = None
            self._store = None

        logger.info("✅ Database connections closed")

    async def get_checkpointer(self) -> AsyncSqliteSaver:
        """Return a live AsyncPostgresSaver.

        We enter the async context manager once and cache the saver so that
        subsequent calls reuse the same database connection pool.  LangGraph
        expects the *real* saver object (it calls methods like
        ``get_next_version``), so returning the context manager wrapper would
        fail.
        """
        if not hasattr(self, "_langgraph_dsn"):
            raise RuntimeError("Database not initialized")
        if self._checkpointer is None:
            self._checkpointer_cm = AsyncSqliteSaver.from_conn_string(
                self._langgraph_dsn
            )
            self._checkpointer = await self._checkpointer_cm.__aenter__()
            # Ensure required tables exist (idempotent)
            await self._checkpointer.setup()
        return self._checkpointer

    async def get_store(self) -> AsyncSqliteStore:
        """Return a live AsyncPostgresStore instance (vector + KV)."""
        if not hasattr(self, "_langgraph_dsn"):
            raise RuntimeError("Database not initialized")
        if self._store is None:
            self._store_cm = AsyncSqliteStore.from_conn_string(self._langgraph_dsn)
            self._store = await self._store_cm.__aenter__()
            # ensure schema
            await self._store.setup()
        return self._store

    def get_engine(self) -> AsyncEngine:
        """Get the SQLAlchemy engine for metadata tables"""
        if not self.engine:
            raise RuntimeError("Database not initialized")
        return self.engine


# Global database manager instance
db_manager = DatabaseManager()
