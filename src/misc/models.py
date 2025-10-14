from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


class ThreadCreate(BaseModel):
    """Request model for creating threads"""
    graph_id: str = Field(..., description="Graph to execute")
    assistant_id: str = Field(..., description="Assistant thread belongs to")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Thread metadata")
    initial_state: Optional[Dict[str, Any]] = Field(None, description="LangGraph initial state")


class Thread(BaseModel):
    """Thread entity model"""
    assistant_id: str
    thread_id: str
    status: str = "idle"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    class Config:
        from_attributes = True


class ThreadCheckpoint(BaseModel):
    """Checkpoint identifier for thread history"""

    checkpoint_id: str | None = None
    thread_id: str | None = None
    checkpoint_ns: str | None = ""


class ThreadState(BaseModel):
    """Thread state model for history endpoint"""

    values: dict[str, Any] = Field(description="Channel values (messages, etc.)")
    next: list[str] = Field(default_factory=list, description="Next nodes to execute")
    tasks: list[dict[str, Any]] = Field(
        default_factory=list, description="Tasks to execute"
    )
    interrupts: list[dict[str, Any]] = Field(
        default_factory=list, description="Interrupt data"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Checkpoint metadata"
    )
    created_at: datetime | None = Field(None, description="Timestamp of state creation")
    checkpoint_id: str | None = Field(
        None, description="Checkpoint ID (for backward compatibility)"
    )
    parent_checkpoint_id: str | None = Field(
        None, description="Parent checkpoint ID (for backward compatibility)"
    )


class ThreadSearchRequest(BaseModel):
    """Request model for thread search"""
    metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata filters")
    status: Optional[str] = Field(None, description="Thread status filter")
    limit: Optional[int] = Field(20, le=100, ge=1, description="Maximum results")
    offset: Optional[int] = Field(0, ge=0, description="Results offset")
    order_by: Optional[str] = Field("created_at DESC", description="Sort order")


class ThreadSearchResponse(BaseModel):
    """Response model for thread search"""
    threads: List[Thread]
    total: int
    limit: int
    offset: int


class ThreadList(BaseModel):
    """Response model for listing threads"""
    threads: List[Thread]
    total: int


class ThreadHistoryRequest(BaseModel):
    """Request model for thread history endpoint"""
    limit: Optional[int] = Field(10, ge=1, le=1000, description="Number of states to return")
    before: Optional[str] = Field(None, description="Return states before this checkpoint ID")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Filter by metadata")
    checkpoint: Optional[Dict[str, Any]] = Field(None, description="Checkpoint for subgraph filtering")
    subgraphs: Optional[bool] = Field(False, description="Include states from subgraphs")
    checkpoint_ns: Optional[str] = Field(None, description="Checkpoint namespace")


class RunCreate(BaseModel):
    """Request model for creating runs"""
    assistant_id: str = Field(None, description="Graph to execute")
    input: Optional[Dict[str, Any]] = Field(
        None,
        description="Input data for the run. Optional when resuming from a checkpoint.",
    )
    config: Optional[Dict[str, Any]] = Field({}, description="LangGraph execution config")
    context: Optional[Dict[str, Any]] = Field({}, description="Context data for the run")
    checkpoint: Optional[Dict[str, Any]] = Field(
        None,
        description="Checkpoint configuration (e.g., {'checkpoint_id': '...', 'checkpoint_ns': ''})",
    )
    stream: bool = Field(False, description="Enable streaming response")
    stream_mode: Optional[str | list[str]] = Field(None, description="Requested stream mode(s) as per LangGraph")
    on_disconnect: Optional[str] = Field(
        None,
        description="Behavior on client disconnect: 'cancel' or 'continue' (default).",
    )


class Run(BaseModel):
    """Run entity model"""
    run_id: str
    thread_id: str
    assistant_id: str
    status: str = "pending"  # pending, running, completed, failed, cancelled
    input: Dict[str, Any]
    output: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RunList(BaseModel):
    """Response model for listing runs"""
    runs: List[Run]
    total: int


class RunStatus(BaseModel):
    """Simple run status response"""
    run_id: str
    status: str
    message: Optional[str] = None