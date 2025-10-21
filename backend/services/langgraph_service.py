"""LangGraph integration service with official patterns"""

import json
import os
import importlib.util
import logging
from typing import Dict, Any, TypeVar
from pathlib import Path
from langgraph.graph import StateGraph
from uuid import uuid5

from constants import ASSISTANT_NAMESPACE_UUID
from core.database import db_manager


logger = logging.getLogger(__name__)

State = TypeVar("State")


class LangGraphService:
    """Service to work with LangGraph CLI configuration and graphs"""

    def __init__(self, config_path: str = "aegra.json"):
        # Default path can be overridden via AEGRA_CONFIG or by placing aegra.json
        self.config_path = Path(config_path)
        self.config: dict[str, Any] | None = None
        self._graph_registry: dict[str, Any] = {}
        self._graph_cache: dict[str, Any] = {}

    async def initialize(self):
        """Load configuration file and setup graph registry.

        Resolution order:
        1) AEGRA_CONFIG env var (absolute or relative path)
        2) Explicit self.config_path if it exists
        3) aegra.json in CWD
        4) langgraph.json in CWD (fallback)
        """
        # 1) Env var override
        env_path = os.getenv("AEGRA_CONFIG")
        resolved_path: Path
        if env_path:
            resolved_path = Path(env_path)
        # 2) Provided path if exists
        elif self.config_path and Path(self.config_path).exists():
            resolved_path = Path(self.config_path)
        else:
            resolved_path = Path("langgraph.json")

        if not resolved_path.exists():
            raise ValueError(
                "Configuration file not found. Expected one of: "
                "AEGRA_CONFIG path, ./aegra.json, or ./langgraph.json"
            )

        # Persist selected path for later reference
        self.config_path = resolved_path

        with self.config_path.open() as f:
            self.config = json.load(f)

        # Load graph registry from config
        self._load_graph_registry()

        # Pre-register assistants for each graph using deterministic UUIDs so
        # clients can pass graph_id directly.
        await self._ensure_default_assistants()

    def _load_graph_registry(self):
        """Load graph definitions from aegra.json"""
        graphs_config = self.config.get("graphs", {})

        for graph_id, graph_path in graphs_config.items():
            # Parse path format: "./graphs/weather_agent.py:graph"
            if ":" not in graph_path:
                raise ValueError(f"Invalid graph path format: {graph_path}")

            file_path, export_name = graph_path.split(":", 1)
            self._graph_registry[graph_id] = {
                "file_path": file_path,
                "export_name": export_name,
            }

    async def _ensure_default_assistants(self) -> None:
        """Create a default assistant per graph with deterministic UUID.

        Uses uuid5 with a fixed namespace so that the same graph_id maps
        to the same assistant_id across restarts. Idempotent.
        """
        from sqlalchemy import select

        from core.orm import Assistant as AssistantORM
        from core.orm import get_session

        # Fixed namespace used to derive assistant IDs from graph IDs
        NS = ASSISTANT_NAMESPACE_UUID
        session_gen = get_session()
        session = await session_gen.__anext__()
        try:
            for graph_id in self._graph_registry:
                assistant_id = str(uuid5(NS, graph_id))
                existing = await session.scalar(
                    select(AssistantORM).where(
                        AssistantORM.assistant_id == assistant_id
                    )
                )
                if existing:
                    continue
                session.add(
                    AssistantORM(
                        assistant_id=assistant_id,
                        name=graph_id,
                        description=f"Default assistant for graph '{graph_id}'",
                        graph_id=graph_id,
                        config={},
                    )
                )
            await session.commit()
        finally:
            await session.close()

    async def get_graph(
        self, graph_id: str, force_reload: bool = False
    ) -> StateGraph[Any]:
        """Get a compiled graph by ID with caching and LangGraph integration"""
        if graph_id not in self._graph_registry:
            raise ValueError(f"Graph not found: {graph_id}")

        # Return cached graph if available and not forcing reload
        if not force_reload and graph_id in self._graph_cache:
            return self._graph_cache[graph_id]

        graph_info = self._graph_registry[graph_id]

        # Load graph from file
        base_graph = await self._load_graph_from_file(graph_id, graph_info)

        if hasattr(base_graph, "compile"):
            # The module exported an *uncompiled* StateGraph – compile it now with
            # a Postgres checkpointer for durable state.
            checkpointer_cm = await db_manager.get_checkpointer()
            store_cm = await db_manager.get_store()
            logger.info(f"🔧 Compiling graph '{graph_id}' with Postgres persistence")
            compiled_graph = base_graph.compile(
                checkpointer=checkpointer_cm, store=store_cm
            )
        else:
            # Graph was already compiled by the module.  Create a shallow copy
            # that injects our Postgres checkpointer *unless* the author already
            # set one.
            checkpointer_cm = await db_manager.get_checkpointer()
            try:
                store_cm = await db_manager.get_store()
                compiled_graph = base_graph.copy(
                    update={"checkpointer": checkpointer_cm, "store": store_cm}
                )
            except Exception:
                # Fallback: property may be immutably set; run as-is with warning
                logger.warning(
                    f"⚠️  Pre-compiled graph '{graph_id}' does not support checkpointer injection; running without persistence"
                )
                compiled_graph = base_graph

        # Cache the compiled graph
        self._graph_cache[graph_id] = compiled_graph

        return compiled_graph

    async def get_graph_raw(self, graph_id: str) -> Any:
        """Get the raw (uncompiled) graph from the module."""
        if graph_id not in self._graph_registry:
            raise ValueError(f"Graph not found: {graph_id}")

        graph_info = self._graph_registry[graph_id]

        # Load graph from file
        base_graph = await self._load_graph_from_file(graph_id, graph_info)

        return base_graph

    async def _load_graph_from_file(self, graph_id: str, graph_info: dict[str, str]):
        """Load graph from filesystem"""
        file_path = Path(graph_info["file_path"])
        if not file_path.exists():
            raise ValueError(f"Graph file not found: {file_path}")

        # Dynamic import of graph module
        spec = importlib.util.spec_from_file_location(
            f"graphs.{graph_id}", str(file_path.resolve())
        )
        if spec is None or spec.loader is None:
            raise ValueError(f"Failed to load graph module: {file_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Get the exported graph
        export_name = graph_info["export_name"]
        if not hasattr(module, export_name):
            raise ValueError(f"Graph export not found: {export_name} in {file_path}")

        graph = getattr(module, export_name)

        # The graph should already be compiled in the module
        # If it needs our checkpointer/store, we'll handle that during execution
        return graph

    def list_graphs(self) -> dict[str, str]:
        """List all available graphs"""
        return {
            graph_id: info["file_path"]
            for graph_id, info in self._graph_registry.items()
        }

    def invalidate_cache(self, graph_id: str = None):
        """Invalidate graph cache for hot-reload"""
        if graph_id:
            self._graph_cache.pop(graph_id, None)
        else:
            self._graph_cache.clear()

    def get_config(self) -> dict[str, Any] | None:
        """Get loaded configuration"""
        return self.config

    def get_dependencies(self) -> list:
        """Get dependencies from config"""
        if self.config is None:
            return []
        return self.config.get("dependencies", [])


# Global service instance
_langgraph_service = None


def get_langgraph_service() -> LangGraphService:
    """Get global LangGraph service instance"""
    global _langgraph_service
    if _langgraph_service is None:
        _langgraph_service = LangGraphService()
    return _langgraph_service


def create_thread_config(thread_id: str, additional_config: Dict = None) -> Dict:
    """Create LangGraph configuration for a specific thread"""
    base_config = {"configurable": {"thread_id": thread_id}}

    if additional_config:
        base_config.update(additional_config)

    return base_config


def create_run_config(
    run_id: str,
    thread_id: str,
    additional_config: Dict = None,
    checkpoint: Dict | None = None,
) -> Dict:
    """Create LangGraph configuration for a specific run with full context.

    The function is *additive*: it never removes or renames anything the client
    supplied.  We simply ensure a `configurable` dict exists and then merge a
    few server-side keys so graph nodes can rely on them.
    """
    from copy import deepcopy

    cfg: Dict = deepcopy(additional_config) if additional_config else {}

    # Ensure a configurable section exists
    cfg.setdefault("configurable", {})

    # Merge server-provided fields (do NOT overwrite if client already set)
    cfg["configurable"].setdefault("thread_id", thread_id)
    cfg["configurable"].setdefault("run_id", run_id)

    # Apply checkpoint parameters if provided
    if checkpoint and isinstance(checkpoint, dict):
        cfg["configurable"].update(
            {k: v for k, v in checkpoint.items() if v is not None}
        )

    return cfg
