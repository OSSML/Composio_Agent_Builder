from __future__ import annotations

import os
from dataclasses import dataclass, field, fields


@dataclass(kw_only=True)
class Context:
    """The context for the agent."""

    system_prompt: str = field(
        metadata={
            "description": "The system prompt to use for the agent's interactions. "
            "This prompt sets the context and behavior for the agent."
        },
    )

    tools: list = field(
        metadata={
            "description": "A list of tools to use for the agent's interactions. "
            "Each tool is a string representing the slug of the tool."
        },
    )

    def __post_init__(self) -> None:
        """Fetch env vars for attributes that were not passed as args."""
        for f in fields(self):
            if not f.init:
                continue

            if getattr(self, f.name) == f.default:
                setattr(self, f.name, os.environ.get(f.name.upper(), f.default))
