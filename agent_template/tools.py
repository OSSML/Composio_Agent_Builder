from composio import Composio
from dotenv import load_dotenv

from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv()

tools = None

async def fetch_tools():
    global tools
    if tools is None:
        composio = Composio()
        userId = "hey@example.com"
        # Create a tool router session
        session = composio.experimental.tool_router.create_session(
            user_id=userId,
        )

        mcpUrl = session['url']

        client = MultiServerMCPClient(
            {
                "composio": {
                    "url": mcpUrl,
                    "transport": "streamable_http"
                }
            }
        )
        tools = await client.get_tools()

    return tools
