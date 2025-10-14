"""Define a custom Reasoning and Action agent.

Works with a chat model with tool calling support.
"""
import os
from datetime import UTC, datetime
from typing import Literal, cast, Dict, List

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode

from agent_builder.state import InputState, State
from agent_builder.tools import fetch_tools
from agent_builder.prompts import SYSTEM_PROMPT

load_dotenv()


async def call_model(
    state: State
) -> dict[str, list[AIMessage]]:
    """Call the LLM powering our "agent".

    This function prepares the prompt, initializes the model, and processes the response.

    Args:
        state (State): The current state of the conversation.
        config (RunnableConfig): Configuration for the model run.

    Returns:
        dict: A dictionary containing the model's response message.
    """
    print(os.getenv("GOOGLE_API_KEY"))
    # Initialize the model with tool binding. Change the model or add more tools here.
    model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=os.getenv("GOOGLE_API_KEY"))

    model = model.bind_tools(await fetch_tools())

    # Format the system prompt. Customize this to change the agent's behavior.
    system_message = SYSTEM_PROMPT.format(
        system_time=datetime.now(tz=UTC).isoformat()
    )

    # Get the model's response
    response = cast(
        "AIMessage",
        await model.ainvoke(
            [{"role": "system", "content": system_message}, *state.messages]
        ),
    )

    # Handle the case when it's the last step and the model still wants to use a tool
    if state.is_last_step and response.tool_calls:
        return {
            "messages": [
                AIMessage(
                    id=response.id,
                    content="Sorry, I could not find an answer to your question in the specified number of steps.",
                )
            ]
        }

    # Return the model's response as a list to be added to existing messages
    return {"messages": [response]}

async def execute_tools(
    state: State
) -> Dict[str, List[BaseMessage]]:
    """Execute tools dynamically based on the current context.

    This node gets the tool calls from the last AI message and executes them
    using a ToolExecutor initialized with tools from the runtime context.

    Args:
        state (State): The current state of the conversation.
        runtime (Runtime[Context]): The graph runtime containing the current context.

    Returns:
        dict: A dictionary containing the tool execution results as ToolMessages.
    """
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        # This should not be called if there are no tool calls
        return {}

    # Get the actual tool functions from the map
    selected_tools = await fetch_tools()

    # Create a ToolExecutor with only the selected tools for this run
    tool_executor = ToolNode(selected_tools)

    # Execute the tool calls
    response = await tool_executor.ainvoke(last_message.tool_calls)

    return response


# Define a new graph

builder = StateGraph(State, input_schema=InputState)

# Define the two nodes we will cycle between
builder.add_node(call_model)
builder.add_node("tools", execute_tools)

# Set the entrypoint as `call_model`
# This means that this node is the first one called
builder.add_edge("__start__", "call_model")


def route_model_output(state: State) -> Literal["__end__", "tools"]:
    """Determine the next node based on the model's output.

    This function checks if the model's last message contains tool calls.

    Args:
        state (State): The current state of the conversation.

    Returns:
        str: The name of the next node to call ("__end__" or "tools").
    """
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage):
        raise ValueError(
            f"Expected AIMessage in output edges, but got {type(last_message).__name__}"
        )
    # If there is no tool call, then we finish
    if not last_message.tool_calls:
        return "__end__"
    # Otherwise we execute the requested actions
    return "tools"


# Add a conditional edge to determine the next step after `call_model`
builder.add_conditional_edges(
    "call_model",
    # After call_model finishes running, the next node(s) are scheduled
    # based on the output from route_model_output
    route_model_output,
)

# Add a normal edge from `tools` to `call_model`
# This creates a cycle: after using tools, we always return to the model
builder.add_edge("tools", "call_model")

# Compile the builder into an executable graph
graph = builder.compile(name="ReAct Agent")

if __name__ == "__main__":
    import asyncio
    from langchain_core.messages import HumanMessage

    async def main() -> None:
        async for raw_event in graph.astream(
                InputState(
                    messages=[HumanMessage(content="Fetch my latest documents from google docs.")],
                )
        ):
            print(raw_event)
        # print(result)

    asyncio.run(main())