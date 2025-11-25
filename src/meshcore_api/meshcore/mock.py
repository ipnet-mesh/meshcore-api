"""Mock MeshCore implementation for testing without hardware."""

import asyncio
import logging
import random
import time
from datetime import datetime
from typing import Callable, List, Optional
from .interface import MeshCoreInterface, Event, Contact
from .scenarios import SCENARIOS, process_dynamic_values

logger = logging.getLogger(__name__)


class MockMeshCore(MeshCoreInterface):
    """Mock MeshCore implementation for development and testing."""

    def __init__(
        self,
        scenario_name: Optional[str] = None,
        loop_scenario: bool = False,
        num_nodes: int = 10,
        min_interval: float = 1.0,
        max_interval: float = 10.0,
        center_lat: float = 45.5231,
        center_lon: float = -122.6765,
        gps_radius_km: float = 10.0,
    ):
        """
        Initialize mock MeshCore.

        Args:
            scenario_name: Name of scenario to play back (None for random)
            loop_scenario: Whether to loop scenario indefinitely
            num_nodes: Number of simulated nodes for random mode
            min_interval: Minimum interval between random events (seconds)
            max_interval: Maximum interval between random events (seconds)
            center_lat: Center latitude for simulated nodes
            center_lon: Center longitude for simulated nodes
            gps_radius_km: Radius in km for random GPS coordinates
        """
        self.scenario_name = scenario_name
        self.loop_scenario = loop_scenario
        self.num_nodes = num_nodes
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.center_lat = center_lat
        self.center_lon = center_lon
        self.gps_radius_km = gps_radius_km

        self._connected = False
        self._event_handlers: List[Callable] = []
        self._background_task: Optional[asyncio.Task] = None
        self._simulated_nodes: List[dict] = []
        self._message_counter = 0

    async def connect(self) -> bool:
        """Connect to mock MeshCore."""
        logger.info("Connecting to Mock MeshCore")
        self._connected = True

        # Generate simulated nodes
        self._generate_simulated_nodes()

        # Start background event generation
        if self.scenario_name:
            self._background_task = asyncio.create_task(self._playback_scenario())
        else:
            self._background_task = asyncio.create_task(self._generate_random_events())

        logger.info(f"Mock MeshCore connected with {len(self._simulated_nodes)} simulated nodes")
        return True

    async def disconnect(self) -> None:
        """Disconnect from mock MeshCore."""
        logger.info("Disconnecting from Mock MeshCore")
        self._connected = False

        if self._background_task:
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass

    async def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected

    async def subscribe_to_events(self, handler: Callable[[Event], None]) -> None:
        """Subscribe to events."""
        self._event_handlers.append(handler)
        logger.debug(f"Added event handler: {handler.__name__}")

    async def sync_clock(self) -> Event:
        """Pretend to sync clock for mock implementation."""
        now = datetime.utcnow()
        timestamp = int(now.timestamp())
        logger.info(f"Mock: Syncing clock to {now.isoformat()}Z")
        return Event(
            type="CLOCK_SYNCED",
            payload={"timestamp": timestamp}
        )

    def _resolve_destination(self, destination: str) -> str:
        """
        Resolve a destination prefix to a full public key.

        Args:
            destination: Public key or prefix (minimum 2 characters)

        Returns:
            Full public key

        Raises:
            ValueError: If prefix is too short, no contact found, or multiple matches
        """
        if not destination:
            raise ValueError("Destination cannot be empty")

        # If destination looks like a full key (64 hex chars), return as-is
        if len(destination) == 64 and all(c in '0123456789abcdefABCDEF' for c in destination):
            return destination.lower()

        # Require at least 2 characters for prefix matching
        if len(destination) < 2:
            raise ValueError("Destination prefix must be at least 2 characters")

        # Find matching nodes by prefix
        destination_lower = destination.lower()
        matching_nodes = [
            node for node in self._simulated_nodes
            if node["public_key"].lower().startswith(destination_lower)
        ]

        if not matching_nodes:
            raise ValueError(f"No contact found matching prefix '{destination}'")

        if len(matching_nodes) > 1:
            logger.warning(f"Multiple contacts match prefix '{destination}', using first match")

        full_key = matching_nodes[0]["public_key"]
        logger.debug(f"Resolved prefix '{destination}' to full key '{full_key[:8]}...'")
        return full_key

    def _generate_simulated_nodes(self) -> None:
        """Generate simulated node data."""
        node_names = [
            "Alice", "Bob", "Charlie", "Diana", "Eve", "Frank",
            "Grace", "Henry", "Ivy", "Jack", "Kate", "Leo",
            "Repeater-01", "Repeater-02", "Gateway-01", "Sensor-01",
            "Sensor-02", "Mobile-01", "Mobile-02", "Base-Station"
        ]

        node_types = ["chat", "repeater", "room", "none"]

        for i in range(self.num_nodes):
            # Generate random public key
            public_key = "".join([f"{random.randint(0, 255):02x}" for _ in range(32)])

            # Random GPS within radius
            lat_offset = random.uniform(-1, 1) * (self.gps_radius_km / 111.0)
            lon_offset = random.uniform(-1, 1) * (self.gps_radius_km / 111.0)

            node = {
                "public_key": public_key,
                "name": node_names[i % len(node_names)] if i < len(node_names) else f"Node-{i}",
                "node_type": random.choice(node_types),
                "latitude": self.center_lat + lat_offset,
                "longitude": self.center_lon + lon_offset,
            }
            self._simulated_nodes.append(node)

    async def _dispatch_event(self, event: Event) -> None:
        """Dispatch event to all handlers."""
        for handler in self._event_handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Error in event handler {handler.__name__}: {e}")

    async def _generate_random_events(self) -> None:
        """Background task generating random events."""
        logger.info("Starting random event generation")

        while self._connected:
            try:
                # Select random event type
                event_type = self._select_random_event_type()

                # Generate event
                event = await self._create_random_event(event_type)

                # Dispatch event
                await self._dispatch_event(event)

                # Wait random interval
                delay = random.uniform(self.min_interval, self.max_interval)
                await asyncio.sleep(delay)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error generating random event: {e}")
                await asyncio.sleep(1.0)

    def _select_random_event_type(self) -> str:
        """Select random event type with weighted probabilities."""
        event_types = [
            ("ADVERTISEMENT", 30),
            ("CONTACT_MSG_RECV", 25),
            ("CHANNEL_MSG_RECV", 15),
            ("PATH_UPDATED", 10),
            ("SEND_CONFIRMED", 8),
            ("TELEMETRY_RESPONSE", 5),
            ("TRACE_DATA", 3),
            ("BATTERY", 2),
            ("STATUS_RESPONSE", 2),
        ]

        total_weight = sum(weight for _, weight in event_types)
        rand = random.uniform(0, total_weight)

        cumulative = 0
        for event_type, weight in event_types:
            cumulative += weight
            if rand <= cumulative:
                return event_type

        return "ADVERTISEMENT"

    async def _create_random_event(self, event_type: str) -> Event:
        """Create random event of specified type."""
        node = random.choice(self._simulated_nodes)

        if event_type == "ADVERTISEMENT":
            return Event(
                type="ADVERTISEMENT",
                payload={
                    "public_key": node["public_key"],
                    "name": node["name"],
                    "adv_type": node["node_type"],
                    "latitude": node["latitude"],
                    "longitude": node["longitude"],
                    "flags": random.randint(0, 255),
                }
            )

        elif event_type == "CONTACT_MSG_RECV":
            from_node = node
            messages = [
                "Hello!", "How are you?", "Testing 123", "Roger that",
                "Message received", "All good here", "Check",
                "Standing by", "Copy that", "Acknowledged"
            ]
            txt_type = random.choice([0, 0, 0, 2])  # mostly plain, sometimes signed
            signature = "".join(random.choices("0123456789abcdef", k=8)) if txt_type == 2 else None
            return Event(
                type="CONTACT_MSG_RECV",
                payload={
                    "pubkey_prefix": from_node["public_key"][:12],
                    "path_len": random.randint(0, 10),
                    "txt_type": txt_type,
                    "signature": signature,
                    "text": random.choice(messages),
                    "SNR": random.uniform(-5, 30),
                    "sender_timestamp": int(datetime.utcnow().timestamp()),
                }
            )

        elif event_type == "CHANNEL_MSG_RECV":
            messages = [
                "Hello everyone!", "Anyone online?", "Network test",
                "All stations check in", "Repeater operational",
                "Good morning", "Weather update", "Checking coverage"
            ]
            return Event(
                type="CHANNEL_MSG_RECV",
                payload={
                    "channel_idx": random.randint(0, 5),
                    "path_len": random.randint(0, 10),
                    "txt_type": 0,
                    "text": random.choice(messages),
                    "SNR": random.uniform(-5, 30),
                    "sender_timestamp": int(datetime.utcnow().timestamp()),
                }
            )

        elif event_type == "PATH_UPDATED":
            hop_count = random.randint(1, 5)
            return Event(
                type="PATH_UPDATED",
                payload={
                    "node_public_key": node["public_key"],
                    "hop_count": hop_count,
                }
            )

        elif event_type == "SEND_CONFIRMED":
            return Event(
                type="SEND_CONFIRMED",
                payload={
                    "destination_public_key": node["public_key"],
                    "round_trip_ms": random.randint(500, 10000),
                }
            )

        elif event_type == "TELEMETRY_RESPONSE":
            return Event(
                type="TELEMETRY_RESPONSE",
                payload={
                    "node_public_key": node["public_key"][:12],
                    "parsed_data": {
                        "temperature": random.uniform(15, 35),
                        "humidity": random.randint(30, 80),
                        "battery": random.uniform(3.0, 4.2),
                    }
                }
            )

        elif event_type == "TRACE_DATA":
            hop_count = random.randint(1, 5)
            path_hashes = [node["public_key"][:2] for _ in range(hop_count)]
            snr_values = [random.uniform(10, 50) for _ in range(hop_count)]
            return Event(
                type="TRACE_DATA",
                payload={
                    "initiator_tag": random.randint(0, 0xFFFFFFFF),
                    "path_len": hop_count,
                    "path_hashes": path_hashes,
                    "snr_values": snr_values,
                    "hop_count": hop_count,
                }
            )

        elif event_type == "BATTERY":
            return Event(
                type="BATTERY",
                payload={
                    "battery_voltage": random.uniform(3.2, 4.2),
                    "battery_percentage": random.randint(20, 100),
                }
            )

        elif event_type == "STATUS_RESPONSE":
            return Event(
                type="STATUS_RESPONSE",
                payload={
                    "node_public_key": node["public_key"],
                    "status_data": {
                        "uptime": random.randint(0, 86400),
                        "messages": random.randint(0, 1000),
                    }
                }
            )

        return Event(type="UNKNOWN", payload={})

    async def _playback_scenario(self) -> None:
        """Play back predefined scenario."""
        if self.scenario_name not in SCENARIOS:
            logger.error(f"Unknown scenario: {self.scenario_name}")
            return

        scenario = SCENARIOS[self.scenario_name]
        logger.info(f"Playing scenario: {scenario['description']}")

        while self._connected:
            start_time = time.time()

            for event_def in scenario["events"]:
                if not self._connected:
                    break

                # Wait until event delay
                target_time = start_time + event_def["delay"]
                await asyncio.sleep(max(0, target_time - time.time()))

                # Process dynamic values
                payload = process_dynamic_values(event_def["data"])

                # Create and dispatch event
                event = Event(type=event_def["type"], payload=payload)
                await self._dispatch_event(event)

            if not self.loop_scenario:
                logger.info("Scenario playback complete")
                break

            logger.info("Looping scenario...")

    async def send_message(self, destination: str, text: str, text_type: str = "plain") -> Event:
        """Send a direct message (mock)."""
        # Resolve destination prefix to full public key
        try:
            resolved_dest = self._resolve_destination(destination)
        except ValueError as e:
            logger.error(f"Failed to resolve destination: {e}")
            return Event(type="ERROR", payload={"error": str(e)})

        self._message_counter += 1
        logger.info(f"Mock: Sending message to {resolved_dest[:8]}...: {text}")
        return Event(
            type="MSG_SENT",
            payload={
                "message_id": self._message_counter,
                "destination": resolved_dest,
                "text": text,
                "estimated_delivery_ms": random.randint(1000, 5000),
            }
        )

    async def send_channel_message(self, text: str, flood: bool = True) -> Event:
        """Send a channel message (mock)."""
        self._message_counter += 1
        logger.info(f"Mock: Sending channel message: {text}")
        return Event(
            type="MSG_SENT",
            payload={
                "message_id": self._message_counter,
                "text": text,
                "flood": flood,
            }
        )

    async def send_advert(self, flood: bool = True) -> Event:
        """Send advertisement (mock)."""
        logger.info("Mock: Sending advertisement")
        return Event(
            type="ADVERT_SENT",
            payload={"flood": flood}
        )

    async def send_trace_path(self, destination: str) -> Event:
        """Send trace path request (mock)."""
        # Resolve destination prefix to full public key
        try:
            resolved_dest = self._resolve_destination(destination)
        except ValueError as e:
            logger.error(f"Failed to resolve destination: {e}")
            return Event(type="ERROR", payload={"error": str(e)})

        tag = random.randint(0, 0xFFFFFFFF)
        logger.info(f"Mock: Sending trace path to {resolved_dest[:8]}..., tag={tag}")
        return Event(
            type="TRACE_INITIATED",
            payload={
                "destination": resolved_dest,
                "initiator_tag": tag,
            }
        )

    async def ping(self, destination: str) -> Event:
        """Ping node (mock)."""
        # Resolve destination prefix to full public key
        try:
            resolved_dest = self._resolve_destination(destination)
        except ValueError as e:
            logger.error(f"Failed to resolve destination: {e}")
            return Event(type="ERROR", payload={"error": str(e)})

        logger.info(f"Mock: Pinging {resolved_dest[:8]}...")
        return Event(
            type="PING_SENT",
            payload={"destination": resolved_dest}
        )

    async def send_telemetry_request(self, destination: str) -> Event:
        """Request telemetry (mock)."""
        # Resolve destination prefix to full public key
        try:
            resolved_dest = self._resolve_destination(destination)
        except ValueError as e:
            logger.error(f"Failed to resolve destination: {e}")
            return Event(type="ERROR", payload={"error": str(e)})

        logger.info(f"Mock: Requesting telemetry from {resolved_dest[:8]}...")
        return Event(
            type="TELEMETRY_REQUEST_SENT",
            payload={"destination": resolved_dest}
        )

    async def get_device_info(self) -> Event:
        """Get device info (mock)."""
        return Event(
            type="DEVICE_INFO",
            payload={
                "firmware_version": "1.21.0-mock",
                "capabilities": {"ble": True, "gps": True, "lora": True}
            }
        )

    async def get_battery(self) -> Event:
        """Get battery status (mock)."""
        return Event(
            type="BATTERY",
            payload={
                "battery_voltage": random.uniform(3.5, 4.2),
                "battery_percentage": random.randint(50, 100),
            }
        )

    async def get_contacts(self) -> List[Contact]:
        """Get contacts (mock)."""
        contacts = []
        for node in self._simulated_nodes:
            contact = Contact(
                public_key=node["public_key"],
                name=node["name"],
                node_type=node["node_type"],
            )
            contacts.append(contact)
        return contacts
