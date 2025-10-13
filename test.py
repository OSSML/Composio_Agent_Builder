import asyncio
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from react_agent.graph import graph, InputState

load_dotenv()

async def main() -> None:
    async for raw_event in graph.astream(
            InputState(
                messages=[HumanMessage(content="Fetch my latest documents from google docs.")],
            )
    ):
        print(raw_event)

asyncio.run(main())