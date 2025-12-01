"""Unit tests for webhook handler."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from meshcore_api.webhook.handler import WebhookHandler


@pytest.mark.asyncio
class TestWebhookHandlerInit:
    """Test WebhookHandler initialization."""

    async def test_init_with_all_urls(self):
        """Test initialization with all webhook URLs configured."""
        handler = WebhookHandler(
            message_direct_url="https://example.com/direct",
            message_channel_url="https://example.com/channel",
            advertisement_url="https://example.com/advert",
        )
        assert handler.message_direct_url == "https://example.com/direct"
        assert handler.message_channel_url == "https://example.com/channel"
        assert handler.advertisement_url == "https://example.com/advert"
        assert handler.timeout == 5
        assert handler.retry_count == 3
        await handler.close()

    async def test_init_with_no_urls(self):
        """Test initialization with no webhook URLs configured."""
        handler = WebhookHandler()
        assert handler.message_direct_url is None
        assert handler.message_channel_url is None
        assert handler.advertisement_url is None
        await handler.close()

    async def test_init_custom_timeout_and_retry(self):
        """Test initialization with custom timeout and retry count."""
        handler = WebhookHandler(timeout=10, retry_count=5)
        assert handler.timeout == 10
        assert handler.retry_count == 5
        await handler.close()

    async def test_init_event_url_mapping(self):
        """Test event type to URL mapping is set up correctly."""
        handler = WebhookHandler(
            message_direct_url="https://example.com/direct",
            message_channel_url="https://example.com/channel",
            advertisement_url="https://example.com/advert",
        )
        assert handler._event_url_map["CONTACT_MSG_RECV"] == "https://example.com/direct"
        assert handler._event_url_map["CHANNEL_MSG_RECV"] == "https://example.com/channel"
        assert handler._event_url_map["ADVERTISEMENT"] == "https://example.com/advert"
        assert handler._event_url_map["NEW_ADVERT"] == "https://example.com/advert"
        await handler.close()

    async def test_init_jsonpath_expressions(self):
        """Test JSONPath expressions are compiled correctly."""
        handler = WebhookHandler(
            message_direct_jsonpath="$.data.text",
            message_channel_jsonpath="$.data",
            advertisement_jsonpath="$",
        )
        assert "CONTACT_MSG_RECV" in handler._jsonpath_map
        assert "CHANNEL_MSG_RECV" in handler._jsonpath_map
        assert "ADVERTISEMENT" in handler._jsonpath_map
        await handler.close()


@pytest.mark.asyncio
class TestWebhookHandlerCompileJsonpath:
    """Test JSONPath compilation."""

    async def test_compile_valid_jsonpath(self):
        """Test compiling a valid JSONPath expression."""
        handler = WebhookHandler()
        # Should have compiled the default "$" expressions
        assert handler._jsonpath_map["CONTACT_MSG_RECV"] is not None
        await handler.close()

    async def test_compile_invalid_jsonpath_falls_back_to_root(self):
        """Test invalid JSONPath falls back to root expression."""
        # JSONPath that would cause parsing issues
        handler = WebhookHandler(message_direct_jsonpath="[invalid")
        # Should have fallen back to "$" (root expression)
        assert handler._jsonpath_map["CONTACT_MSG_RECV"] is not None
        await handler.close()


@pytest.mark.asyncio
class TestWebhookHandlerApplyJsonpath:
    """Test JSONPath application."""

    async def test_apply_jsonpath_root(self):
        """Test applying root JSONPath returns full payload."""
        handler = WebhookHandler(message_direct_jsonpath="$")
        payload = {"event_type": "CONTACT_MSG_RECV", "data": {"text": "Hello"}}
        result = handler._apply_jsonpath("CONTACT_MSG_RECV", payload)
        assert result == payload
        await handler.close()

    async def test_apply_jsonpath_nested(self):
        """Test applying nested JSONPath returns filtered data."""
        handler = WebhookHandler(message_direct_jsonpath="$.data.text")
        payload = {"event_type": "CONTACT_MSG_RECV", "data": {"text": "Hello"}}
        result = handler._apply_jsonpath("CONTACT_MSG_RECV", payload)
        assert result == "Hello"
        await handler.close()

    async def test_apply_jsonpath_no_matches(self):
        """Test JSONPath with no matches returns full payload."""
        handler = WebhookHandler(message_direct_jsonpath="$.nonexistent")
        payload = {"event_type": "CONTACT_MSG_RECV", "data": {"text": "Hello"}}
        result = handler._apply_jsonpath("CONTACT_MSG_RECV", payload)
        # Should return full payload when no matches
        assert result == payload
        await handler.close()

    async def test_apply_jsonpath_unknown_event_type(self):
        """Test applying JSONPath for unknown event type."""
        handler = WebhookHandler()
        payload = {"event_type": "UNKNOWN", "data": {}}
        result = handler._apply_jsonpath("UNKNOWN", payload)
        # Should return full payload for unknown types
        assert result == payload
        await handler.close()


@pytest.mark.asyncio
class TestWebhookHandlerSendEvent:
    """Test send_event method."""

    async def test_send_event_no_url_configured(self):
        """Test send_event does nothing when no URL configured."""
        handler = WebhookHandler()
        # Should not raise, just log and return
        await handler.send_event("CONTACT_MSG_RECV", {"text": "Hello"})
        await handler.close()

    async def test_send_event_success(self):
        """Test send_event successfully sends webhook."""
        handler = WebhookHandler(message_direct_url="https://example.com/direct")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch.object(handler.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await handler.send_event("CONTACT_MSG_RECV", {"text": "Hello"})
            mock_post.assert_called_once()

        await handler.close()

    async def test_send_event_includes_timestamp(self):
        """Test send_event includes timestamp in payload."""
        handler = WebhookHandler(message_direct_url="https://example.com/direct")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch.object(handler.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await handler.send_event("CONTACT_MSG_RECV", {"text": "Hello"})

            call_kwargs = mock_post.call_args
            payload = call_kwargs.kwargs.get("json", {})
            assert "timestamp" in payload
            assert payload["event_type"] == "CONTACT_MSG_RECV"
            assert payload["data"] == {"text": "Hello"}

        await handler.close()


@pytest.mark.asyncio
class TestWebhookHandlerSendWebhook:
    """Test _send_webhook method."""

    async def test_send_webhook_success(self):
        """Test successful webhook delivery."""
        handler = WebhookHandler()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch.object(handler.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await handler._send_webhook("https://example.com/webhook", {"event": "test"})
            assert mock_post.call_count == 1

        await handler.close()

    async def test_send_webhook_retry_on_http_error(self):
        """Test webhook retries on HTTP errors."""
        handler = WebhookHandler(retry_count=2)

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Server Error", request=MagicMock(), response=mock_response
            )
        )

        with patch.object(handler.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await handler._send_webhook("https://example.com/webhook", {"event": "test"})
            # Should attempt 1 initial + 2 retries = 3 total
            assert mock_post.call_count == 3

        await handler.close()

    async def test_send_webhook_retry_on_timeout(self):
        """Test webhook retries on timeout."""
        handler = WebhookHandler(retry_count=1)

        with patch.object(handler.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Timeout")
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await handler._send_webhook("https://example.com/webhook", {"event": "test"})
            # Should attempt 1 initial + 1 retry = 2 total
            assert mock_post.call_count == 2

        await handler.close()

    async def test_send_webhook_no_retries(self):
        """Test webhook with zero retry count only makes one attempt."""
        handler = WebhookHandler(retry_count=0)

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Server Error", request=MagicMock(), response=mock_response
            )
        )

        with patch.object(handler.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await handler._send_webhook("https://example.com/webhook", {"event": "test"})
            # Should only attempt once (no retries)
            assert mock_post.call_count == 1

        await handler.close()

    async def test_send_webhook_string_payload(self):
        """Test sending string payload as plain text."""
        handler = WebhookHandler()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch.object(handler.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await handler._send_webhook("https://example.com/webhook", "Hello World")

            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["content"] == "Hello World"
            assert call_kwargs["headers"]["Content-Type"] == "text/plain"

        await handler.close()

    async def test_send_webhook_primitive_payload(self):
        """Test sending primitive payload (number) as JSON."""
        handler = WebhookHandler()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch.object(handler.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await handler._send_webhook("https://example.com/webhook", 42)

            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["content"] == "42"
            assert call_kwargs["headers"]["Content-Type"] == "application/json"

        await handler.close()

    async def test_send_webhook_list_payload(self):
        """Test sending list payload as JSON."""
        handler = WebhookHandler()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch.object(handler.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await handler._send_webhook("https://example.com/webhook", [1, 2, 3])

            call_kwargs = mock_post.call_args.kwargs
            assert "json" in call_kwargs
            assert call_kwargs["json"] == [1, 2, 3]

        await handler.close()

    async def test_send_webhook_generic_exception(self):
        """Test webhook handles generic exceptions."""
        handler = WebhookHandler(retry_count=1)

        with patch.object(handler.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = Exception("Generic error")
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await handler._send_webhook("https://example.com/webhook", {"event": "test"})
            # Should still retry
            assert mock_post.call_count == 2

        await handler.close()


@pytest.mark.asyncio
class TestWebhookHandlerClose:
    """Test webhook handler close method."""

    async def test_close(self):
        """Test closing the HTTP client."""
        handler = WebhookHandler()
        await handler.close()
        # Should complete without error
        assert True
