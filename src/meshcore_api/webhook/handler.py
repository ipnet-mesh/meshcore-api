"""WebhookHandler for sending HTTP notifications on MeshCore events."""

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class WebhookHandler:
    """Handles sending webhook HTTP POST requests for MeshCore events."""

    def __init__(
        self,
        message_direct_url: Optional[str] = None,
        message_channel_url: Optional[str] = None,
        advertisement_url: Optional[str] = None,
        timeout: int = 5,
        retry_count: int = 3,
    ):
        """
        Initialize webhook handler with event-specific URLs.

        Args:
            message_direct_url: URL for direct/contact message events
            message_channel_url: URL for channel message events
            advertisement_url: URL for advertisement events
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

        logger.info(
            f"WebhookHandler initialized: "
            f"direct={message_direct_url is not None}, "
            f"channel={message_channel_url is not None}, "
            f"advertisement={advertisement_url is not None}"
        )

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

        # Send webhook with retry logic
        await self._send_webhook(url, payload)

    async def _send_webhook(self, url: str, payload: dict[str, Any]) -> None:
        """
        Send HTTP POST to webhook URL with retry logic and exponential backoff.

        Always attempts delivery at least once. If retry_count is 0, only the initial
        attempt is made. If retry_count > 0, makes initial attempt plus up to retry_count
        additional retries.

        Args:
            url: Webhook URL to POST to
            payload: JSON payload to send
        """
        total_attempts = self.retry_count + 1  # Initial attempt + retries

        for attempt in range(total_attempts):
            try:
                response = await self.client.post(
                    url, json=payload, headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()

                logger.debug(
                    f"Webhook sent successfully: {payload['event_type']} to {url} "
                    f"(status={response.status_code})"
                )
                return

            except httpx.HTTPStatusError as e:
                logger.warning(
                    f"Webhook HTTP error (attempt {attempt + 1}/{total_attempts}): "
                    f"{e.response.status_code} - {url}"
                )
            except httpx.TimeoutException:
                logger.warning(
                    f"Webhook timeout (attempt {attempt + 1}/{total_attempts}): {url}"
                )
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
            f"{payload['event_type']} to {url}"
        )

    async def close(self) -> None:
        """Close HTTP client connection pool."""
        await self.client.aclose()
        logger.debug("WebhookHandler closed")
