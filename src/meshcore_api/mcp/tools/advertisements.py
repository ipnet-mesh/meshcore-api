"""Advertisement tools for MeshCore API."""

import logging
from typing import Optional

from ..client import APIError, api_get, api_post

logger = logging.getLogger(__name__)


def register_tools(mcp):
    """Register advertisement tools with the MCP server."""

    @mcp.tool()
    async def meshcore_get_advertisements(
        node_public_key: Optional[str] = None,
        adv_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> str:
        """
        Query advertisements from the mesh network.

        Args:
            node_public_key: Filter by node public key (full 64 hex characters)
            adv_type: Filter by advertisement type (none/chat/repeater/room)
            start_date: Filter advertisements after this date (ISO 8601 format)
            end_date: Filter advertisements before this date (ISO 8601 format)
            limit: Maximum number of advertisements to return (1-1000, default: 100)
            offset: Number of advertisements to skip (default: 0)

        Returns:
            Formatted list of advertisements
        """
        try:
            params = {
                "node_public_key": node_public_key,
                "adv_type": adv_type,
                "start_date": start_date,
                "end_date": end_date,
                "limit": limit,
                "offset": offset,
            }

            result = await api_get("/api/v1/advertisements", params=params)

            advertisements = result.get("advertisements", [])
            total = result.get("total", 0)

            if not advertisements:
                return "No advertisements found"

            output = f"Advertisements ({len(advertisements)} of {total} total):\n"
            output += "=" * 60 + "\n"

            for i, adv in enumerate(advertisements, 1):
                output += f"\n[{i}] Advertisement\n"
                output += f"  ID: {adv.get('id', 'N/A')}\n"
                output += f"  Public Key: {adv.get('public_key', 'N/A')}\n"
                output += f"  Type: {adv.get('adv_type', 'N/A')}\n"
                output += f"  Name: {adv.get('name', 'N/A')}\n"
                if adv.get("flags") is not None:
                    output += f"  Flags: {adv.get('flags')}\n"
                output += f"  Received: {adv.get('received_at', 'N/A')}\n"
                output += "-" * 60 + "\n"

            return output

        except APIError as e:
            return f"Error querying advertisements: {e.message}"
        except Exception as e:
            logger.error(f"Unexpected error querying advertisements: {e}")
            return f"Error querying advertisements: {str(e)}"

    @mcp.tool()
    async def meshcore_send_advertisement(flood: bool = False) -> str:
        """
        Send an advertisement to announce this device on the mesh network.

        Args:
            flood: Enable flooding to propagate the advertisement further (default: false)

        Returns:
            Status message indicating success or failure
        """
        try:
            result = await api_post("/api/v1/commands/send_advert", json_data={"flood": flood})

            success = result.get("success", False)
            message = result.get("message", "Unknown result")
            queue_info = result.get("queue_info")

            output = f"Advertisement send {'succeeded' if success else 'failed'}: {message}"

            if queue_info:
                output += f"\n  Queue position: {queue_info.get('position', 'N/A')}"
                output += f"\n  Estimated wait: {queue_info.get('estimated_wait_seconds', 'N/A')}s"
                if queue_info.get("debounced"):
                    output += "\n  (Command was debounced)"

            return output

        except APIError as e:
            return f"Error sending advertisement: {e.message}"
        except Exception as e:
            logger.error(f"Unexpected error sending advertisement: {e}")
            return f"Error sending advertisement: {str(e)}"
