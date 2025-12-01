"""WebhookHandler for sending HTTP notifications on MeshCore events."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Optional

import httpx
from jsonpath_ng import parse as jsonpath_parse
from jsonpath_ng.exceptions import JSONPathError

logger = logging.getLogger(__name__)


class WebhookHandler:
    """Handles sending webhook HTTP POST requests for MeshCore events."""

    def __init__(
        self,
        message_direct_url: Optional[str] = None,
        message_channel_url: Optional[str] = None,
        advertisement_url: Optional[str] = None,
        message_direct_jsonpath: str = "$",
        message_channel_jsonpath: str = "$",
        advertisement_jsonpath: str = "$",
        timeout: int = 5,
        retry_count: int = 3,
    ):
        """
        Initialize webhook handler with event-specific URLs.

        Args:
            message_direct_url: URL for direct/contact message events
            message_channel_url: URL for channel message events
            advertisement_url: URL for advertisement events
            message_direct_jsonpath: JSONPath expression for direct message payload filtering
            message_channel_jsonpath: JSONPath expression for channel message payload filtering
            advertisement_jsonpath: JSONPath expression for advertisement payload filtering
            timeout: HTTP request timeout in seconds
            retry_count: Number of retry attempts on failure
        """
        self.message_direct_url = message_direct_url
        self.message_channel_url = message_channel_url
        self.advertisement_url = advertisement_url
        self.timeout = timeout
        self.retry_count = retry_count
        self.client = httpx.AsyncClient(timeout=timeout)

        # Event type to URL mapping
        self._event_url_map = {
            "CONTACT_MSG_RECV": self.message_direct_url,
            "CHANNEL_MSG_RECV": self.message_channel_url,
            "ADVERTISEMENT": self.advertisement_url,
            "NEW_ADVERT": self.advertisement_url,
        }

        # Compile JSONPath expressions
        self._jsonpath_map = {}
        self._compile_jsonpath("CONTACT_MSG_RECV", message_direct_jsonpath)
        self._compile_jsonpath("CHANNEL_MSG_RECV", message_channel_jsonpath)
        self._compile_jsonpath("ADVERTISEMENT", advertisement_jsonpath)
        self._compile_jsonpath("NEW_ADVERT", advertisement_jsonpath)

        logger.info(
            f"WebhookHandler initialized: "
            f"direct={message_direct_url is not None} (jsonpath={message_direct_jsonpath}), "
            f"channel={message_channel_url is not None} (jsonpath={message_channel_jsonpath}), "
            f"advertisement={advertisement_url is not None} (jsonpath={advertisement_jsonpath})"
        )

    def _compile_jsonpath(self, event_type: str, expression: str) -> None:
        """
        Compile and store JSONPath expression for an event type.

        Args:
            event_type: Event type to associate with this expression
            expression: JSONPath expression string
        """
        try:
            compiled = jsonpath_parse(expression)
            self._jsonpath_map[event_type] = compiled
            logger.debug(f"Compiled JSONPath for {event_type}: {expression}")
        except JSONPathError as e:
            logger.error(
                f"Invalid JSONPath expression for {event_type}: '{expression}' - {e}. "
                f"Falling back to '$' (full payload)"
            )
            # Fall back to root expression
            self._jsonpath_map[event_type] = jsonpath_parse("$")
        except Exception as e:
            logger.error(
                f"Failed to compile JSONPath for {event_type}: {e}. "
                f"Falling back to '$' (full payload)"
            )
            self._jsonpath_map[event_type] = jsonpath_parse("$")

    def _apply_jsonpath(self, event_type: str, payload: dict[str, Any]) -> Any:
        """
        Apply JSONPath filtering to payload.

        Args:
            event_type: Event type to determine which JSONPath expression to use
            payload: Full webhook payload

        Returns:
            Filtered data based on JSONPath expression, or full payload on error
        """
        jsonpath_expr = self._jsonpath_map.get(event_type)
        if not jsonpath_expr:
            logger.warning(f"No JSONPath expression for {event_type}, using full payload")
            return payload

        try:
            matches = jsonpath_expr.find(payload)

            if not matches:
                logger.warning(
                    f"JSONPath expression for {event_type} returned no results. "
                    f"Sending full payload."
                )
                return payload

            # If single match, return its value
            if len(matches) == 1:
                return matches[0].value

            # Multiple matches, return as list
            return [match.value for match in matches]

        except Exception as e:
            logger.error(
                f"Error applying JSONPath for {event_type}: {e}. " f"Sending full payload."
            )
            return payload

    async def send_event(self, event_type: str, data: dict[str, Any]) -> None:
        """
        Route event to appropriate webhook URL and send POST request.

        Args:
            event_type: Type of MeshCore event (e.g., "CONTACT_MSG_RECV")
            data: Event payload data to send
        """
        # Get URL for this event type
        url = self._event_url_map.get(event_type)

        if not url:
            # No webhook configured for this event type
            logger.debug(f"No webhook URL configured for event type: {event_type}")
            return

        # Build webhook payload
        payload = {
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": data,
        }

        # Apply JSONPath filtering
        filtered_payload = self._apply_jsonpath(event_type, payload)

        # Send webhook with retry logic
        await self._send_webhook(url, filtered_payload)

    async def _send_webhook(self, url: str, payload: Any) -> None:
        """
        Send HTTP POST to webhook URL with retry logic and exponential backoff.

        Always attempts delivery at least once. If retry_count is 0, only the initial
        attempt is made. If retry_count > 0, makes initial attempt plus up to retry_count
        additional retries.

        Args:
            url: Webhook URL to POST to
            payload: Payload to send (can be dict, list, string, number, or boolean)
        """
        total_attempts = self.retry_count + 1  # Initial attempt + retries

        # Prepare request based on payload type
        if isinstance(payload, (dict, list)):
            # Send as JSON
            request_kwargs = {"json": payload, "headers": {"Content-Type": "application/json"}}
            event_type = (
                payload.get("event_type", "unknown") if isinstance(payload, dict) else "unknown"
            )
        elif isinstance(payload, str):
            # Send as plain text
            request_kwargs = {"content": payload, "headers": {"Content-Type": "text/plain"}}
            event_type = "unknown"
        else:
            # Send primitives (numbers, booleans) as JSON
            request_kwargs = {
                "content": json.dumps(payload),
                "headers": {"Content-Type": "application/json"},
            }
            event_type = "unknown"

        for attempt in range(total_attempts):
            try:
                response = await self.client.post(url, **request_kwargs)
                response.raise_for_status()

                logger.debug(
                    f"Webhook sent successfully: {event_type} to {url} "
                    f"(status={response.status_code})"
                )
                return

            except httpx.HTTPStatusError as e:
                logger.warning(
                    f"Webhook HTTP error (attempt {attempt + 1}/{total_attempts}): "
                    f"{e.response.status_code} - {url}"
                )
            except httpx.TimeoutException:
                logger.warning(f"Webhook timeout (attempt {attempt + 1}/{total_attempts}): {url}")
            except Exception as e:
                logger.warning(
                    f"Webhook error (attempt {attempt + 1}/{total_attempts}): "
                    f"{type(e).__name__}: {e}"
                )

            # Exponential backoff: 2s, 4s, 8s (only if there are more attempts)
            if attempt < total_attempts - 1:
                delay = 2 ** (attempt + 1)
                await asyncio.sleep(delay)

        # All attempts exhausted
        logger.error(
            f"Webhook failed after {total_attempts} attempts "
            f"(1 initial + {self.retry_count} retries): "
            f"{event_type} to {url}"
        )

    async def close(self) -> None:
        """Close HTTP client connection pool."""
        await self.client.aclose()
        logger.debug("WebhookHandler closed")
