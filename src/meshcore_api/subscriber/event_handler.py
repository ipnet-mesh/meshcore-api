"""Event handler for processing and persisting MeshCore events."""
import base64
import json
import logging
from datetime import datetime
from typing import Optional, List
from ..meshcore.interface import Event, MeshCoreInterface, Contact
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
from ..constants import NODE_TYPE_MAP, node_type_name

logger = logging.getLogger(__name__)


class EventHandler:
    """Handles MeshCore events and persists them to database."""

    def __init__(self, meshcore: Optional[MeshCoreInterface] = None):
        """Initialize event handler."""
        self.event_count = 0
        self.meshcore = meshcore
        self._contact_fetch_inflight = False

    async def handle_event(self, event: Event) -> None:
        """
        Handle incoming MeshCore event.

        Args:
            event: Event to process and persist
        """
        self.event_count += 1

        # Some events are noisy/incremental and should be largely silent here
        silent_types = {"NEXT_CONTACT"}

        try:
            if event.type not in silent_types:
                logger.debug(f"Processing event: {event.type}")

            # Log all events to events_log table
            if event.type not in silent_types:
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
                # Contact sync events (used to enrich node info)
                "NEXT_CONTACT": None,  # informational; handled on CONTACTS aggregate
                "CONTACTS": self._handle_contact_sync,
                # Error events (informational)
                "ERROR": None,
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
                    event_data=json.dumps(event.payload, default=self._json_default),
                )
                session.add(event_log)
        except Exception as e:
            logger.error(f"Failed to log event: {e}")

    @staticmethod
    def _json_default(obj):
        """JSON serializer for non-serializable types."""
        if isinstance(obj, (bytes, bytearray, memoryview)):
            return base64.b64encode(bytes(obj)).decode("ascii")
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    async def _fetch_contacts(self, fetch: bool = True) -> List[Contact]:
        """
        Fetch contacts from MeshCore.

        Args:
            fetch: If False, read cached contacts without issuing a fetch command.
        """
        if not self.meshcore:
            return []
        try:
            if self._contact_fetch_inflight:
                cache = getattr(self.meshcore, "contacts", {}) if hasattr(self.meshcore, "contacts") else {}
                return self._contacts_from_cache(cache)

            if hasattr(self.meshcore, "contacts"):
                cache = getattr(self.meshcore, "contacts", {}) or {}
                if cache and (not fetch or not self._contact_fetch_inflight):
                    return self._contacts_from_cache(cache)

            self._contact_fetch_inflight = True
            try:
                contacts = await self.meshcore.get_contacts()
                return contacts or []
            finally:
                self._contact_fetch_inflight = False
        except Exception as e:
            logger.warning(f"Failed to fetch contacts from MeshCore: {e}")
            return []

    async def _handle_contact_sync(self, event: Event) -> None:
        """
        Handle NEXT_CONTACT and CONTACTS events.

        We rely on meshcore.ensure_contacts to populate meshcore.contacts.
        Here we upsert what the interface returns to refresh nodes.
        """
        contacts = await self._fetch_contacts(fetch=False)
        for contact in contacts:
            contact_key = getattr(contact, "public_key", None)
            if not contact_key:
                continue
            normalized = normalize_public_key(contact_key)
            await self._upsert_node(
                normalized,
                name=getattr(contact, "name", None),
                node_type=node_type_name(getattr(contact, "node_type", None)),
            )

    async def _get_contact_for_key(self, normalized_key: str) -> Optional[Contact]:
        """Retrieve contact info for a given key and upsert all contacts."""
        contacts = await self._fetch_contacts(fetch=not self._contact_fetch_inflight)
        match: Optional[Contact] = None

        for contact in contacts:
            contact_key = getattr(contact, "public_key", None)
            if not contact_key:
                continue
            contact_norm = normalize_public_key(contact_key)
            # Upsert every contact to keep node table in sync
            await self._upsert_node(
                contact_norm,
                name=getattr(contact, "name", None),
                node_type=node_type_name(getattr(contact, "node_type", None)),
            )
            if contact_norm == normalized_key:
                match = contact

        return match

    @staticmethod
    def _contacts_from_cache(cache: dict) -> List[Contact]:
        """Convert meshcore contact cache dict to Contact list."""
        contacts: List[Contact] = []
        for mc_contact in cache.values():
            pub_key = mc_contact.get("public_key", "")
            contact = Contact(
                public_key=pub_key,
                name=mc_contact.get("adv_name") or mc_contact.get("name"),
                node_type=mc_contact.get("node_type") or mc_contact.get("type") or mc_contact.get("adv_type"),
            )
            contacts.append(contact)
        return contacts

    def _should_update_name(self, current: Optional[str], new: Optional[str], normalized_key: str) -> bool:
        """Decide if the stored node name should be replaced."""
        if not new:
            return False
        if not current:
            return True
        # Don't update if the names are the same (case-insensitive)
        if current.lower() == new.lower():
            return False
        # Check if current name is a placeholder (first 8 chars of key)
        placeholder = normalized_key[:8]
        current_is_placeholder = current.lower() == placeholder.lower()
        new_is_placeholder = new.lower() == placeholder.lower()

        # Allow update if:
        # 1. Current is a placeholder and new is not (upgrade to real name)
        # 2. Current is not a placeholder and new is not (name change)
        # Don't allow: Current is not a placeholder and new IS a placeholder (downgrade)
        if current_is_placeholder:
            return True  # Always upgrade from placeholder
        if new_is_placeholder:
            return False  # Never downgrade to placeholder
        return True  # Both are real names, allow the update

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
            if "node_type" in kwargs:
                kwargs["node_type"] = node_type_name(kwargs.get("node_type"))

            with session_scope() as session:
                # Try to find existing node
                node = session.query(Node).filter_by(public_key=normalized_key).first()

                if node:
                    # Update existing node
                    for key, value in kwargs.items():
                        if value is not None:
                            if key == "name" and not self._should_update_name(getattr(node, key), value, normalized_key):
                                logger.debug(f"Skipping name update for {normalized_key[:8]}...: '{getattr(node, key)}' -> '{value}'")
                                continue
                            old_value = getattr(node, key, None)
                            if old_value != value:
                                logger.info(f"Updating {key} for {normalized_key[:8]}...: {old_value} -> {value}")
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

        normalized_key = normalize_public_key(public_key)
        adv_type = payload.get("adv_type") or payload.get("type")

        # Extract data from advertisement payload
        adv_name = (
            payload.get("name")
            or payload.get("node_name")
            or payload.get("device_name")
            or payload.get("alias")
            or payload.get("adv_name")
        )

        # Try to enrich with contact info for name and type
        contact = None
        if (not adv_name or not adv_type) and self.meshcore:
            contact = await self._get_contact_for_key(normalized_key)

        # Use advertisement payload first, then contact data as fallback
        name = adv_name or (contact.name if contact else None) or normalized_key[:8]
        node_type = adv_type or (contact.node_type if contact else None)

        # Upsert node (no GPS)
        await self._upsert_node(
            public_key,
            node_type=node_type,
            name=name,
        )

        # Store advertisement
        with session_scope() as session:
            advert = Advertisement(
                public_key=normalized_key,
                adv_type=adv_type,
                name=name,
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

        initiator_tag = payload.get("initiator_tag") or payload.get("tag")
        if initiator_tag is None:
            logger.warning(f"Skipping TRACE_DATA with missing initiator_tag: {payload}")
            return

        destination_key = payload.get("destination_public_key")
        normalized_destination = normalize_public_key(destination_key) if destination_key else None

        path_hashes = payload.get("path_hashes")
        if path_hashes is None and "path" in payload:
            path_hashes = [hop.get("hash") for hop in payload.get("path", []) if hop.get("hash") is not None]

        snr_values = payload.get("snr_values")
        if snr_values is None and "path" in payload:
            snr_values = [hop.get("snr") for hop in payload.get("path", []) if hop.get("snr") is not None]

        hop_count = payload.get("hop_count") or (len(path_hashes) if path_hashes is not None else None)

        with session_scope() as session:
            trace = TracePath(
                initiator_tag=initiator_tag,
                destination_public_key=normalized_destination,
                path_hashes=json.dumps(path_hashes or []),
                snr_values=json.dumps(snr_values or []),
                hop_count=hop_count,
            )
            session.add(trace)

    async def _handle_telemetry(self, event: Event) -> None:
        """Handle TELEMETRY_RESPONSE event."""
        payload = event.payload
        node_key = payload.get("node_public_key")

        if not node_key:
            return

        normalized_key = normalize_public_key(node_key)

        with session_scope() as session:
            telemetry = Telemetry(
                node_public_key=normalized_key,
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
