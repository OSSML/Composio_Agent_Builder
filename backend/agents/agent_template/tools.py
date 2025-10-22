from composio import Composio
from composio_langgraph import LanggraphProvider


def fetch_tools(tools: list):
    composio = Composio(provider=LanggraphProvider())
    tools = composio.tools.get("hey@example.com", tools=tools)
    return tools
