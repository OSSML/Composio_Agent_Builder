from composio import Composio
from dotenv import load_dotenv
import logging

from langchain_mcp_adapters.client import MultiServerMCPClient
from .config import settings

load_dotenv()
logger = logging.getLogger(__name__)

tools = None

async def  fetch_tools():
    global tools
    if tools is None:
        logger.info("Fetching tools...")
        composio = Composio()
        # Create a tool router session
        session = composio.experimental.tool_router.create_session(
            user_id=settings.USER_ID,
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
