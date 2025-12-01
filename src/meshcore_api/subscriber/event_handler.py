"""Event handler for processing and persisting MeshCore events."""

import asyncio
import base64
import json
import logging
from datetime import datetime
from typing import List, Optional

from ..constants import NODE_TYPE_MAP, node_type_name
from ..database.engine import session_scope
from ..database.models import (
    Advertisement,
    EventLog,
    Message,
    Node,
    SignalStrength,
    Telemetry,
    TracePath,
)
from ..meshcore.interface import Contact, Event, MeshCoreInterface
from ..utils.address import extract_prefix, normalize_public_key

logger = logging.getLogger(__name__)


class EventHandler:
    """Handles MeshCore events and persists them to database."""

    def __init__(
        self,
        meshcore: Optional[MeshCoreInterface] = None,
        webhook_handler: Optional["WebhookHandler"] = None,
    ):
        """Initialize event handler."""
        self.event_count = 0
        self.meshcore = meshcore
        self.webhook_handler = webhook_handler
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

            # Trigger webhook (non-blocking) for supported event types
            if self.webhook_handler and event.type in [
                "CONTACT_MSG_RECV",
                "CHANNEL_MSG_RECV",
                "ADVERTISEMENT",
                "NEW_ADVERT",
            ]:
                asyncio.create_task(self._send_webhook_for_event(event))

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
                cache = (
                    getattr(self.meshcore, "contacts", {})
                    if hasattr(self.meshcore, "contacts")
                    else {}
                )
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
                node_type=mc_contact.get("node_type")
                or mc_contact.get("type")
                or mc_contact.get("adv_type"),
            )
            contacts.append(contact)
        return contacts

    def _should_update_name(
        self, current: Optional[str], new: Optional[str], normalized_key: str
    ) -> bool:
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
                            if key == "name" and not self._should_update_name(
                                getattr(node, key), value, normalized_key
                            ):
                                logger.debug(
                                    f"Skipping name update for {normalized_key[:8]}...: '{getattr(node, key)}' -> '{value}'"
                                )
                                continue
                            old_value = getattr(node, key, None)
                            if old_value != value:
                                logger.info(
                                    f"Updating {key} for {normalized_key[:8]}...: {old_value} -> {value}"
                                )
                            setattr(node, key, value)
                    node.last_seen = datetime.utcnow()
                else:
                    # Create new node
                    node = Node(
                        public_key=normalized_key,
                        public_key_prefix_2=extract_prefix(normalized_key, 2),
                        public_key_prefix_8=extract_prefix(normalized_key, 8),
                        last_seen=datetime.utcnow(),
                        **kwargs,
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

        # Normalize pubkey_prefix to lowercase for consistency
        pubkey_prefix = payload.get("pubkey_prefix")
        if pubkey_prefix:
            pubkey_prefix = pubkey_prefix.lower()

        # Store message
        with session_scope() as session:
            message = Message(
                direction="inbound",
                message_type="contact",
                pubkey_prefix=pubkey_prefix,
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

    def _resolve_prefix_to_full_key(self, session, prefix: str) -> Optional[str]:
        """
        Resolve a 2-character public key prefix to a full 64-character public key.

        Uses existing database APIs to find matching nodes. If multiple nodes match,
        returns the one with the most recent last_seen timestamp.

        Args:
            session: Database session
            prefix: 2-character public key prefix (lowercase)

        Returns:
            Full 64-character public key if found, None otherwise
        """
        if not prefix or len(prefix) < 2:
            return None

        # Find all nodes matching this prefix
        nodes = Node.find_by_prefix(session, prefix)

        if not nodes:
            logger.debug(f"No nodes found for prefix '{prefix}'")
            return None

        if len(nodes) == 1:
            return nodes[0].public_key

        # Multiple matches - use the one with the most recent last_seen
        nodes_with_last_seen = [n for n in nodes if n.last_seen is not None]
        if nodes_with_last_seen:
            most_recent = max(nodes_with_last_seen, key=lambda n: n.last_seen)
            logger.debug(
                f"Multiple nodes ({len(nodes)}) match prefix '{prefix}', "
                f"using most recent: {most_recent.public_key[:8]}..."
            )
            return most_recent.public_key

        # No nodes have last_seen set, use the first one (by creation order)
        logger.debug(
            f"Multiple nodes ({len(nodes)}) match prefix '{prefix}' with no last_seen, "
            f"using first: {nodes[0].public_key[:8]}..."
        )
        return nodes[0].public_key

    async def _handle_trace_data(self, event: Event) -> None:
        """Handle TRACE_DATA event."""
        payload = event.payload

        initiator_tag = payload.get("initiator_tag") or payload.get("tag")
        if initiator_tag is None:
            logger.warning(f"Skipping TRACE_DATA with missing initiator_tag: {payload}")
            return

        path_hashes = payload.get("path_hashes")
        if path_hashes is None and "path" in payload:
            path_hashes = [
                hop.get("hash") for hop in payload.get("path", []) if hop.get("hash") is not None
            ]

        # Normalize path hashes to lowercase for consistency
        if path_hashes:
            path_hashes = [h.lower() if h else h for h in path_hashes]

        snr_values = payload.get("snr_values")
        if snr_values is None and "path" in payload:
            snr_values = [
                hop.get("snr") for hop in payload.get("path", []) if hop.get("snr") is not None
            ]

        path_len = payload.get("path_len")
        if path_len is None and path_hashes is not None:
            path_len = len(path_hashes)

        hop_count = (
            payload.get("hop_count")
            or path_len
            or (len(path_hashes) if path_hashes is not None else None)
        )

        with session_scope() as session:
            trace = TracePath(
                initiator_tag=initiator_tag,
                path_len=path_len,
                flags=payload.get("flags"),
                auth=payload.get("auth"),
                path_hashes=json.dumps(path_hashes or []),
                snr_values=json.dumps(snr_values or []),
                hop_count=hop_count,
            )
            session.add(trace)
            session.flush()  # Get the trace ID

            # Create SignalStrength records for consecutive node pairs
            if path_hashes and snr_values and len(path_hashes) >= 2:
                self._create_signal_strength_records(session, trace.id, path_hashes, snr_values)

    def _create_signal_strength_records(
        self,
        session,
        trace_path_id: int,
        path_hashes: List[str],
        snr_values: List[float],
    ) -> None:
        """
        Create SignalStrength records for consecutive node pairs in a trace path.

        The SNR at index i represents the signal received by node path_hashes[i]
        from the previous node. For i > 0, we can create records where:
        - source = path_hashes[i-1]
        - destination = path_hashes[i]
        - snr = snr_values[i]

        Args:
            session: Database session
            trace_path_id: ID of the trace path for reference
            path_hashes: List of 2-char node prefixes in path order
            snr_values: List of SNR values corresponding to each hop
        """
        created_count = 0

        # Create records for consecutive pairs (starting from index 1)
        # snr_values[i] is the signal from path_hashes[i-1] to path_hashes[i]
        for i in range(1, min(len(path_hashes), len(snr_values))):
            source_prefix = path_hashes[i - 1]
            dest_prefix = path_hashes[i]
            snr = snr_values[i]

            if source_prefix is None or dest_prefix is None or snr is None:
                logger.debug(f"Skipping hop {i}: missing data")
                continue

            # Resolve prefixes to full public keys
            source_key = self._resolve_prefix_to_full_key(session, source_prefix)
            dest_key = self._resolve_prefix_to_full_key(session, dest_prefix)

            if source_key is None:
                logger.debug(f"Could not resolve source prefix '{source_prefix}' for hop {i}")
                continue
            if dest_key is None:
                logger.debug(f"Could not resolve dest prefix '{dest_prefix}' for hop {i}")
                continue

            # Create SignalStrength record
            signal_strength = SignalStrength(
                source_public_key=source_key,
                destination_public_key=dest_key,
                snr=float(snr),
                trace_path_id=trace_path_id,
            )
            session.add(signal_strength)
            created_count += 1

        if created_count > 0:
            logger.debug(
                f"Created {created_count} SignalStrength records for trace path {trace_path_id}"
            )

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
                parsed_data=(
                    json.dumps(payload.get("parsed_data")) if payload.get("parsed_data") else None
                ),
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
            if timestamp_str.endswith("Z"):
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

    async def _send_webhook_for_event(self, event: Event) -> None:
        """
        Send webhook for supported event types.

        Args:
            event: Event to send webhook for
        """
        try:
            # Send the event payload directly to the webhook handler
            # The webhook handler will route to the appropriate URL based on event type
            await self.webhook_handler.send_event(
                event_type=event.type,
                data=event.payload,
            )
        except Exception as e:
            # Don't let webhook errors affect event processing
            logger.warning(f"Failed to send webhook for {event.type}: {e}")
