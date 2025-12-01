"""Shared pytest fixtures for MeshCore API tests."""

import asyncio
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from meshcore_api.api.app import create_app
from meshcore_api.config import Config
from meshcore_api.database.engine import DatabaseEngine
from meshcore_api.database.models import Base
from meshcore_api.meshcore.mock import MockMeshCore
from meshcore_api.queue.manager import CommandQueueManager
from meshcore_api.queue.models import QueueFullBehavior
from meshcore_api.subscriber.event_handler import EventHandler
from meshcore_api.webhook.handler import WebhookHandler


@pytest.fixture(scope="session")
def event_loop_policy():
    """Set event loop policy for async tests."""
    return asyncio.get_event_loop_policy()


@pytest.fixture(scope="function")
def temp_db_path() -> Generator[str, None, None]:
    """Create a temporary database file."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture(scope="function")
def test_config(temp_db_path: str) -> Config:
    """Create a test configuration."""
    return Config(
        # Connection
        serial_port=None,
        use_mock=True,
        mock_min_interval=0.1,  # Fast events for testing
        mock_max_interval=0.2,
        mock_nodes=5,  # Fewer nodes for faster tests
        mock_scenario=None,
        mock_loop=False,
        # Database
        db_path=temp_db_path,
        retention_days=30,
        cleanup_interval_hours=24,
        # API
        api_host="127.0.0.1",
        api_port=8000,
        api_bearer_token=None,  # No auth by default
        # Logging
        log_level="WARNING",  # Quiet logs in tests
        log_format="text",
        # Webhooks
        webhook_message_direct=None,
        webhook_message_channel=None,
        webhook_advertisement=None,
        webhook_timeout=5,
        webhook_retry_count=3,
        webhook_message_direct_jsonpath="$",
        webhook_message_channel_jsonpath="$",
        webhook_advertisement_jsonpath="$",
        # Queue
        queue_max_size=100,
        queue_full_behavior=QueueFullBehavior.REJECT,
        # Rate limiting (disabled for fast tests)
        rate_limit_enabled=False,
        rate_limit_per_second=10.0,
        rate_limit_burst=10,
        # Debouncing (disabled for predictable tests)
        debounce_enabled=False,
        debounce_window_seconds=1.0,
        debounce_cache_max_size=100,
        debounce_commands="send_message,send_channel_message,send_advert",
        # Metrics
        metrics_enabled=False,
    )


@pytest.fixture(scope="function")
def test_config_with_auth(test_config: Config) -> Config:
    """Create a test configuration with bearer authentication."""
    test_config.api_bearer_token = "test-token-12345"
    return test_config


@pytest.fixture(scope="function")
def db_engine(test_config: Config) -> Generator[DatabaseEngine, None, None]:
    """Create a database engine for testing."""
    engine = DatabaseEngine(test_config.db_path)
    engine.initialize()
    yield engine
    engine.close()


@pytest.fixture(scope="function")
def db_session(db_engine: DatabaseEngine) -> Generator[Session, None, None]:
    """Create a database session for testing."""
    with db_engine.get_session() as session:
        yield session


@pytest_asyncio.fixture
async def mock_meshcore() -> AsyncGenerator[MockMeshCore, None]:
    """Create a MockMeshCore instance for testing."""
    mock = MockMeshCore(
        num_nodes=5,
        min_interval=0.1,
        max_interval=0.2,
        scenario_name=None,
        loop_scenario=False,
    )
    await mock.connect()
    yield mock
    await mock.disconnect()


@pytest_asyncio.fixture
async def queue_manager(
    mock_meshcore: MockMeshCore,
    test_config: Config,
) -> AsyncGenerator[CommandQueueManager, None]:
    """Create a CommandQueueManager for testing."""
    manager = CommandQueueManager(
        meshcore=mock_meshcore,
        max_queue_size=test_config.queue_max_size,
        queue_full_behavior=test_config.queue_full_behavior,
        rate_limit_per_second=test_config.rate_limit_per_second,
        rate_limit_burst=test_config.rate_limit_burst,
        rate_limit_enabled=test_config.rate_limit_enabled,
        debounce_window_seconds=test_config.debounce_window_seconds,
        debounce_cache_max_size=test_config.debounce_cache_max_size,
        debounce_enabled=test_config.debounce_enabled,
        debounce_commands=set(test_config.debounce_commands.split(",")),
    )
    await manager.start()
    yield manager
    await manager.stop()


@pytest.fixture(scope="function")
def mock_webhook_handler() -> WebhookHandler:
    """Create a mock webhook handler for testing."""
    config = Config(
        webhook_message_direct="http://localhost:9999/direct",
        webhook_message_channel="http://localhost:9999/channel",
        webhook_advertisement="http://localhost:9999/advert",
        webhook_timeout=5,
        webhook_retry_count=1,  # Fewer retries for faster tests
    )
    return WebhookHandler(config)


@pytest_asyncio.fixture
async def event_handler(
    db_engine: DatabaseEngine,
    mock_webhook_handler: WebhookHandler,
) -> AsyncGenerator[EventHandler, None]:
    """Create an EventHandler for testing."""
    handler = EventHandler(
        db_engine=db_engine,
        webhook_handler=mock_webhook_handler,
    )
    yield handler


@pytest.fixture(scope="function")
def test_app() -> TestClient:
    """Create a simple FastAPI test client without dependencies."""
    app = create_app()
    return TestClient(app)


@pytest.fixture(scope="function")
def test_app_with_auth() -> TestClient:
    """Create a simple FastAPI test client with authentication."""
    app = create_app(bearer_token="test-token-12345")
    return TestClient(app)


@pytest.fixture(scope="session")
def sample_public_keys() -> list[str]:
    """Generate sample public keys for testing."""
    return [
        "a" * 64,  # aaaa...aaaa
        "b" * 64,  # bbbb...bbbb
        "c" * 64,  # cccc...cccc
        "abc123" + "d" * 58,  # Starts with abc123
        "xyz789" + "e" * 58,  # Starts with xyz789
    ]


@pytest.fixture(scope="session")
def sample_events() -> dict[str, dict]:
    """Generate sample MeshCore events for testing."""
    timestamp = datetime.now(timezone.utc).isoformat()

    return {
        "advertisement": {
            "type": "ADVERTISEMENT",
            "timestamp": timestamp,
            "data": {
                "adv_type": "ADVERT_TYPE_NODE",
                "public_key": "a" * 64,
                "name": "Test Node",
                "flags": ["FLAG_REPEATER"],
                "gps": {"latitude": 37.7749, "longitude": -122.4194, "altitude": 100},
            },
        },
        "contact_message": {
            "type": "CONTACT_MSG_RECV",
            "timestamp": timestamp,
            "data": {
                "pubkey_prefix": "aaaaaaaaaaaa",
                "text": "Hello from node A",
                "text_type": "TEXT_TYPE_PLAIN",
                "SNR": 8.5,
                "sender_timestamp": timestamp,
            },
        },
        "channel_message": {
            "type": "CHANNEL_MSG_RECV",
            "timestamp": timestamp,
            "data": {
                "channel_idx": 4,
                "text": "Broadcast message",
                "text_type": "TEXT_TYPE_PLAIN",
                "SNR": 7.2,
                "sender_timestamp": timestamp,
            },
        },
        "telemetry": {
            "type": "TELEMETRY_RESPONSE",
            "timestamp": timestamp,
            "data": {
                "destination_pubkey": "b" * 64,
                "lpp_data": "0167FFE70368210A",
                "parsed_data": {
                    "temperature_0": -2.5,
                    "barometric_pressure_1": 1025.3,
                },
            },
        },
        "trace_path": {
            "type": "TRACE_DATA",
            "timestamp": timestamp,
            "data": {
                "initiator_tag": "aa",
                "path_len": 3,
                "path_hashes": ["aa", "bb", "cc"],
                "snr_values": [8.5, 7.2, 6.1],
            },
        },
        "path_updated": {
            "type": "PATH_UPDATED",
            "timestamp": timestamp,
            "data": {
                "destination_hash": "aa",
                "next_hop_hash": "bb",
            },
        },
        "send_confirmed": {
            "type": "SEND_CONFIRMED",
            "timestamp": timestamp,
            "data": {
                "destination_hash": "aa",
                "success": True,
            },
        },
        "battery": {
            "type": "BATTERY",
            "timestamp": timestamp,
            "data": {
                "voltage": 4.2,
                "percentage": 85,
            },
        },
        "status_response": {
            "type": "STATUS_RESPONSE",
            "timestamp": timestamp,
            "data": {
                "destination_pubkey": "c" * 64,
                "is_online": True,
                "last_seen": timestamp,
            },
        },
    }


@pytest.fixture(scope="session")
def sample_tags() -> dict[str, dict]:
    """Generate sample node tags for testing."""
    return {
        "a"
        * 64: {
            "friendly_name": {"value_type": "string", "value": "Gateway Node"},
            "location": {
                "value_type": "coordinate",
                "value": {"latitude": 37.7749, "longitude": -122.4194},
            },
            "is_gateway": {"value_type": "boolean", "value": True},
            "battery_count": {"value_type": "number", "value": 4},
        },
        "b"
        * 64: {
            "friendly_name": {"value_type": "string", "value": "Repeater Node"},
            "is_repeater": {"value_type": "boolean", "value": True},
        },
    }


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Return the fixtures directory path."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="function")
def mock_httpx_client() -> AsyncMock:
    """Create a mock httpx.AsyncClient for testing webhooks."""
    mock_client = AsyncMock()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = "OK"
    mock_client.post.return_value = mock_response
    return mock_client
