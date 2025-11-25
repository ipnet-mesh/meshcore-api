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
    TracePath,
    Telemetry,
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
                "TRACE_DATA": self._handle_trace_data,
                "TELEMETRY_RESPONSE": self._handle_telemetry,
                # The following events are logged but not persisted:
                "SEND_CONFIRMED": None,
                "STATUS_RESPONSE": None,
                "STATISTICS": None,
                "BATTERY": None,
                "DEVICE_INFO": None,
                "BINARY_RESPONSE": None,
                "CONTROL_DATA": None,
                "RAW_DATA": None,
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

        # Store message
        with session_scope() as session:
            message = Message(
                direction="inbound",
                message_type="contact",
                pubkey_prefix=payload.get("pubkey_prefix"),
                channel_idx=None,
                txt_type=payload.get("txt_type"),
                path_len=payload.get("path_len"),
                signature=payload.get("signature"),
                content=payload.get("text", ""),
                snr=payload.get("SNR"),
                sender_timestamp=self._sender_timestamp(payload.get("sender_timestamp")),
            )
            session.add(message)

    async def _handle_channel_message(self, event: Event) -> None:
        """Handle CHANNEL_MSG_RECV event."""
        payload = event.payload

        # Store message
        with session_scope() as session:
            message = Message(
                direction="inbound",
                message_type="channel",
                pubkey_prefix=None,
                channel_idx=payload.get("channel_idx"),
                txt_type=payload.get("txt_type"),
                path_len=payload.get("path_len"),
                signature=payload.get("signature"),
                content=payload.get("text", ""),
                snr=payload.get("SNR"),
                sender_timestamp=self._sender_timestamp(payload.get("sender_timestamp")),
            )
            session.add(message)

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

    def _sender_timestamp(self, value: Optional[int]) -> Optional[datetime]:
        """Convert meshcore sender_timestamp (epoch seconds) to datetime."""
        if value is None:
            return None
        try:
            return datetime.utcfromtimestamp(int(value))
        except Exception as e:
            try:
                # Support ISO strings (from mock/scenarios)
                ts_str = str(value)
                if ts_str.endswith("Z"):
                    ts_str = ts_str[:-1]
                return datetime.fromisoformat(ts_str)
            except Exception:
                logger.warning(f"Failed to parse sender_timestamp '{value}': {e}")
                return None
