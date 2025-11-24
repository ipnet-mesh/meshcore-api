"""Real MeshCore implementation using meshcore_py library."""

import logging
from typing import Callable, List, Optional
from meshcore import MeshCore as MeshCorePy
from meshcore import EventType
from .interface import MeshCoreInterface, Event, Contact

logger = logging.getLogger(__name__)


class RealMeshCore(MeshCoreInterface):
    """Real MeshCore implementation wrapping meshcore_py library."""

    def __init__(self, serial_port: str, baud_rate: int = 115200):
        """
        Initialize real MeshCore connection.

        Args:
            serial_port: Serial port device path (e.g., /dev/ttyUSB0)
            baud_rate: Serial baud rate (default 115200)
        """
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.meshcore: Optional[MeshCorePy] = None
        self._event_handlers: List[Callable] = []

    async def connect(self) -> bool:
        """Connect to MeshCore device via serial."""
        try:
            logger.info(f"Connecting to MeshCore on {self.serial_port} at {self.baud_rate} baud")
            self.meshcore = await MeshCorePy.create_serial(
                self.serial_port,
                self.baud_rate,
                debug=False
            )

            # Subscribe to all event types
            logger.info(f"Subscribing to {len(list(EventType))} event types")
            for event_type in EventType:
                logger.debug(f"Subscribing to {event_type.name}")
                self.meshcore.subscribe(event_type, self._handle_meshcore_event)

            # Start auto message fetching if available
            if hasattr(self.meshcore, 'start_auto_message_fetching'):
                logger.info("Starting auto message fetching")
                await self.meshcore.start_auto_message_fetching()

            logger.info("Connected to MeshCore device")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to MeshCore: {e}", exc_info=True)
            return False

    async def disconnect(self) -> None:
        """Disconnect from MeshCore device."""
        if self.meshcore:
            try:
                await self.meshcore.disconnect()
                logger.info("Disconnected from MeshCore device")
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")
            finally:
                self.meshcore = None

    async def is_connected(self) -> bool:
        """Check if connected to MeshCore device."""
        if not self.meshcore:
            return False
        try:
            return self.meshcore.is_connected
        except Exception:
            return False

    async def subscribe_to_events(self, handler: Callable[[Event], None]) -> None:
        """Subscribe to all MeshCore events."""
        self._event_handlers.append(handler)
        logger.info(f"Added event handler: {handler.__name__} (total handlers: {len(self._event_handlers)})")

    async def _handle_meshcore_event(self, event) -> None:
        """
        Internal handler that converts meshcore_py events to our Event format.

        Args:
            event: meshcore_py Event object
        """
        try:
            logger.debug(f"Received MeshCore event: {event}")

            # Convert meshcore_py event to our Event format
            event_type = event.type.name if hasattr(event.type, 'name') else str(event.type)
            event_payload = event.payload if hasattr(event, 'payload') else {}

            logger.info(f"Processing event: {event_type}")

            our_event = Event(
                type=event_type,
                payload=event_payload
            )

            # Dispatch to all registered handlers
            logger.debug(f"Dispatching to {len(self._event_handlers)} handlers")
            for handler in self._event_handlers:
                try:
                    await handler(our_event)
                except Exception as e:
                    logger.error(f"Error in event handler {handler.__name__}: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Error processing MeshCore event: {e}", exc_info=True)

    async def send_message(self, destination: str, text: str, text_type: str = "plain") -> Event:
        """Send a direct message to a node."""
        if not self.meshcore:
            raise RuntimeError("Not connected to MeshCore")

        try:
            result = await self.meshcore.send_msg(destination, text)
            return Event(
                type=result.type.name if hasattr(result.type, 'name') else str(result.type),
                payload=result.payload if hasattr(result, 'payload') else {}
            )
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return Event(type="ERROR", payload={"error": str(e)})

    async def send_channel_message(self, text: str, flood: bool = True) -> Event:
        """Send a channel broadcast message."""
        if not self.meshcore:
            raise RuntimeError("Not connected to MeshCore")

        try:
            # Note: meshcore_py may have a different method name for channel messages
            # This is a placeholder - adjust based on actual API
            result = await self.meshcore.send_channel_msg(text, flood=flood)
            return Event(
                type=result.type.name if hasattr(result.type, 'name') else str(result.type),
                payload=result.payload if hasattr(result, 'payload') else {}
            )
        except Exception as e:
            logger.error(f"Failed to send channel message: {e}")
            return Event(type="ERROR", payload={"error": str(e)})

    async def send_advert(self, flood: bool = True) -> Event:
        """Send self-advertisement."""
        if not self.meshcore:
            raise RuntimeError("Not connected to MeshCore")

        try:
            result = await self.meshcore.send_advert(flood=flood)
            return Event(
                type=result.type.name if hasattr(result.type, 'name') else str(result.type),
                payload=result.payload if hasattr(result, 'payload') else {}
            )
        except Exception as e:
            logger.error(f"Failed to send advertisement: {e}")
            return Event(type="ERROR", payload={"error": str(e)})

    async def send_trace_path(self, destination: str) -> Event:
        """Initiate trace path to destination."""
        if not self.meshcore:
            raise RuntimeError("Not connected to MeshCore")

        try:
            result = await self.meshcore.send_trace_path(destination)
            return Event(
                type=result.type.name if hasattr(result.type, 'name') else str(result.type),
                payload=result.payload if hasattr(result, 'payload') else {}
            )
        except Exception as e:
            logger.error(f"Failed to send trace path: {e}")
            return Event(type="ERROR", payload={"error": str(e)})

    async def ping(self, destination: str) -> Event:
        """Ping a node (typically via telemetry request or status request)."""
        if not self.meshcore:
            raise RuntimeError("Not connected to MeshCore")

        try:
            # MeshCore doesn't have a dedicated ping, so use status request
            result = await self.meshcore.send_status_req(destination)
            return Event(
                type=result.type.name if hasattr(result.type, 'name') else str(result.type),
                payload=result.payload if hasattr(result, 'payload') else {}
            )
        except Exception as e:
            logger.error(f"Failed to ping node: {e}")
            return Event(type="ERROR", payload={"error": str(e)})

    async def send_telemetry_request(self, destination: str) -> Event:
        """Request telemetry from a node."""
        if not self.meshcore:
            raise RuntimeError("Not connected to MeshCore")

        try:
            result = await self.meshcore.send_telemetry_req(destination)
            return Event(
                type=result.type.name if hasattr(result.type, 'name') else str(result.type),
                payload=result.payload if hasattr(result, 'payload') else {}
            )
        except Exception as e:
            logger.error(f"Failed to send telemetry request: {e}")
            return Event(type="ERROR", payload={"error": str(e)})

    async def get_device_info(self) -> Event:
        """Get companion device information."""
        if not self.meshcore:
            raise RuntimeError("Not connected to MeshCore")

        try:
            result = await self.meshcore.send_device_query()
            return Event(
                type=result.type.name if hasattr(result.type, 'name') else str(result.type),
                payload=result.payload if hasattr(result, 'payload') else {}
            )
        except Exception as e:
            logger.error(f"Failed to get device info: {e}")
            return Event(type="ERROR", payload={"error": str(e)})

    async def get_battery(self) -> Event:
        """Get battery status."""
        if not self.meshcore:
            raise RuntimeError("Not connected to MeshCore")

        try:
            result = await self.meshcore.get_bat()
            return Event(
                type=result.type.name if hasattr(result.type, 'name') else str(result.type),
                payload=result.payload if hasattr(result, 'payload') else {}
            )
        except Exception as e:
            logger.error(f"Failed to get battery status: {e}")
            return Event(type="ERROR", payload={"error": str(e)})

    async def get_contacts(self) -> List[Contact]:
        """Get list of contacts."""
        if not self.meshcore:
            raise RuntimeError("Not connected to MeshCore")

        try:
            contacts_result = await self.meshcore.get_contacts()
            contacts = []

            # Convert meshcore_py contacts to our Contact format
            if hasattr(contacts_result, 'payload') and 'contacts' in contacts_result.payload:
                for mc_contact in contacts_result.payload['contacts']:
                    contact = Contact(
                        public_key=mc_contact.get('public_key', ''),
                        name=mc_contact.get('name'),
                        node_type=mc_contact.get('node_type'),
                        latitude=mc_contact.get('latitude'),
                        longitude=mc_contact.get('longitude')
                    )
                    contacts.append(contact)

            return contacts

        except Exception as e:
            logger.error(f"Failed to get contacts: {e}")
            return []

    async def get_statistics(self, stat_type: str = "core") -> Event:
        """Get device statistics."""
        if not self.meshcore:
            raise RuntimeError("Not connected to MeshCore")

        try:
            result = await self.meshcore.get_stats(stat_type)
            return Event(
                type=result.type.name if hasattr(result.type, 'name') else str(result.type),
                payload=result.payload if hasattr(result, 'payload') else {}
            )
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return Event(type="ERROR", payload={"error": str(e)})
