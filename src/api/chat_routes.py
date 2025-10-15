import asyncio
from datetime import datetime, timezone, UTC
from uuid import uuid4
from typing import List, Dict, Any, Optional
import logging

from fastapi import APIRouter, HTTPException, Depends, Query, Header
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..misc.active_runs import active_runs
from ..misc.models import (
    Thread, ThreadCreate, ThreadHistoryRequest, ThreadState, ThreadSearchRequest, ThreadSearchResponse,
    Run, RunStatus, RunCreate, RunList
)
from ..core.orm import Assistant as AssistantORM, Thread as ThreadORM, get_session, Run as RunORM
from ..core.sse import create_end_event, get_sse_headers
from ..misc.utils import set_thread_status, update_thread_metadata, execute_run_async
from ..services.langgraph_service import get_langgraph_service, create_thread_config
from ..services.streaming_service import streaming_service
from ..utils import resolve_assistant_id, _merge_jsonb

router = APIRouter()

logger = logging.getLogger(__name__)


@router.post("/chat/new", response_model=Thread)
async def create_chat(
    request: ThreadCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create a new chat thread."""
    thread_id = str(uuid4())

    metadata = request.metadata or {}
    metadata.update({
        "graph_id": request.graph_id
    })

    thread_orm = ThreadORM(
        assistant_id=request.assistant_id,
        thread_id=thread_id,
        status="idle",
        metadata_json=metadata,
    )

    # SQLAlchemy AsyncSession.add is sync; do not await
    session.add(thread_orm)
    await session.commit()

    try:
        await session.refresh(thread_orm)
    except Exception:
        pass

    thread_dict: Dict[str, Any] = {
        "thread_id": thread_orm.thread_id,
        "assistant_id": thread_orm.assistant_id,
        "status": thread_orm.status,
        "metadata": thread_orm.metadata_json,
        "created_at": thread_orm.created_at,
    }

    return Thread.model_validate(thread_dict)


@router.post("/chat/{thread_id}/history", response_model=List[ThreadState])
async def get_chat_history(
    thread_id: str,
    request: ThreadHistoryRequest,
    session: AsyncSession = Depends(get_session)
):
    """Get the chat history for a specific thread."""
    try:
        limit = request.limit or 10
        if not isinstance(limit, int) or limit < 1 or limit > 1000:
            raise HTTPException(422, "Invalid limit; must be an integer between 1 and 1000")

        before = request.before
        if before is not None and not isinstance(before, str):
            raise HTTPException(422, "Invalid 'before' parameter; must be a string checkpoint identifier")

        metadata = request.metadata
        if metadata is not None and not isinstance(metadata, dict):
            raise HTTPException(422, "Invalid 'metadata' parameter; must be an object")

        checkpoint = request.checkpoint or {}
        if not isinstance(checkpoint, dict):
            raise HTTPException(422, "Invalid 'checkpoint' parameter; must be an object")

        checkpoint_ns = request.checkpoint_ns
        if checkpoint_ns is not None and not isinstance(checkpoint_ns, str):
            raise HTTPException(422, "Invalid 'checkpoint_ns'; must be a string")

        logger.debug(
            f"history POST: thread_id={thread_id} limit={limit} before={before} checkpoint_ns={checkpoint_ns}")

        # Verify the thread exists and belongs to the user
        stmt = select(ThreadORM).where(
            ThreadORM.thread_id == thread_id
        )
        thread = await session.scalar(stmt)
        if not thread:
            raise HTTPException(404, f"Thread '{thread_id}' not found")

        # Extract graph_id from thread metadata
        thread_metadata = thread.metadata_json or {}
        graph_id = thread_metadata.get("graph_id")
        if not graph_id:
            # Return empty history if no graph is associated yet
            logger.info(f"history POST: no graph_id set for thread {thread_id}")
            return []

        # Get compiled graph
        langgraph_service = get_langgraph_service()
        try:
            agent = await langgraph_service.get_graph(graph_id)
        except Exception as e:
            logger.exception("Failed to load graph '%s' for history", graph_id)
            raise HTTPException(500, f"Failed to load graph '{graph_id}': {str(e)}")

        # Build config with user context and thread_id
        config: Dict[str, Any] = create_thread_config(thread_id, {})
        # Merge checkpoint and namespace if provided
        if checkpoint:
            cfg_cp = checkpoint.copy()
            if checkpoint_ns is not None:
                cfg_cp.setdefault("checkpoint_ns", checkpoint_ns)
            config["configurable"].update(cfg_cp)
        elif checkpoint_ns is not None:
            config["configurable"]["checkpoint_ns"] = checkpoint_ns

        # Fetch state history
        state_snapshots = []
        kwargs = {
            "limit": limit,
            "before": before,
        }
        # The runtime may expect metadata filter under "filter" or "metadata"; try "metadata"
        if metadata is not None:
            kwargs["metadata"] = metadata  # type: ignore[index]

        async for snapshot in agent.aget_state_history(config, **kwargs):
            state_snapshots.append(snapshot)

        # Map to ThreadState
        thread_states: List[ThreadState] = []
        for snapshot in state_snapshots:
            snap_config = getattr(snapshot, "config", {}) or {}
            parent_config = getattr(snapshot, "parent_config", {}) or {}
            checkpoint_id = None
            parent_checkpoint_id = None
            if isinstance(snap_config, dict):
                checkpoint_id = (snap_config.get("configurable") or {}).get("checkpoint_id")
            if isinstance(parent_config, dict):
                parent_checkpoint_id = (parent_config.get("configurable") or {}).get("checkpoint_id")

            created_at = getattr(snapshot, "created_at", None)

            thread_state = ThreadState(
                values=getattr(snapshot, "values", {}),
                next=getattr(snapshot, "next", []) or [],
                metadata=getattr(snapshot, "metadata", {}) or {},
                created_at=created_at,
                checkpoint_id=checkpoint_id,
                parent_checkpoint_id=parent_checkpoint_id,
            )
            thread_states.append(thread_state)

        return thread_states

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error in history POST for thread %s", thread_id)
        # Return empty list for clearly absent histories if backend signals not found-like cases
        msg = str(e).lower()
        if "not found" in msg or "no checkpoint" in msg:
            return []
        raise HTTPException(500, f"Error retrieving thread history: {str(e)}")

@router.post("/chat/search", response_model=ThreadSearchResponse)
async def chat_search(
    request: ThreadSearchRequest,
    session: AsyncSession = Depends(get_session)
):
    """Search chats with filters"""

    stmt = select(ThreadORM)

    if request.status:
        stmt = stmt.where(ThreadORM.status == request.status)

    if request.metadata:
        stmt = stmt.where(ThreadORM.metadata_json.op("@>")(request.metadata))

    # Count total first
    _count_result = await session.scalars(stmt)
    total = len(_count_result.all())

    offset = request.offset or 0
    limit = request.limit or 20
    # Return latest first
    stmt = stmt.order_by(ThreadORM.created_at.desc()).offset(offset).limit(limit)

    result = await session.scalars(stmt)
    rows = result.all()
    threads_models = [
        Thread.model_validate({
            **{c.name: getattr(t, c.name) for c in t.__table__.columns},
            "metadata": t.metadata_json,
        })
        for t in rows
    ]

    # Return array of threads for client/vendor parity
    return ThreadSearchResponse(
        threads=threads_models,
        total=total,
        limit=limit,
        offset=offset,
    )

@router.post("/chat/{thread_id}/runs", response_model=Run)
async def create_run(
    thread_id: str,
    request: RunCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create and execute a new run (persisted)."""

    run_id = str(uuid4())

    # Get LangGraph service
    langgraph_service = get_langgraph_service()
    logger.info(
        f"create_run: scheduling background task run_id={run_id} thread_id={thread_id}"
    )
    logger.info(
        f"[create_run] scheduling background task run_id={run_id} thread_id={thread_id}"
    )

    # Validate assistant exists and get its graph_id. If a graph_id was provided
    # instead of an assistant UUID, map it deterministically and fall back to the
    # default assistant created at startup.
    requested_id = str(request.assistant_id)
    available_graphs = langgraph_service.list_graphs()
    resolved_assistant_id = resolve_assistant_id(requested_id, available_graphs)

    config = request.config
    context = request.context
    configurable = config.get("configurable", {})

    if config.get("configurable") and context:
        raise HTTPException(
            status_code=400,
            detail="Cannot specify both configurable and context. Prefer setting context alone. Context was introduced in LangGraph 0.6.0 and is the long term planned replacement for configurable.",
        )

    if context:
        configurable = context.copy()
        config["configurable"] = configurable
    else:
        context = configurable.copy()

    assistant_stmt = select(AssistantORM).where(
        AssistantORM.assistant_id == resolved_assistant_id,
    )
    assistant = await session.scalar(assistant_stmt)
    if not assistant:
        raise HTTPException(404, f"Assistant '{request.assistant_id}' not found")

    config = _merge_jsonb(assistant.config, config)
    context = _merge_jsonb(assistant.context, context)

    # Validate the assistant's graph exists
    available_graphs = langgraph_service.list_graphs()
    if assistant.graph_id not in available_graphs:
        raise HTTPException(
            404, f"Graph '{assistant.graph_id}' not found for assistant"
        )

    # Mark thread as busy and update metadata with assistant/graph info
    await set_thread_status(session, thread_id, "busy")
    await update_thread_metadata(
        session, thread_id, assistant.assistant_id, assistant.graph_id
    )

    # Persist run record via ORM model in core.orm (Run table)
    now = datetime.now(UTC)
    run_orm = RunORM(
        run_id=run_id,  # explicitly set (DB can also default-generate if omitted)
        thread_id=thread_id,
        assistant_id=resolved_assistant_id,
        status="pending",
        input=request.input or {},
        config=config,
        context=context,
        created_at=now,
        updated_at=now,
        output=None,
        error_message=None,
    )
    session.add(run_orm)
    await session.commit()

    # Build response from ORM -> Pydantic
    run = Run(
        run_id=run_id,
        thread_id=thread_id,
        assistant_id=resolved_assistant_id,
        status="pending",
        input=request.input or {},
        config=config,
        context=context,
        created_at=now,
        updated_at=now,
        output=None,
        error_message=None,
    )

    # Start execution asynchronously
    # Don't pass the session to avoid transaction conflicts
    task = asyncio.create_task(
        execute_run_async(
            run_id,
            thread_id,
            assistant.graph_id,
            request.input or {},
            config,
            context,
            request.stream_mode,
            request.checkpoint
            )
    )
    logger.info(
        f"[create_run] background task created task_id={id(task)} for run_id={run_id}"
    )
    active_runs[run_id] = task

    return run


@router.post("/threads/{thread_id}/runs/stream")
async def create_and_stream_run(
        thread_id: str,
        request: RunCreate,
        session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Create a new run and stream its execution - persisted + SSE."""

    run_id = str(uuid4())

    # Get LangGraph service
    langgraph_service = get_langgraph_service()
    logger.info(
        f"[create_and_stream_run] scheduling background task run_id={run_id} thread_id={thread_id}"
    )

    # Validate assistant exists and get its graph_id. Allow passing a graph_id
    # by mapping it to a deterministic assistant ID.
    requested_id = str(request.assistant_id)
    available_graphs = langgraph_service.list_graphs()

    resolved_assistant_id = resolve_assistant_id(requested_id, available_graphs)

    config = request.config
    context = request.context
    configurable = config.get("configurable", {})

    if config.get("configurable") and context:
        raise HTTPException(
            status_code=400,
            detail="Cannot specify both configurable and context. Prefer setting context alone. Context was introduced in LangGraph 0.6.0 and is the long term planned replacement for configurable.",
        )

    if context:
        configurable = context.copy()
        config["configurable"] = configurable
    else:
        context = configurable.copy()

    assistant_stmt = select(AssistantORM).where(
        AssistantORM.assistant_id == resolved_assistant_id,
        )
    assistant = await session.scalar(assistant_stmt)
    if not assistant:
        raise HTTPException(404, f"Assistant '{request.assistant_id}' not found")

    config = _merge_jsonb(assistant.config, config)
    context = _merge_jsonb(assistant.context, context)

    # Validate the assistant's graph exists
    available_graphs = langgraph_service.list_graphs()
    if assistant.graph_id not in available_graphs:
        raise HTTPException(
            404, f"Graph '{assistant.graph_id}' not found for assistant"
        )

    # Mark thread as busy and update metadata with assistant/graph info
    await set_thread_status(session, thread_id, "busy")
    await update_thread_metadata(
        session, thread_id
    )

    # Persist run record
    now = datetime.now(UTC)
    run_orm = RunORM(
        run_id=run_id,
        thread_id=thread_id,
        assistant_id=resolved_assistant_id,
        status="streaming",
        input=request.input or {},
        config=config,
        context=context,
        created_at=now,
        updated_at=now,
        output=None,
        error_message=None,
    )
    session.add(run_orm)
    await session.commit()

    # Build response model for stream context
    run = Run(
        run_id=run_id,
        thread_id=thread_id,
        assistant_id=resolved_assistant_id,
        status="streaming",
        input=request.input or {},
        config=config,
        context=context,
        created_at=now,
        updated_at=now,
        output=None,
        error_message=None,
    )

    # Start background execution that will populate the broker
    # Don't pass the session to avoid transaction conflicts
    task = asyncio.create_task(
        execute_run_async(
            run_id,
            thread_id,
            assistant.graph_id,
            request.input or {},
            config,
            context,
            request.stream_mode,
            request.checkpoint
            )
    )
    logger.info(
        f"[create_and_stream_run] background task created task_id={id(task)} for run_id={run_id}"
    )
    active_runs[run_id] = task

    # Extract requested stream mode(s)
    stream_mode = request.stream_mode
    if not stream_mode and config and "stream_mode" in config:
        stream_mode = config["stream_mode"]

    # Stream immediately from broker (which will also include replay of any early events)
    cancel_on_disconnect = (request.on_disconnect or "continue").lower() == "cancel"

    return StreamingResponse(
        streaming_service.stream_run_execution(
            run,
            None,
            cancel_on_disconnect=cancel_on_disconnect,
        ),
        media_type="text/event-stream",
        headers={
            **get_sse_headers(),
            "Location": f"/threads/{thread_id}/runs/{run_id}/stream",
            "Content-Location": f"/threads/{thread_id}/runs/{run_id}",
        },
    )


@router.get("/chat/{thread_id}/runs/{run_id}", response_model=Run)
async def get_run(
    thread_id: str,
    run_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get run by ID (persisted)."""
    stmt = select(RunORM).where(
        RunORM.run_id == str(run_id),
        RunORM.thread_id == thread_id,
    )
    logger.info(f"[get_run] querying DB run_id={run_id} thread_id={thread_id}")
    run_orm = await session.scalar(stmt)
    if not run_orm:
        raise HTTPException(404, f"Run '{run_id}' not found")

    logger.info(f"[get_run] found run status={run_orm.status} thread_id={thread_id} run_id={run_id}")
    # Convert to Pydantic
    return Run.model_validate({c.name: getattr(run_orm, c.name) for c in run_orm.__table__.columns})


@router.get("/chat/{thread_id}/runs", response_model=RunList)
async def list_runs(
    thread_id: str,
    session: AsyncSession = Depends(get_session),
):
    """List runs for a specific thread (persisted)."""
    stmt = select(RunORM).where(
        RunORM.thread_id == thread_id,
    ).order_by(RunORM.created_at.desc())
    logger.info(f"[list_runs] querying DB thread_id={thread_id}")
    result = await session.scalars(stmt)
    rows = result.all()
    runs = [Run.model_validate({c.name: getattr(r, c.name) for c in r.__table__.columns}) for r in rows]
    logger.info(f"[list_runs] total={len(runs)} thread_id={thread_id}")
    return RunList(runs=runs, total=len(runs))


@router.patch("/chat/{thread_id}/runs/{run_id}")
async def update_run(
    thread_id: str,
    run_id: str,
    request: RunStatus,
    session: AsyncSession = Depends(get_session),
):
    """Update run status (for cancellation/interruption, persisted)."""
    logger.info(f"[update_run] fetch for update run_id={run_id} thread_id={thread_id}")
    run_orm = await session.scalar(
        select(RunORM).where(
            RunORM.run_id == str(run_id),
            RunORM.thread_id == thread_id,
        )
    )
    if not run_orm:
        raise HTTPException(404, f"Run '{run_id}' not found")

    # Handle interruption/cancellation
    if request.status == "cancelled":
        logger.info(f"[update_run] cancelling run_id={run_id} thread_id={thread_id}")
        await streaming_service.cancel_run(run_id)
        logger.info(f"[update_run] set DB status=cancelled run_id={run_id}")
        await session.execute(
            update(RunORM).where(RunORM.run_id == str(run_id)).values(status="cancelled", updated_at=datetime.now(timezone.utc))
        )
        await session.commit()
        logger.info(f"[update_run] commit done (cancelled) run_id={run_id}")
    elif request.status == "interrupted":
        logger.info(f"[update_run] interrupt run_id={run_id} thread_id={thread_id}")
        await streaming_service.interrupt_run(run_id)
        logger.info(f"[update_run] set DB status=interrupted run_id={run_id}")
        await session.execute(
            update(RunORM).where(RunORM.run_id == str(run_id)).values(status="interrupted", updated_at=datetime.now(timezone.utc))
        )
        await session.commit()
        logger.info(f"[update_run] commit done (interrupted) run_id={run_id}")

    # Return final run state
    run_orm = await session.scalar(select(RunORM).where(RunORM.run_id == run_id))
    return Run.model_validate({c.name: getattr(run_orm, c.name) for c in run_orm.__table__.columns})


@router.post("/chat/{thread_id}/runs/{run_id}/cancel")
async def cancel_run_endpoint(
    thread_id: str,
    run_id: str,
    wait: int = Query(0, ge=0, le=1, description="Whether to wait for the run task to settle"),
    action: str = Query("cancel", pattern="^(cancel|interrupt)$", description="Cancellation action"),
    session: AsyncSession = Depends(get_session),
):
    """
    Cancel or interrupt a run.

    Matches client usage:
      POST /v1/threads/{thread_id}/runs/{run_id}/cancel?wait=0&action=interrupt

    - action=cancel => hard cancel
    - action=interrupt => cooperative interrupt if supported
    - wait=1 => await background task to finish settling
    """
    logger.info(f"[cancel_run] fetch run run_id={run_id} thread_id={thread_id}")
    run_orm = await session.scalar(
        select(RunORM).where(
            RunORM.run_id == run_id,
            RunORM.thread_id == thread_id,
        )
    )
    if not run_orm:
        raise HTTPException(404, f"Run '{run_id}' not found")

    if action == "interrupt":
        logger.info(f"[cancel_run] interrupt run_id={run_id} hread_id={thread_id}")
        await streaming_service.interrupt_run(run_id)
        # Persist status as interrupted
        await session.execute(
            update(RunORM).where(RunORM.run_id == str(run_id)).values(status="interrupted", updated_at=datetime.now(timezone.utc))
        )
        await session.commit()
    else:
        logger.info(f"[cancel_run] cancel run_id={run_id} thread_id={thread_id}")
        await streaming_service.cancel_run(run_id)
        # Persist status as cancelled
        await session.execute(
            update(RunORM).where(RunORM.run_id == str(run_id)).values(status="cancelled", updated_at=datetime.now(timezone.utc))
        )
        await session.commit()

    # Optionally wait for background task
    if wait:
        task = active_runs.get(run_id)
        if task:
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

    # Reload and return updated Run (do NOT delete here; deletion is a separate endpoint)
    run_orm = await session.scalar(
        select(RunORM).where(
            RunORM.run_id == run_id,
            RunORM.thread_id == thread_id,
        )
    )
    if not run_orm:
        raise HTTPException(404, f"Run '{run_id}' not found after cancellation")
    return Run.model_validate({c.name: getattr(run_orm, c.name) for c in run_orm.__table__.columns})
