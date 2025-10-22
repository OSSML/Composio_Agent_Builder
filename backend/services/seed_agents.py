import pathlib
import json

from core.orm import Assistant
from core.orm import _get_session_maker


async def seed_agents(directory_path: pathlib.Path):
    session_maker = _get_session_maker()
    async with session_maker() as session:
        for file in directory_path.iterdir():
            if file.is_file():
                with open(file, "rb") as f:
                    agent = json.load(f)
                assistant = Assistant(
                    name=agent["name"],
                    description=agent["description"],
                    config=agent["config"],
                    context=agent["context"],
                    tool_kits=agent["tool_kits"],
                    required_fields=agent["required_fields"],
                    graph_id="agent_template",
                )
                session.add(assistant)
        await session.commit()
