import asyncio
from typing import Dict, AsyncIterator, Optional, Any

import structlog

from core.sse import (
    create_values_event,
    create_end_event,
    create_error_event,
    create_messages_event,
    create_state_event,
    create_logs_event,
    create_tasks_event,
    create_subgraphs_event,
    create_debug_event,
    create_metadata_event,
    create_events_event,
)
from misc.models import Run
from misc.active_runs import active_runs
from services.event_store import event_store, store_sse_event
from services.broker import broker_manager

logger = structlog.getLogger(__name__)


class StreamingService:
    """Service to handle SSE streaming orchestration with LangGraph compatibility"""

    def __init__(self):
        self.active_streams: Dict[str, asyncio.Task] = {}
        self.event_counters: Dict[str, int] = {}

    def _next_event_counter(self, run_id: str, event_id: str) -> int:
        """Update and return the next event counter for a run"""
        try:
            idx = self._extract_event_sequence(event_id)
            current = self.event_counters.get(run_id, 0)
            if idx > current:
                self.event_counters[run_id] = idx
                return idx
        except Exception:
            pass  # Ignore format issues
        return self.event_counters.get(run_id, 0)

    async def put_to_broker(self, run_id: str, event_id: str, raw_event: Any):
        """Put an event into the run's broker queue for live consumers"""
        broker = broker_manager.get_or_create_broker(run_id)
        # Keep internal counter in sync with highest event index seen
        self._next_event_counter(run_id, event_id)
        await broker.put(event_id, raw_event)

    async def store_event_from_raw(self, run_id: str, event_id: str, raw_event: Any):
        """Convert raw event to stored format and store it"""
        # Parse the raw event similar to existing logic
        node_path = None
        stream_mode_label = None
        event_payload = None

        if isinstance(raw_event, tuple):
            if len(raw_event) == 2:
                stream_mode_label, event_payload = raw_event
            elif len(raw_event) == 3:
                node_path, stream_mode_label, event_payload = raw_event
        else:
            stream_mode_label = "values"
            event_payload = raw_event

        # Store based on stream mode
        if stream_mode_label == "messages":
            await store_sse_event(
                run_id,
                event_id,
                "messages",
                {
                    "type": "messages_stream",
                    "message_chunk": event_payload[0]
                    if isinstance(event_payload, tuple) and len(event_payload) >= 1
                    else event_payload,
                    "metadata": event_payload[1]
                    if isinstance(event_payload, tuple) and len(event_payload) >= 2
                    else None,
                    "node_path": node_path,
                },
            )
        elif stream_mode_label == "values":
            await store_sse_event(
                run_id,
                event_id,
                "values",
                {"type": "execution_values", "chunk": event_payload},
            )
        elif stream_mode_label == "end":
            await store_sse_event(
                run_id,
                event_id,
                "end",
                {
                    "type": "run_complete",
                    "status": event_payload.get("status", "completed"),
                    "final_output": event_payload.get("final_output"),
                },
            )
        # Add other stream modes as needed

    async def signal_run_cancelled(self, run_id: str):
        """Signal that a run was cancelled"""
        counter = self.event_counters.get(run_id, 0) + 1
        self.event_counters[run_id] = counter
        event_id = f"{run_id}_event_{counter}"

        broker = broker_manager.get_or_create_broker(run_id)
        if broker:
            await broker.put(event_id, ("end", {"status": "cancelled"}))

        broker_manager.cleanup_broker(run_id)

    async def signal_run_error(self, run_id: str, error_message: str):
        """Signal that a run encountered an error"""
        counter = self.event_counters.get(run_id, 0) + 1
        self.event_counters[run_id] = counter
        event_id = f"{run_id}_event_{counter}"

        broker = broker_manager.get_or_create_broker(run_id)
        if broker:
            await broker.put(
                event_id, ("end", {"status": "failed", "error": error_message})
            )

        broker_manager.cleanup_broker(run_id)

    def _extract_event_sequence(self, event_id: str) -> int:
        """Extract numeric sequence from event_id format: {run_id}_event_{sequence}"""
        try:
            return int(event_id.split("_event_")[-1])
        except (ValueError, IndexError):
            return 0

    async def stream_run_execution(
        self,
        run: Run,
        last_event_id: Optional[str] = None,
        cancel_on_disconnect: bool = False,
    ) -> AsyncIterator[str]:
        """Stream run execution with unified producer-consumer pattern"""
        run_id = run.run_id
        try:
            # -------- Replay stored events once --------
            if last_event_id:
                stored_events = await event_store.get_events_since(
                    run_id, last_event_id
                )
            else:
                stored_events = await event_store.get_all_events(run_id)

            last_sent_event_id: Optional[str] = last_event_id
            last_sent_sequence: int = (
                self._extract_event_sequence(last_event_id) if last_event_id else 0
            )

            # Replay stored events
            for ev in stored_events:
                sse_event = self._stored_event_to_sse(run_id, ev)
                if sse_event:
                    yield sse_event
                    last_sent_event_id = ev.id
                    last_sent_sequence = self._extract_event_sequence(ev.id)

            # If run already finished and there's nothing new to stream, exit
            broker = broker_manager.get_or_create_broker(run_id)
            if run.status in ["completed", "failed", "cancelled", "interrupted"] and (
                broker.is_finished()
            ):
                return

            # Consume live events from broker if run is still active
            if broker:
                async for event_id, raw_event in broker.aiter():
                    # Skip duplicates that were already replayed - compare numeric sequences
                    current_sequence = self._extract_event_sequence(event_id)
                    if (
                        last_sent_event_id is not None
                        and current_sequence <= last_sent_sequence
                    ):
                        continue

                    sse_event = await self._convert_raw_to_sse(event_id, raw_event)
                    if sse_event:
                        yield sse_event
                        last_sent_event_id = event_id
                        last_sent_sequence = current_sequence

        except asyncio.CancelledError:
            logger.debug(f"Stream cancelled for run {run_id}")
            if cancel_on_disconnect:
                # Attempt to cancel the background run task as well
                try:
                    task = active_runs.get(run_id)
                    if task and not task.done():
                        task.cancel()
                except Exception as e:
                    logger.warning(
                        f"Failed to cancel background task for run {run_id} on disconnect: {e}"
                    )
            raise
        except Exception as e:
            logger.error(f"Error in stream_run_execution for run {run_id}: {e}")
            yield create_error_event(str(e))

    async def _convert_raw_to_sse(self, event_id: str, raw_event: Any) -> Optional[str]:
        """Convert a raw event from broker to SSE format using the provided event_id"""
        # Parse raw_event similar to earlier logic
        node_path = None
        stream_mode_label = None
        event_payload = None

        if isinstance(raw_event, tuple):
            if len(raw_event) == 2:
                stream_mode_label, event_payload = raw_event
            elif len(raw_event) == 3:
                node_path, stream_mode_label, event_payload = raw_event
        else:
            stream_mode_label = "values"
            event_payload = raw_event

        # Convert to SSE event
        if stream_mode_label == "messages":
            return create_messages_event(event_payload, event_id=event_id)
        elif stream_mode_label == "values":
            return create_values_event(event_payload, event_id)
        elif stream_mode_label == "state":
            return create_state_event(event_payload, event_id)
        elif stream_mode_label == "logs":
            return create_logs_event(event_payload, event_id)
        elif stream_mode_label == "tasks":
            return create_tasks_event(event_payload, event_id)
        elif stream_mode_label == "subgraphs":
            return create_subgraphs_event(event_payload, event_id)
        elif stream_mode_label == "debug":
            return create_debug_event(event_payload, event_id)
        elif stream_mode_label == "end":
            return create_end_event(event_id)

        return None

    async def interrupt_run(self, run_id: str) -> bool:
        """Interrupt a running execution"""
        try:
            await self.signal_run_error(run_id, "Run was interrupted")
            await self._update_run_status(run_id, "interrupted")
            return True
        except Exception as e:
            logger.error(f"Error interrupting run {run_id}: {e}")
            return False

    async def cancel_run(self, run_id: str) -> bool:
        """Cancel a pending or running execution"""
        try:
            await self.signal_run_cancelled(run_id)
            await self._update_run_status(run_id, "cancelled")
            return True
        except Exception as e:
            logger.error(f"Error cancelling run {run_id}: {e}")
            return False

    async def _update_run_status(
        self, run_id: str, status: str, output: Any = None, error: str = None
    ):
        """Update run status in database using the shared updater."""
        try:
            from misc.utils import update_run_status

            await update_run_status(run_id, status, output, error)
        except Exception as e:
            logger.error(f"Error updating run status for {run_id}: {e}")

    def is_run_streaming(self, run_id: str) -> bool:
        """Check if run is currently active (has a broker)"""
        broker = broker_manager.get_broker(run_id)
        return broker is not None and not broker.is_finished()

    async def cleanup_run(self, run_id: str):
        """Clean up streaming resources for a run"""
        self.active_streams.pop(run_id, None)
        broker_manager.cleanup_broker(run_id)

    def _stored_event_to_sse(self, run_id: str, ev) -> Optional[str]:
        """Convert stored event object to SSE string"""
        if ev.event == "messages":
            message_chunk = ev.data.get("message_chunk")
            metadata = ev.data.get("metadata")
            if message_chunk is None:
                return None
            message_data = (
                (message_chunk, metadata) if metadata is not None else message_chunk
            )
            return create_messages_event(message_data, event_id=ev.id)
        elif ev.event == "values":
            return create_values_event(ev.data.get("chunk"), ev.id)
        elif ev.event == "metadata":
            return create_metadata_event(run_id, ev.id)
        elif ev.event == "state":
            return create_state_event(ev.data.get("state"), ev.id)
        elif ev.event == "logs":
            return create_logs_event(ev.data.get("logs"), ev.id)
        elif ev.event == "tasks":
            return create_tasks_event(ev.data.get("tasks"), ev.id)
        elif ev.event == "subgraphs":
            return create_subgraphs_event(ev.data.get("subgraphs"), ev.id)
        elif ev.event == "debug":
            return create_debug_event(ev.data.get("debug"), ev.id)
        elif ev.event == "events":
            return create_events_event(ev.data.get("event"), ev.id)
        elif ev.event == "end":
            return create_end_event(ev.id)
        elif ev.event == "error":
            return create_error_event(ev.data.get("error"), ev.id)
        return None


# Global streaming service instance
streaming_service = StreamingService()
