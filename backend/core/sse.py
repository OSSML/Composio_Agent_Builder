"""Server-Sent Events utilities and formatting - LangGraph Compatible"""

import json
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass


def _serialize_message_object(obj):
    """Custom serializer for LangChain message objects"""
    # Handle LangChain message objects
    if hasattr(obj, "dict"):
        return obj.dict()
    elif hasattr(obj, "__dict__"):
        # For message chunks, extract key attributes
        result = {}
        if hasattr(obj, "content"):
            result["content"] = obj.content
        if hasattr(obj, "additional_kwargs"):
            result["additional_kwargs"] = obj.additional_kwargs
        if hasattr(obj, "response_metadata"):
            result["response_metadata"] = obj.response_metadata
        if hasattr(obj, "id"):
            result["id"] = obj.id
        if hasattr(obj, "type"):
            result["type"] = obj.type
        return result if result else str(obj)
    else:
        return str(obj)


def get_sse_headers() -> Dict[str, str]:
    """Get standard SSE headers"""
    return {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Type": "text/event-stream",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Last-Event-ID",
    }


def format_sse_message(event: str, data: Any, event_id: Optional[str] = None) -> str:
    """Format a message as Server-Sent Event following SSE standard"""
    lines = []

    if event_id:
        lines.append(f"id: {event_id}")

    lines.append(f"event: {event}")

    # Convert data to JSON string with proper message object handling
    if data is None:
        data_str = ""
    else:
        data_str = json.dumps(
            data, default=_serialize_message_object, separators=(",", ":")
        )

    lines.append(f"data: {data_str}")
    lines.append("")  # Empty line to end the event

    return "\n".join(lines) + "\n"


def create_metadata_event(run_id: str, event_id: Optional[str] = None) -> str:
    """Create metadata event - equivalent to LangGraph's metadata event"""
    data = {"run_id": run_id, "timestamp": datetime.utcnow().isoformat()}
    return format_sse_message("metadata", data, event_id)


def create_values_event(
    chunk_data: Dict[str, Any], event_id: Optional[str] = None
) -> str:
    """Create values event - equivalent to LangGraph's values stream mode"""
    return format_sse_message("values", chunk_data, event_id)


def create_debug_event(
    debug_data: Dict[str, Any], event_id: Optional[str] = None
) -> str:
    """Create debug event - equivalent to LangGraph's debug stream mode"""
    return format_sse_message("debug", debug_data, event_id)


def create_end_event(event_id: Optional[str] = None) -> str:
    """Create end event - signals completion of stream"""
    return format_sse_message("end", {"status": "completed"}, event_id)


def create_error_event(error: str, event_id: Optional[str] = None) -> str:
    """Create error event"""
    data = {"error": error, "timestamp": datetime.utcnow().isoformat()}
    return format_sse_message("error", data, event_id)


def create_events_event(
    event_data: Dict[str, Any], event_id: Optional[str] = None
) -> str:
    """Create events stream mode event"""
    return format_sse_message("events", event_data, event_id)


def create_state_event(
    state_data: Dict[str, Any], event_id: Optional[str] = None
) -> str:
    """Create state event - equivalent to LangGraph's state stream mode"""
    return format_sse_message("state", state_data, event_id)


def create_logs_event(logs_data: Dict[str, Any], event_id: Optional[str] = None) -> str:
    """Create logs event - equivalent to LangGraph's logs stream mode"""
    return format_sse_message("logs", logs_data, event_id)


def create_tasks_event(
    tasks_data: Dict[str, Any], event_id: Optional[str] = None
) -> str:
    """Create tasks event - equivalent to LangGraph's tasks stream mode"""
    return format_sse_message("tasks", tasks_data, event_id)


def create_subgraphs_event(
    subgraphs_data: Dict[str, Any], event_id: Optional[str] = None
) -> str:
    """Create subgraphs event - equivalent to LangGraph's subgraphs stream mode"""
    return format_sse_message("subgraphs", subgraphs_data, event_id)


def create_messages_event(
    messages_data: Any, event_type: str = "messages", event_id: Optional[str] = None
) -> str:
    """Create messages event (messages, messages/partial, messages/complete, messages/metadata)"""
    # Handle tuple format for token streaming: (message_chunk, metadata)
    if isinstance(messages_data, tuple) and len(messages_data) == 2:
        message_chunk, metadata = messages_data
        # Format as expected by LangGraph SDK client
        data = [message_chunk, metadata]
        return format_sse_message(event_type, data, event_id)
    else:
        # Handle list of messages format
        return format_sse_message(event_type, messages_data, event_id)


# Legacy compatibility functions (deprecated)
@dataclass
class SSEEvent:
    """Legacy SSE Event data structure - deprecated"""

    id: str
    event: str
    data: Dict[str, Any]
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

    def format(self) -> str:
        """Format as proper SSE event - deprecated"""
        json_data = json.dumps(self.data, default=str)
        return f"id: {self.id}\nevent: {self.event}\ndata: {json_data}\n\n"


def format_sse_event(id: str, event: str, data: Dict[str, Any]) -> str:
    """Legacy format function - deprecated"""
    json_data = json.dumps(data, default=str)
    return f"id: {id}\nevent: {event}\ndata: {json_data}\n\n"


# Legacy event creation functions - deprecated but kept for compatibility
def create_start_event(run_id: str, event_counter: int) -> str:
    """Legacy start event - deprecated, use create_metadata_event instead"""
    return format_sse_event(
        id=f"{run_id}_event_{event_counter}",
        event="start",
        data={
            "type": "run_start",
            "run_id": run_id,
            "status": "streaming",
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


def create_chunk_event(
    run_id: str, event_counter: int, chunk_data: Dict[str, Any]
) -> str:
    """Legacy chunk event - deprecated, use create_values_event instead"""
    return format_sse_event(
        id=f"{run_id}_event_{event_counter}",
        event="chunk",
        data={
            "type": "execution_chunk",
            "chunk": chunk_data,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


def create_complete_event(run_id: str, event_counter: int, final_output: Any) -> str:
    """Legacy complete event - deprecated, use create_end_event instead"""
    return format_sse_event(
        id=f"{run_id}_event_{event_counter}",
        event="complete",
        data={
            "type": "run_complete",
            "status": "completed",
            "final_output": final_output,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


def create_cancelled_event(run_id: str, event_counter: int) -> str:
    """Legacy cancelled event - deprecated"""
    return format_sse_event(
        id=f"{run_id}_event_{event_counter}",
        event="cancelled",
        data={
            "type": "run_cancelled",
            "status": "cancelled",
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


def create_interrupted_event(run_id: str, event_counter: int) -> str:
    """Legacy interrupted event - deprecated"""
    return format_sse_event(
        id=f"{run_id}_event_{event_counter}",
        event="interrupted",
        data={
            "type": "run_interrupted",
            "status": "interrupted",
            "timestamp": datetime.utcnow().isoformat(),
        },
    )
