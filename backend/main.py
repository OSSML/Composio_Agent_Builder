import pathlib

from sqlalchemy import create_engine, inspect
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from api import assistant_router, chat_router, composio_router, cron_router
from core.database import db_manager
from core.config import settings
from core.orm import Base
from core.tool_router import fetch_tools
from misc.active_runs import active_runs
from misc.setup_logging import setup_logging
from services.cron_service import scheduler
from services.event_store import event_store
from services.langgraph_service import get_langgraph_service
from services.seed_agents import seed_agents

setup_logging()
logger = structlog.getLogger(__name__)


async def startup_event():
    """Initialize resources on startup."""
    logger.info("Initializing application resources...")

    # Startup: Initialize database and LangGraph components
    await db_manager.initialize()

    URL = settings.DATABASE_URL.replace("sqlite+aiosqlite", "sqlite")
    engine = create_engine(URL)

    empty_database = False
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    if not table_names:
        logger.info("Database is empty. Seeding default agents...")
        empty_database = True

    # Create the necessary tables for the database. (If not present)
    Base.metadata.create_all(engine)

    if empty_database:
        await seed_agents(pathlib.Path(__file__).parent / "default_agents")

    # Initialize LangGraph service
    langgraph_service = get_langgraph_service()
    await langgraph_service.initialize()

    # Initialize event store cleanup task
    await event_store.start_cleanup_task()

    # Load tools instance
    await fetch_tools()

    scheduler.start()


async def shutdown_event():
    """Cleanup resources on shutdown."""
    logger.info("Shutting down application...")
    # Shutdown: Clean up connections and cancel active runs
    for task in active_runs.values():
        if not task.done():
            task.cancel()

    # Stop event store cleanup task
    await event_store.stop_cleanup_task()

    await db_manager.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup and shutdown events."""
    # Startup event
    await startup_event()

    yield

    # Shutdown event
    await shutdown_event()


app = FastAPI(title="Composio agent builder", lifespan=lifespan)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat_router, prefix="/api", tags=["chats"])
app.include_router(assistant_router, prefix="/api", tags=["assistants"])
app.include_router(composio_router, prefix="/api", tags=["composio"])
app.include_router(cron_router, prefix="/api", tags=["cron"])


@app.get("/")
async def root():
    return {"message": "Welcome to Composio agent builder API"}


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000)
