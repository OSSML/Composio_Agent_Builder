from typing import List

import structlog
from composio import Composio
from fastapi import APIRouter, HTTPException, Body

from core.config import settings


router = APIRouter()

composio = Composio()
logger = structlog.getLogger(__name__)


@router.post("/tools/connect", response_model=List[str])
async def connect_tools(
    tools: List[str] = Body(..., embed=True),
):
    """Fetch and connect tools from the tool repository."""
    try:
        output = []
        for tool in tools:
            auth_configs = composio.auth_configs.list(toolkit_slug=tool)
            if auth_configs.total_items == 0:
                tool_details = composio.toolkits.get(slug=tool)
                if tool_details.auth_config_details[0].mode == "NO_AUTH":
                    output.append("connected")
                    continue
                output.append(
                    composio.toolkits.authorize(
                        user_id=settings.USER_ID, toolkit=tool
                    ).redirect_url
                )
                continue

            auth_config_id = auth_configs.items[0].id
            connected_accounts = composio.connected_accounts.list(
                auth_config_ids=[auth_config_id]
            )

            active_account = False
            for item in connected_accounts.items:
                if item.data["status"] == "ACTIVE":
                    active_account = True
                    break

            if active_account:
                output.append("connected")
                continue

            # Removed all the Connected accounts which are not in ACTIVE status
            for item in connected_accounts.items:
                composio.connected_accounts.delete(item.id)

            output.append(
                composio.toolkits.authorize(
                    user_id=settings.USER_ID, toolkit=tool
                ).redirect_url
            )

        return output

    except Exception as e:
        raise HTTPException(500, f"Failed to connect tools: {str(e)}") from e


@router.post("/tools/disconnect", response_model=str)
async def disconnect_tool(
    tool: str = Body(..., embed=True),
):
    """Disconnect a tool from the tool repository."""
    try:
        tool_details = composio.toolkits.get(slug=tool)
        if tool_details.auth_config_details[0].mode == "NO_AUTH":
            return "connected"
        auth_configs = composio.auth_configs.list(toolkit_slug=tool)
        auth_config_id = auth_configs.items[0].id
        for item in composio.connected_accounts.list(
            auth_config_ids=[auth_config_id]
        ).items:
            composio.connected_accounts.delete(item.id)

        return composio.toolkits.authorize(
            user_id=settings.USER_ID, toolkit=tool
        ).redirect_url

    except Exception as e:
        raise HTTPException(500, f"Failed to disconnect tool: {str(e)}") from e
