from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import datetime, UTC

from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
    Text,
    Boolean
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, declarative_base, mapped_column, relationship

Base = declarative_base()


class Assistant(Base):
    __tablename__ = "assistant"

    assistant_id: Mapped[str] = mapped_column(
        Text, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    graph_id: Mapped[str] = mapped_column(Text, nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default={})
    context: Mapped[dict] = mapped_column(JSON, default={})
    tool_kits: Mapped[list[str]] = mapped_column(
        JSON, default=[]
    )  # List of tool kit names
    required_fields: Mapped[list[dict]] = mapped_column(
        JSON, default=[]
    )
    created_at: Mapped[datetime] = mapped_column(
        Text, default=datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        Text, default=datetime.now(UTC)
    )


class Thread(Base):
    __tablename__ = "thread"

    thread_id: Mapped[str] = mapped_column(Text, primary_key=True)
    status: Mapped[str] = mapped_column(Text, server_default="idle")
    # Database column is 'metadata_json' (per database.py). ORM attribute 'metadata_json' must map to that column.
    metadata_json: Mapped[dict] = mapped_column(
        "metadata_json", JSON, default={}
    )
    assistant_id: Mapped[str] = mapped_column(
        Text, ForeignKey("assistant.assistant_id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        Text, default=datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        Text, default=datetime.now(UTC)
    )

    # Indexes for performance
    __table_args__ = (Index("idx_thread_assistant", "assistant_id"),)


class Run(Base):
    __tablename__ = "runs"

    run_id: Mapped[str] = mapped_column(
        Text, primary_key=True, default= lambda: str(uuid.uuid4())
    )
    thread_id: Mapped[str] = mapped_column(
        Text, ForeignKey("thread.thread_id", ondelete="CASCADE"), nullable=False
    )
    assistant_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("assistant.assistant_id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    input: Mapped[dict | None] = mapped_column(
        JSON, default={}
    )
    # Some environments may not yet have a 'config' column; make it nullable without default to match existing DB.
    # If migrations add this column later, it's already represented here.
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        Text, default=datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        Text, default=datetime.now(UTC)
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_runs_thread_id", "thread_id"),
        Index("idx_runs_status", "status"),
        Index("idx_runs_assistant_id", "assistant_id"),
        Index("idx_runs_created_at", "created_at"),
    )


class RunEvent(Base):
    __tablename__ = "run_events"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(Text, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        Text, default=datetime.now(UTC)
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_run_events_run_id", "run_id"),
        Index("idx_run_events_seq", "run_id", "seq"),
    )


class Cron(Base):
    __tablename__ = "cron"

    cron_id: Mapped[str] = mapped_column(
        Text, primary_key=True, default= lambda: str(uuid.uuid4())
    )
    assistant_id: Mapped[str] = mapped_column(
        Text, ForeignKey("assistant.assistant_id", ondelete="CASCADE"), nullable=False
    )
    schedule: Mapped[str] = mapped_column(Text, nullable=False)  # e.g., cron expression
    required_fields: Mapped[dict] = mapped_column(JSON, default={})
    special_instructions: Mapped[str | None] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        Text, default=datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        Text, default=datetime.now(UTC)
    )


class CronRun(Base):
    __tablename__ = "cron_runs"

    cron_run_id: Mapped[str] = mapped_column(
        Text, primary_key=True, default= lambda: str(uuid.uuid4())
    )
    cron_id: Mapped[str] = mapped_column(
        Text, ForeignKey("cron.cron_id", ondelete="CASCADE"), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, server_default="scheduled")
    output: Mapped[str] = mapped_column(Text, nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(
        Text, default=datetime.now(UTC)
    )
    started_at: Mapped[datetime | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(Text, nullable=True)

    cron = relationship("Cron", backref="runs")

    # Indexes for performance
    __table_args__ = (
        Index("idx_cron_runs_cron_id", "cron_id"),
        Index("idx_cron_runs_status", "status"),
    )


async_session_maker: async_sessionmaker[AsyncSession] | None = None


def _get_session_maker() -> async_sessionmaker[AsyncSession]:
    """Return a cached async_sessionmaker bound to db_manager.engine."""
    global async_session_maker
    if async_session_maker is None:
        from .database import db_manager

        engine = db_manager.get_engine()
        async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
    return async_session_maker


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields an AsyncSession."""
    maker = _get_session_maker()
    async with maker() as session:
        yield session