"""Event handler for processing and persisting MeshCore events."""

import json
import logging
from datetime import datetime
from typing import Optional
from ..meshcore.interface import Event
from ..database.models import (
    Node,
    Message,
    Advertisement,
    Path,
    TracePath,
    Telemetry,
    Acknowledgment,
    StatusResponse,
    Statistics,
    BinaryResponse,
    ControlData,
    RawData,
    DeviceInfo,
    EventLog,
)
from ..database.engine import session_scope
from ..utils.address import normalize_public_key, extract_prefix

logger = logging.getLogger(__name__)


class EventHandler:
    """Handles MeshCore events and persists them to database."""

    def __init__(self):
        """Initialize event handler."""
        self.event_count = 0

    async def handle_event(self, event: Event) -> None:
        """
        Handle incoming MeshCore event.

        Args:
            event: Event to process and persist
        """
        self.event_count += 1

        try:
            logger.debug(f"Processing event: {event.type}")

            # Log all events to events_log table
            await self._log_event(event)

            # Handle specific event types
            handler_map = {
                "ADVERTISEMENT": self._handle_advertisement,
                "NEW_ADVERT": self._handle_advertisement,
                "CONTACT_MSG_RECV": self._handle_contact_message,
                "CHANNEL_MSG_RECV": self._handle_channel_message,
                "PATH_UPDATED": self._handle_path_updated,
                "TRACE_DATA": self._handle_trace_data,
                "TELEMETRY_RESPONSE": self._handle_telemetry,
                "SEND_CONFIRMED": self._handle_acknowledgment,
                "STATUS_RESPONSE": self._handle_status_response,
                "STATISTICS": self._handle_statistics,
                "BATTERY": self._handle_battery,
                "DEVICE_INFO": self._handle_device_info,
                "BINARY_RESPONSE": self._handle_binary_response,
                "CONTROL_DATA": self._handle_control_data,
                "RAW_DATA": self._handle_raw_data,
                # Internal meshcore_py events (informational only)
                "MESSAGES_WAITING": None,  # Logged but not persisted separately
                "NO_MORE_MSGS": None,  # Logged but not persisted separately
                "RX_LOG_DATA": None,  # Logged but not persisted separately
            }

            handler = handler_map.get(event.type)
            if handler:
                await handler(event)
            elif handler is None and event.type in handler_map:
                # Event type is known but no specific handler (informational)
                logger.debug(f"Informational event (not persisted separately): {event.type}")
            else:
                logger.info(f"Unknown event type (logged to events_log): {event.type}")

        except Exception as e:
            logger.error(f"Error handling event {event.type}: {e}", exc_info=True)

    async def _log_event(self, event: Event) -> None:
        """Log raw event to events_log table."""
        try:
            with session_scope() as session:
                event_log = EventLog(
                    event_type=event.type,
                    event_data=json.dumps(event.payload),
                )
                session.add(event_log)
        except Exception as e:
            logger.error(f"Failed to log event: {e}")

    async def _upsert_node(self, public_key: str, **kwargs) -> Optional[Node]:
        """
        Create or update node record.

        Args:
            public_key: Node public key
            **kwargs: Additional node attributes

        Returns:
            Node object or None on error
        """
        try:
            normalized_key = normalize_public_key(public_key)

            with session_scope() as session:
                # Try to find existing node
                node = session.query(Node).filter_by(public_key=normalized_key).first()

                if node:
                    # Update existing node
                    for key, value in kwargs.items():
                        if value is not None:
                            setattr(node, key, value)
                    node.last_seen = datetime.utcnow()
                else:
                    # Create new node
                    node = Node(
                        public_key=normalized_key,
                        public_key_prefix_2=extract_prefix(normalized_key, 2),
                        public_key_prefix_8=extract_prefix(normalized_key, 8),
                        last_seen=datetime.utcnow(),
                        **kwargs
                    )
                    session.add(node)

                session.flush()
                return node

        except Exception as e:
            logger.error(f"Failed to upsert node {public_key}: {e}")
            return None

    async def _handle_advertisement(self, event: Event) -> None:
        """Handle ADVERTISEMENT event."""
        payload = event.payload
        public_key = payload.get("public_key")

        if not public_key:
            logger.warning("Advertisement missing public_key")
            return

        # Upsert node
        await self._upsert_node(
            public_key,
            node_type=payload.get("adv_type"),
            name=payload.get("name"),
            latitude=payload.get("latitude"),
            longitude=payload.get("longitude"),
        )

        # Store advertisement
        with session_scope() as session:
            advert = Advertisement(
                public_key=normalize_public_key(public_key),
                adv_type=payload.get("adv_type"),
                name=payload.get("name"),
                latitude=payload.get("latitude"),
                longitude=payload.get("longitude"),
                flags=payload.get("flags"),
            )
            session.add(advert)

    async def _handle_contact_message(self, event: Event) -> None:
        """Handle CONTACT_MSG_RECV event."""
        payload = event.payload
        from_key = payload.get("from_public_key")
        to_key = payload.get("to_public_key")

        # Upsert sender node
        if from_key:
            await self._upsert_node(from_key)

        # Store message
        with session_scope() as session:
            message = Message(
                direction="inbound",
                message_type="contact",
                from_public_key=normalize_public_key(from_key) if from_key else None,
                to_public_key=normalize_public_key(to_key) if to_key else None,
                content=payload.get("text", ""),
                text_type=payload.get("text_type", "plain"),
                snr=payload.get("snr"),
                rssi=payload.get("rssi"),
                timestamp=self._parse_timestamp(payload.get("timestamp")),
            )
            session.add(message)

    async def _handle_channel_message(self, event: Event) -> None:
        """Handle CHANNEL_MSG_RECV event."""
        payload = event.payload
        from_key = payload.get("from_public_key")

        # Upsert sender node
        if from_key:
            await self._upsert_node(from_key)

        # Store message
        with session_scope() as session:
            message = Message(
                direction="inbound",
                message_type="channel",
                from_public_key=normalize_public_key(from_key) if from_key else None,
                to_public_key=None,
                content=payload.get("text", ""),
                text_type=payload.get("text_type", "plain"),
                snr=payload.get("snr"),
                rssi=payload.get("rssi"),
                timestamp=self._parse_timestamp(payload.get("timestamp")),
            )
            session.add(message)

    async def _handle_path_updated(self, event: Event) -> None:
        """Handle PATH_UPDATED event."""
        payload = event.payload
        node_key = payload.get("node_public_key")

        if not node_key:
            return

        # Upsert node
        await self._upsert_node(node_key)

        # Store path
        with session_scope() as session:
            path = Path(
                node_public_key=normalize_public_key(node_key),
                path_data=payload.get("path_data"),
                hop_count=payload.get("hop_count"),
            )
            session.add(path)

    async def _handle_trace_data(self, event: Event) -> None:
        """Handle TRACE_DATA event."""
        payload = event.payload

        with session_scope() as session:
            trace = TracePath(
                initiator_tag=payload.get("initiator_tag"),
                destination_public_key=payload.get("destination_public_key"),
                path_hashes=json.dumps(payload.get("path_hashes", [])),
                snr_values=json.dumps(payload.get("snr_values", [])),
                hop_count=payload.get("hop_count"),
            )
            session.add(trace)

    async def _handle_telemetry(self, event: Event) -> None:
        """Handle TELEMETRY_RESPONSE event."""
        payload = event.payload
        node_key = payload.get("node_public_key")

        if not node_key:
            return

        with session_scope() as session:
            telemetry = Telemetry(
                node_public_key=node_key,
                lpp_data=payload.get("lpp_data"),
                parsed_data=json.dumps(payload.get("parsed_data")) if payload.get("parsed_data") else None,
            )
            session.add(telemetry)

    async def _handle_acknowledgment(self, event: Event) -> None:
        """Handle SEND_CONFIRMED event."""
        payload = event.payload

        with session_scope() as session:
            ack = Acknowledgment(
                message_id=payload.get("message_id"),
                destination_public_key=payload.get("destination_public_key"),
                round_trip_ms=payload.get("round_trip_ms"),
            )
            session.add(ack)

    async def _handle_status_response(self, event: Event) -> None:
        """Handle STATUS_RESPONSE event."""
        payload = event.payload
        node_key = payload.get("node_public_key")

        if not node_key:
            return

        with session_scope() as session:
            status = StatusResponse(
                node_public_key=normalize_public_key(node_key),
                status_data=json.dumps(payload.get("status_data", {})),
            )
            session.add(status)

    async def _handle_statistics(self, event: Event) -> None:
        """Handle STATISTICS event."""
        payload = event.payload

        with session_scope() as session:
            stats = Statistics(
                stat_type=payload.get("stat_type", "core"),
                data=json.dumps(payload.get("data", {})),
            )
            session.add(stats)

    async def _handle_battery(self, event: Event) -> None:
        """Handle BATTERY event."""
        payload = event.payload

        with session_scope() as session:
            device_info = DeviceInfo(
                battery_voltage=payload.get("battery_voltage"),
                battery_percentage=payload.get("battery_percentage"),
            )
            session.add(device_info)

    async def _handle_device_info(self, event: Event) -> None:
        """Handle DEVICE_INFO event."""
        payload = event.payload

        with session_scope() as session:
            device_info = DeviceInfo(
                battery_voltage=payload.get("battery_voltage"),
                battery_percentage=payload.get("battery_percentage"),
                storage_used=payload.get("storage_used"),
                storage_total=payload.get("storage_total"),
                device_time=self._parse_timestamp(payload.get("device_time")),
                firmware_version=payload.get("firmware_version"),
                capabilities=json.dumps(payload.get("capabilities")) if payload.get("capabilities") else None,
            )
            session.add(device_info)

    async def _handle_binary_response(self, event: Event) -> None:
        """Handle BINARY_RESPONSE event."""
        payload = event.payload

        with session_scope() as session:
            binary_resp = BinaryResponse(
                tag=payload.get("tag"),
                payload=payload.get("payload", b""),
            )
            session.add(binary_resp)

    async def _handle_control_data(self, event: Event) -> None:
        """Handle CONTROL_DATA event."""
        payload = event.payload

        with session_scope() as session:
            control = ControlData(
                from_public_key=payload.get("from_public_key"),
                payload=payload.get("payload", b""),
            )
            session.add(control)

    async def _handle_raw_data(self, event: Event) -> None:
        """Handle RAW_DATA event."""
        payload = event.payload

        with session_scope() as session:
            raw = RawData(
                from_public_key=payload.get("from_public_key"),
                payload=payload.get("payload", b""),
            )
            session.add(raw)

    def _parse_timestamp(self, timestamp_str: Optional[str]) -> datetime:
        """
        Parse timestamp string to datetime.

        Args:
            timestamp_str: ISO format timestamp string

        Returns:
            datetime object (current time if parsing fails)
        """
        if not timestamp_str:
            return datetime.utcnow()

        try:
            # Remove 'Z' suffix if present
            if timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str[:-1]

            return datetime.fromisoformat(timestamp_str)
        except Exception as e:
            logger.warning(f"Failed to parse timestamp '{timestamp_str}': {e}")
            return datetime.utcnow()
