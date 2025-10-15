import asyncio
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from agent_builder.graph import graph, InputState
from template_agent.graph import graph as template_graph

load_dotenv()

async def main() -> None:
    output = await graph.ainvoke(InputState(
                messages=[HumanMessage(content="AI Engineer Workspace Orchestrator – Compile release notes by pulling GitHub PRs, drafting in Docs, and posting to Slack.")],
            ))

    print(output.values())
    print(output)
    for message in output["messages"]:
        print(message.content)
    print(output["messages"][-1].content)

    async for raw_event in template_graph.astream(
            InputState(
                messages=[HumanMessage(content="Run")],
            ),
        context={"system_prompt": output}
    ):
        print(raw_event)


asyncio.run(main())