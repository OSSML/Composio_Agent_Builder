import asyncio
from typing import Dict

# NOTE: We keep only an in-memory task registry for asyncio.Task handles.
# All run metadata/state is persisted via ORM.
active_runs: Dict[str, asyncio.Task] = {}
