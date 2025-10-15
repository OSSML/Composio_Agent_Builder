from asyncio import run
from dotenv import load_dotenv
import os
load_dotenv()

from sqlalchemy import create_engine

from src.core.database import db_manager
from src.core.orm import Base

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from agent_builder.tools import fetch_tools
from src.misc.active_runs import active_runs
from src.api.chat_routes import router as chat_routes
from src.api.assistant_routes import router as assistant_routes
from src.core.database import db_manager

logger = structlog.getLogger(__name__)

async def startup_event():
    """Initialize resources on startup."""
    logger.info("Initializing application resources...")

    # Startup: Initialize database and LangGraph components
    await db_manager.initialize()

    URL = os.getenv("DATABASE_URL").replace("sqlite+aiosqlite", "sqlite")
    engine = create_engine(URL)

    Base.metadata.create_all(engine)

    # Initialize LangGraph service
    from src.services.langgraph_service import get_langgraph_service
    langgraph_service = get_langgraph_service()
    await langgraph_service.initialize()

    # Initialize event store cleanup task
    from src.services.event_store import event_store
    await event_store.start_cleanup_task()

    # Load tools instance
    await fetch_tools()


async def shutdown_event():
    """Cleanup resources on shutdown."""
    logger.info("Shutting down application...")
    # Shutdown: Clean up connections and cancel active runs
    for task in active_runs.values():
        if not task.done():
            task.cancel()

    # Stop event store cleanup task
    from src.services.event_store import event_store
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
    allow_origins=["*"],  # Update for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat_routes, prefix="/api", tags=["chats"])
app.include_router(assistant_routes, prefix="/api", tags=["assistants"])

@app.get("/")
async def root():
    return {"message": "Welcome to Composio agent builder API"}

@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
