import asyncio
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from agent_builder.graph import graph, InputState
from template_agent.graph import graph as template_graph

load_dotenv()

async def main() -> None:
    output = graph.invoke(InputState(
                messages=[HumanMessage(content="create a assistant that can access my google docs and calendar.")],
            ))

    async for raw_event in template_graph.astream(
            InputState(
                messages=[HumanMessage(content="Run")],
            ),
        context={"system_prompt": output}
    ):
        print(raw_event)


asyncio.run(main())