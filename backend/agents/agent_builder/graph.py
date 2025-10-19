"""Define a custom Reasoning and Action agent.

Works with a chat model with tool calling support.
"""
import os
from typing import Literal, cast, Dict, List

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode

from agents.agent_builder.state import InputState, State
from core.tool_router import fetch_tools
from agents.agent_builder.prompts import SYSTEM_PROMPT
from agents.agent_builder.models import BuilderResponse

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
    # Initialize the model with tool binding. Change the model or add more tools here.
    # model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=os.getenv("GOOGLE_API_KEY"))
    model = ChatOpenAI(model="gpt-4.1-mini-2025-04-14")

    model = model.bind_tools(await fetch_tools())

    # Format the system prompt. Customize this to change the agent's behavior.
    system_message = SYSTEM_PROMPT

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


async def respond(state: State):
    # model_with_structured_output = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=os.getenv("GOOGLE_API_KEY"))
    model_with_structured_output = ChatOpenAI(model="gpt-4.1-mini-2025-04-14")
    model_with_structured_output = model_with_structured_output.with_structured_output(BuilderResponse)
    response = await model_with_structured_output.ainvoke(
        [HumanMessage(content=state.messages[-1].content)]
    )
    print(state.messages[-1].content)
    print(
        "response",
        response,
    )
    output = AIMessage(content=response.model_dump_json())
    # We return the final answer
    return {"messages": [output], "structured_output": response.model_dump_json()}


# Define a new graph

builder = StateGraph(State, input_schema=InputState)

# Define the two nodes we will cycle between
builder.add_node(call_model)
builder.add_node("tools", execute_tools)
builder.add_node("respond", respond)

# Set the entrypoint as `call_model`
# This means that this node is the first one called
builder.add_edge("__start__", "call_model")


def route_model_output(state: State) -> Literal["respond", "tools"]:
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
        return "respond"
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

builder.add_edge("respond", "__end__")

# Compile the builder into an executable graph
graph = builder.compile(name="Agent Builder")

if __name__ == "__main__":
    import asyncio
    from langchain_core.messages import HumanMessage

    async def main() -> None:
        async for raw_event in graph.astream(
                InputState(
                    messages=[HumanMessage(content="AI orchestrator: Fetch the PRs from github, draft in google docs and share the doc link in the slack channel.")],
                )
        ):
            print(raw_event)
        # print(result)
        # message = """```json\n{\n "system_prompt": "You are an AI assistant specialized in fetching GitHub Pull Requests, summarizing them in Google Docs, and sharing the summaries on Slack.\\n\\nYour goal is to automate the process of retrieving GitHub Pull Requests, compiling their details into a structured Google Doc, and then sharing a link to this document within a specified Slack channel to keep the team informed.\\n\\n**Tools:**\\n- GITHUB_FIND_PULL_REQUESTS\\n- GOOGLEDOCS_CREATE_DOCUMENT_MARKDOWN\\n- SLACK_SEND_MESSAGE\\n- GITHUB_LIST_PULL_REQUESTS\\n- GITHUB_GET_A_PULL_REQUEST\\n- GOOGLEDOCS_INSERT_TEXT_ACTION\\n- GOOGLEDOCS_GET_DOCUMENT_BY_ID\\n- SLACK_FIND_CHANNELS\\n- GOOGLEDRIVE_ADD_FILE_SHARING_PREFERENCE\\n\\n**Plan:**\\n- **S1**: Fetch all pull requests accessible to the authenticated user across repositories and paginate until completion. Return essential PR details needed for a concise markdown summary: PR number, title, author, base branch, head branch, state, merge status, creation date, last update date, labels, repository, and PR URL. Reference: [GitHub REST API - Pull Requests](https://docs.github.com/en/rest/pulls/pulls). Notes: If results span multiple pages, continue fetching until no more pages remain.\\n- **S2**: Create a new Google Docs document titled with a clear PR summary (e.g., \'Pull Requests Summary - YYYY-MM-DD\') and initialize it with a markdown-formatted overview of the retrieved PRs, including a compact bullet list with key fields per PR. Reference: [Google Docs API - Documents: create](https://developers.google.com/docs/api/reference/rest/v1/documents/create). (Note: If no PRs are returned, initialize the document with a note stating that no open PRs were found.)\\n- **S3**: Optional enhancement: augment the document by inserting per-PR sections or repository-grouped summaries (e.g., by repo) if the initial markdown needs deeper organization. Reference: [Google Docs API - BatchUpdate (InsertText)](https://developers.google.com/docs/api/reference/rest/v1/documents/batchUpdate).\\n- **S4**: Make the newly created Google Doc shareable (e.g., anyone with the link can view, or domain-specific sharing as required) so Slack recipients can access it. Reference: [Google Drive API - Permissions](https://developers.google.com/drive/api/v3/ref_permissions).\\n- **S5**: Locate the target Slack channel by name (or other criteria) to post the document link. Reference: [Slack API Conversations List](https://api.slack.com/methods/conversations.list).\\n- **S6**: Post a message in the identified Slack channel containing the Google Doc link and a brief summary of the PRs. This step exposes the content to a broader audience and should be performed only after confirmation. Reference: [Slack API chat.postMessage](https://api.slack.com/methods/chat.postMessage).\\n\\n**Instructions:**\\n- Strictly follow the provided plan and execute steps sequentially.\\n- Use only the tools specified in the \'Tools\' section.\\n- Ask for clarification only if you are completely blocked and cannot proceed with the plan.\\n\\n**Critical Instructions:**\\n- **Pagination**: If responses are inline (small response size): Continue until has_more=false or no next_cursor. If responses are stored in sandbox files (large datasets): Read the file to find the pagination (like has_more, next_cursor, cursor, etc.) field. If you think you will need many COMPOSIO_MULTI_EXECUTE_TOOL calls to fetch all the required data, use COMPOSIO_REMOTE_WORKBENCH to write the composio code to fetch the data until pagination field is false or all the data is fetched. Fetch in parallel if possible, like if page_number is supported.\\n- **Time Awareness**: This is the current date: 2025-10-17 and current time in epoch: 1760690212 in epoch seconds. For time sensitive operations, use these to construct parameters for tool calls appropriately even when the tool call requires relative times like \\"last week\\", \\"last month\\", \\"last 24 hours\\", etc. Ask user if you are not sure about the timezone and it is required for the task.\\n- **User Confirmation**: Always require explicit user approval before executing any tool with public impact or irreversible side-effects. MUST confirm before: sending messages (email, slack, discord, etc), overwriting or deleting existing data (databases, google sheets), or sharing resources visible to others. After asking for confirmation, you must stop any further tool calls until user replies. No confirmation needed for: read-only operations (list, fetch, search), local/private drafts (email draft), or creating new private resources (eg new google sheet not yet shared).\\n- Ensure to perform the task with High Accuracy and Completeness!",\n "tool_kits": [\n  "github",\n  "googledocs",\n  "slack",\n  "googledrive"\n ],\n "required_fields": [\n  "github_owner",\n  "github_repo",\n  "github_query",\n  "google_doc_title",\n  "google_doc_sharing_role",\n  "google_doc_sharing_type",\n  "slack_channel_name"\n ]\n}\n```"""
        # state = State(messages=[AIMessage(message)])
        # response = await respond(state)
        # print(response)


    asyncio.run(main())