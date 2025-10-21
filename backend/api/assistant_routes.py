from uuid import uuid4
from typing import List

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from core.orm import Assistant as AssistantORM, get_session
from misc.models import AssistantCreate, Assistant
from services.langgraph_service import get_langgraph_service

router = APIRouter()

logger = structlog.getLogger(__name__)


def to_pydantic(row: AssistantORM) -> Assistant:
    """Convert SQLAlchemy ORM object to Pydantic model with proper type casting."""
    row_dict = {c.name: getattr(row, c.name) for c in row.__table__.columns}
    # Cast UUIDs to str so they match the Pydantic schema
    if "assistant_id" in row_dict and row_dict["assistant_id"] is not None:
        row_dict["assistant_id"] = str(row_dict["assistant_id"])
    return Assistant.model_validate(row_dict)


@router.post("/assistants", response_model=Assistant)
async def create_assistant(
    request: AssistantCreate, session: AsyncSession = Depends(get_session)
):
    """Create a new assistant"""
    # Get LangGraph service to validate graph
    langgraph_service = get_langgraph_service()
    available_graphs = langgraph_service.list_graphs()

    # Use graph_id as the main identifier
    graph_id = request.graph_id

    if graph_id not in available_graphs:
        raise HTTPException(
            400,
            f"Graph '{graph_id}' not found in aegra.json. Available: {list(available_graphs.keys())}",
        )

    # Validate graph can be loaded
    try:
        await langgraph_service.get_graph(graph_id)
    except Exception as e:
        raise HTTPException(400, f"Failed to load graph: {str(e)}") from e

    config = request.config
    context = request.context

    if config.get("configurable") and context:
        raise HTTPException(
            status_code=400,
            detail="Cannot specify both configurable and context. Prefer setting context alone. Context was introduced in LangGraph 0.6.0 and is the long term planned replacement for configurable.",
        )

    # Keep config and context up to date with one another
    if config.get("configurable"):
        context = config["configurable"]
    elif context:
        config["configurable"] = context

    # Generate assistant_id if not provided
    assistant_id = request.assistant_id or str(uuid4())

    # Generate name if not provided
    name = request.name or f"Assistant for {graph_id}"

    # Check if an assistant already exists for this user, graph and config pair
    existing_stmt = select(AssistantORM).where(
        or_(
            (AssistantORM.graph_id == graph_id) & (AssistantORM.config == config),
            AssistantORM.assistant_id == assistant_id,
        ),
    )
    existing = await session.scalar(existing_stmt)

    if existing:
        if request.if_exists == "do_nothing":
            return to_pydantic(existing)
        else:  # error (default)
            raise HTTPException(409, f"Assistant '{assistant_id}' already exists")

    # Create assistant record
    assistant_orm = AssistantORM(
        assistant_id=assistant_id,
        name=name,
        description=request.description,
        config=config,
        context=context,
        graph_id=graph_id,
        tool_kits=request.tool_kits,
        required_fields=request.required_fields,
    )

    session.add(assistant_orm)
    await session.commit()
    await session.refresh(assistant_orm)

    return to_pydantic(assistant_orm)


@router.get("/assistants", response_model=List[Assistant])
async def list_assistants(session: AsyncSession = Depends(get_session)):
    """List user's assistants"""
    stmt = select(AssistantORM)
    result = await session.scalars(stmt)
    user_assistants = [to_pydantic(a) for a in result.all()]
    return user_assistants
