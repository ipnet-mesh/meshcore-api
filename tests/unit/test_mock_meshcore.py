"""Unit tests for MockMeshCore implementation."""

import asyncio

import pytest

from meshcore_api.meshcore.mock import MockMeshCore


@pytest.mark.asyncio
class TestMockMeshCoreInit:
    """Test MockMeshCore initialization."""

    async def test_init_default(self):
        """Test initialization with default values."""
        mock = MockMeshCore(num_nodes=5)
        assert mock.num_nodes == 5
        assert mock.scenario_name is None
        assert mock.loop_scenario is False
        assert len(mock._simulated_nodes) == 0  # Not initialized until connect()

    async def test_init_with_scenario(self):
        """Test initialization with scenario."""
        mock = MockMeshCore(
            num_nodes=3,
            scenario_name="test_scenario",
            loop_scenario=True,
        )
        assert mock.scenario_name == "test_scenario"
        assert mock.loop_scenario is True

    async def test_init_custom_intervals(self):
        """Test initialization with custom event intervals."""
        mock = MockMeshCore(
            num_nodes=5,
            min_interval=0.5,
            max_interval=2.0,
        )
        assert mock.min_interval == 0.5
        assert mock.max_interval == 2.0

    async def test_init_custom_gps(self):
        """Test initialization with custom GPS parameters."""
        mock = MockMeshCore(
            num_nodes=3,
            center_lat=37.7749,
            center_lon=-122.4194,
            gps_radius_km=5.0,
        )
        assert mock.center_lat == 37.7749
        assert mock.center_lon == -122.4194
        assert mock.gps_radius_km == 5.0


@pytest.mark.asyncio
class TestMockMeshCoreLifecycle:
    """Test MockMeshCore lifecycle (connect/disconnect)."""

    async def test_connect_creates_nodes(self):
        """Test connect creates simulated nodes."""
        mock = MockMeshCore(num_nodes=5, min_interval=0.1)
        result = await mock.connect()

        assert result is True
        assert len(mock._simulated_nodes) == 5
        assert mock._connected is True

        await mock.disconnect()

    async def test_connect_disconnect(self):
        """Test connect and disconnect lifecycle."""
        mock = MockMeshCore(num_nodes=3, min_interval=0.1)

        # Connect
        await mock.connect()
        assert await mock.is_connected() is True
        assert mock._background_task is not None

        # Disconnect
        await mock.disconnect()
        assert await mock.is_connected() is False

    async def test_double_connect_safe(self):
        """Test calling connect twice is safe."""
        mock = MockMeshCore(num_nodes=3, min_interval=0.1)

        await mock.connect()
        first_count = len(mock._simulated_nodes)

        # Connect again - should be safe
        await mock.connect()

        # Should still have nodes
        assert len(mock._simulated_nodes) >= first_count

        await mock.disconnect()

    async def test_disconnect_without_connect(self):
        """Test calling disconnect without connect is safe."""
        mock = MockMeshCore(num_nodes=3, min_interval=0.1)
        await mock.disconnect()  # Should not raise


@pytest.mark.asyncio
class TestMockMeshCoreEventGeneration:
    """Test event generation."""

    async def test_events_generated(self):
        """Test that events are generated over time."""
        mock = MockMeshCore(num_nodes=3, min_interval=0.05, max_interval=0.1)

        events = []

        async def event_callback(event):
            events.append(event)

        await mock.subscribe_to_events(event_callback)

        await mock.connect()
        await asyncio.sleep(0.3)  # Wait for some events
        await mock.disconnect()

        # Should have generated some events
        assert len(events) > 0

        # Events should have required fields
        for event in events:
            assert hasattr(event, "type")
            assert hasattr(event, "payload")
            # Event has type and payload

    async def test_event_types_varied(self):
        """Test that different event types are generated."""
        mock = MockMeshCore(num_nodes=5, min_interval=0.02, max_interval=0.05)

        events = []

        async def event_callback(event):
            events.append(event)

        await mock.subscribe_to_events(event_callback)

        await mock.connect()
        await asyncio.sleep(0.5)  # Wait for multiple events
        await mock.disconnect()

        # Should have multiple event types
        event_types = {e.type for e in events}
        assert len(event_types) > 1  # Multiple types generated


@pytest.mark.asyncio
class TestMockMeshCoreSubscription:
    """Test event subscription."""

    async def test_subscribe_callback(self):
        """Test subscribing to events."""
        mock = MockMeshCore(num_nodes=2, min_interval=0.05, max_interval=0.1)

        events_received = []

        async def callback(event):
            events_received.append(event)

        await mock.subscribe_to_events(callback)

        await mock.connect()
        await asyncio.sleep(0.25)  # Wait for events
        await mock.disconnect()

        assert len(events_received) > 0

    async def test_multiple_subscribers(self):
        """Test multiple subscribers receive events."""
        mock = MockMeshCore(num_nodes=2, min_interval=0.05, max_interval=0.1)

        events1 = []
        events2 = []

        async def callback1(event):
            events1.append(event)

        async def callback2(event):
            events2.append(event)

        await mock.subscribe_to_events(callback1)
        await mock.subscribe_to_events(callback2)

        await mock.connect()
        await asyncio.sleep(0.25)
        await mock.disconnect()

        # Both should receive events
        assert len(events1) > 0
        assert len(events2) > 0
        # Should receive the same events
        assert len(events1) == len(events2)


@pytest.mark.asyncio
class TestMockMeshCoreNodeGeneration:
    """Test node generation."""

    async def test_node_generation_count(self):
        """Test correct number of nodes are generated."""
        mock = MockMeshCore(num_nodes=7, min_interval=0.1)
        await mock.connect()

        assert len(mock._simulated_nodes) == 7

        await mock.disconnect()

    async def test_node_unique_public_keys(self):
        """Test all nodes have unique public keys."""
        mock = MockMeshCore(num_nodes=10, min_interval=0.1)
        await mock.connect()

        public_keys = [node["public_key"] for node in mock._simulated_nodes]
        # All should be unique
        assert len(public_keys) == len(set(public_keys))

        await mock.disconnect()

    async def test_node_valid_public_keys(self):
        """Test all nodes have valid 64-character hex public keys."""
        mock = MockMeshCore(num_nodes=5, min_interval=0.1)
        await mock.connect()

        for node in mock._simulated_nodes:
            public_key = node["public_key"]
            assert len(public_key) == 64
            # Should be valid hex
            int(public_key, 16)  # Will raise if not valid hex

        await mock.disconnect()
