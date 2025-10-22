from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


class AssistantCreate(BaseModel):
    """Request model for creating assistants"""

    assistant_id: str | None = Field(
        None, description="Unique assistant identifier (auto-generated if not provided)"
    )
    name: str | None = Field(
        None,
        description="Human-readable assistant name (auto-generated if not provided)",
    )
    description: str | None = Field(None, description="Assistant description")
    config: dict[str, Any] | None = Field({}, description="Assistant configuration")
    context: dict[str, Any] | None = Field({}, description="Assistant context")
    graph_id: str = Field(..., description="LangGraph graph ID from aegra.json")
    tool_kits: list[str] | None = Field(
        [], description="List of tool kit names to enable"
    )
    required_fields: list[dict[str, Any]] | None = Field(
        [], description="List of required fields for the assistant"
    )
    metadata: dict[str, Any] | None = Field(
        {}, description="Metadata to use for searching and filtering assistants."
    )
    if_exists: str | None = Field(
        "error", description="What to do if assistant exists: error or do_nothing"
    )


class Assistant(BaseModel):
    """Assistant entity model"""

    assistant_id: str
    name: str
    description: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    tool_kits: list[str] = Field(default_factory=list)
    required_fields: list[dict[str, Any]] = Field(default_factory=list)
    graph_id: str
    created_at: str
    updated_at: str


class AssistantUpdate(BaseModel):
    """Request model for creating assistants"""

    name: str | None = Field(
        None, description="The name of the assistant (auto-generated if not provided)"
    )
    description: str | None = Field(
        None, description="The description of the assistant. Defaults to null."
    )
    config: dict[str, Any] | None = Field(
        {}, description="Configuration to use for the graph."
    )
    graph_id: str = Field("agent", description="The ID of the graph")
    context: dict[str, Any] | None = Field(
        {},
        description="The context to use for the graph. Useful when graph is configurable.",
    )


class AssistantSearchRequest(BaseModel):
    """Request model for assistant search"""

    name: str | None = Field(None, description="Filter by assistant name")
    description: str | None = Field(None, description="Filter by assistant description")
    graph_id: str | None = Field(None, description="Filter by graph ID")
    limit: int | None = Field(20, le=100, ge=1, description="Maximum results")
    offset: int | None = Field(0, ge=0, description="Results offset")


class MinimalAssistant(BaseModel):
    """Minimal assistant model for export and import"""

    name: str
    description: str | None = None
    graph_id: str
    config: dict[str, Any] = Field(default_factory=dict)
    tool_kits: list[str] = Field(default_factory=list)
    required_fields: list[dict[str, Any]] = Field(default_factory=list)


class ThreadCreate(BaseModel):
    """Request model for creating threads"""

    graph_id: str = Field(..., description="Graph to execute")
    assistant_id: str = Field(..., description="Assistant thread belongs to")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Thread metadata")
    initial_state: Optional[Dict[str, Any]] = Field(
        None, description="LangGraph initial state"
    )


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

    limit: Optional[int] = Field(
        10, ge=1, le=1000, description="Number of states to return"
    )
    before: Optional[str] = Field(
        None, description="Return states before this checkpoint ID"
    )
    metadata: Optional[Dict[str, Any]] = Field(None, description="Filter by metadata")
    checkpoint: Optional[Dict[str, Any]] = Field(
        None, description="Checkpoint for subgraph filtering"
    )
    subgraphs: Optional[bool] = Field(
        False, description="Include states from subgraphs"
    )
    checkpoint_ns: Optional[str] = Field(None, description="Checkpoint namespace")


class RunCreate(BaseModel):
    """Request model for creating runs"""

    assistant_id: str = Field(None, description="Graph to execute")
    input: Optional[Dict[str, Any]] = Field(
        None,
        description="Input data for the run. Optional when resuming from a checkpoint.",
    )
    config: Optional[Dict[str, Any]] = Field(
        {}, description="LangGraph execution config"
    )
    context: Optional[Dict[str, Any]] = Field(
        {}, description="Context data for the run"
    )
    checkpoint: Optional[Dict[str, Any]] = Field(
        None,
        description="Checkpoint configuration (e.g., {'checkpoint_id': '...', 'checkpoint_ns': ''})",
    )
    stream: bool = Field(False, description="Enable streaming response")
    stream_mode: Optional[str | list[str]] = Field(
        None, description="Requested stream mode(s) as per LangGraph"
    )
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


class CronCreate(BaseModel):
    """Request model for creating cron jobs"""

    assistant_id: str = Field(..., description="Assistant to run on schedule")
    schedule: str = Field(
        ..., description="Cron schedule expression (e.g., '0 * * * *')"
    )
    required_fields: Optional[Dict[str, Any]] = Field(
        {}, description="Required fields for the assistant"
    )
    special_instructions: Optional[str] = Field(
        "", description="Special instructions for the run"
    )


class Cron(BaseModel):
    """Cron entity model"""

    cron_id: str
    assistant_id: str
    schedule: str
    required_fields: Dict[str, Any]
    special_instructions: Optional[str] = None
    enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CronUpdate(BaseModel):
    """Request model for updating cron jobs"""

    schedule: Optional[str] = Field(
        None, description="Cron schedule expression (e.g., '0 * * * *')"
    )
    required_fields: Optional[Dict[str, Any]] = Field(
        None, description="Required fields for the assistant"
    )
    special_instructions: Optional[str] = Field(
        None, description="Special instructions for the run"
    )
    enabled: Optional[bool] = Field(None, description="Whether the cron job is enabled")


class CronRun(BaseModel):
    """CronRun entity model"""

    cron_run_id: str
    cron_id: str
    status: str  # scheduled, running, completed, failed
    output: str | None = None
    scheduled_at: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: datetime | None = None

    class Config:
        from_attributes = True
