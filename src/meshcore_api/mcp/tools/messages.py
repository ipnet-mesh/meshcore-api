"""Message tools for MeshCore API."""

import logging
from typing import Optional

from ..client import APIError, api_get, api_post

logger = logging.getLogger(__name__)


def register_tools(mcp):
    """Register message tools with the MCP server."""

    @mcp.tool()
    async def meshcore_get_messages(
        sender_public_key: Optional[str] = None,
        channel_idx: Optional[int] = None,
        message_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> str:
        """
        Query messages from the mesh network.

        Args:
            sender_public_key: Filter by sender public key (full 64 hex characters)
            channel_idx: Filter by channel index (for channel messages)
            message_type: Filter by message type ('contact' or 'channel')
            start_date: Filter messages after this sender_timestamp (ISO 8601 format)
            end_date: Filter messages before this sender_timestamp (ISO 8601 format)
            limit: Maximum number of messages to return (1-1000, default: 100)
            offset: Number of messages to skip (default: 0)

        Returns:
            Formatted list of messages
        """
        try:
            params = {
                "sender_public_key": sender_public_key,
                "channel_idx": channel_idx,
                "message_type": message_type,
                "start_date": start_date,
                "end_date": end_date,
                "limit": limit,
                "offset": offset,
            }

            result = await api_get("/api/v1/messages", params=params)

            messages = result.get("messages", [])
            total = result.get("total", 0)

            if not messages:
                return "No messages found"

            output = f"Messages ({len(messages)} of {total} total):\n"
            output += "=" * 60 + "\n"

            for i, msg in enumerate(messages, 1):
                msg_type = msg.get("message_type", "unknown").upper()
                direction = msg.get("direction", "unknown")

                output += f"\n[{i}] {msg_type} MESSAGE ({direction})\n"
                output += f"  ID: {msg.get('id', 'N/A')}\n"

                if msg.get("pubkey_prefix"):
                    output += f"  Sender Key: {msg.get('pubkey_prefix')}\n"

                if msg.get("channel_idx") is not None:
                    output += f"  Channel: {msg.get('channel_idx')}\n"

                output += f"  Content: {msg.get('content', '')}\n"

                if msg.get("snr") is not None:
                    output += f"  SNR: {msg.get('snr')} dB\n"

                if msg.get("path_len") is not None:
                    output += f"  Path Length: {msg.get('path_len')} hops\n"

                if msg.get("sender_timestamp"):
                    output += f"  Sender Time: {msg.get('sender_timestamp')}\n"

                output += f"  Received: {msg.get('received_at', 'N/A')}\n"
                output += "-" * 60 + "\n"

            return output

        except APIError as e:
            return f"Error querying messages: {e.message}"
        except Exception as e:
            logger.error(f"Unexpected error querying messages: {e}")
            return f"Error querying messages: {str(e)}"

    @mcp.tool()
    async def meshcore_send_direct_message(
        destination: str, text: str, text_type: str = "plain"
    ) -> str:
        """
        Send a direct message to a specific node.

        Args:
            destination: Destination node public key (full 64 hex characters)
            text: Message text content (1-1000 characters)
            text_type: Text type - 'plain', 'cli_data', or 'signed_plain' (default: 'plain')

        Returns:
            Status message indicating success or failure
        """
        if len(destination) != 64:
            return (
                f"Error: destination must be a 64-character public key "
                f"(got {len(destination)} characters)"
            )

        if not text or len(text) > 1000:
            return "Error: text must be 1-1000 characters"

        try:
            result = await api_post(
                "/api/v1/commands/send_message",
                json_data={"destination": destination, "text": text, "text_type": text_type},
            )

            success = result.get("success", False)
            message = result.get("message", "Unknown result")
            queue_info = result.get("queue_info")
            estimated_delivery = result.get("estimated_delivery_ms")

            output = f"Direct message send {'succeeded' if success else 'failed'}: {message}"

            if estimated_delivery:
                output += f"\n  Estimated delivery: {estimated_delivery}ms"

            if queue_info:
                output += f"\n  Queue position: {queue_info.get('position', 'N/A')}"
                output += f"\n  Estimated wait: {queue_info.get('estimated_wait_seconds', 'N/A')}s"
                if queue_info.get("debounced"):
                    output += "\n  (Command was debounced)"

            return output

        except APIError as e:
            return f"Error sending direct message: {e.message}"
        except Exception as e:
            logger.error(f"Unexpected error sending direct message: {e}")
            return f"Error sending direct message: {str(e)}"

    @mcp.tool()
    async def meshcore_send_channel_message(text: str, flood: bool = False) -> str:
        """
        Send a broadcast message to all nodes on the channel.

        Args:
            text: Message text content (1-1000 characters)
            flood: Enable flooding to propagate the message further (default: false)

        Returns:
            Status message indicating success or failure
        """
        if not text or len(text) > 1000:
            return "Error: text must be 1-1000 characters"

        try:
            result = await api_post(
                "/api/v1/commands/send_channel_message", json_data={"text": text, "flood": flood}
            )

            success = result.get("success", False)
            message = result.get("message", "Unknown result")
            queue_info = result.get("queue_info")

            output = f"Channel message send {'succeeded' if success else 'failed'}: {message}"

            if queue_info:
                output += f"\n  Queue position: {queue_info.get('position', 'N/A')}"
                output += f"\n  Estimated wait: {queue_info.get('estimated_wait_seconds', 'N/A')}s"
                if queue_info.get("debounced"):
                    output += "\n  (Command was debounced)"

            return output

        except APIError as e:
            return f"Error sending channel message: {e.message}"
        except Exception as e:
            logger.error(f"Unexpected error sending channel message: {e}")
            return f"Error sending channel message: {str(e)}"
