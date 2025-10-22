from composio import Composio
from composio_langgraph import LanggraphProvider


def fetch_tools(tools: list):
    composio = Composio(provider=LanggraphProvider())
    tools = composio.tools.get("hey@example.com", tools=tools)
    return tools

if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv
    load_dotenv()
    # toolkits = ["GOOGLEDOCS"]
    # output = asyncio.run(fetch_tools(["googledocs"], ["GITHUB_FIND_PULL_REQUESTS", "GOOGLEDOCS_CREATE_DOCUMENT_MARKDOWN"]))
    # print(output)
    # import json
    # print(json.dumps(output, indent=4))