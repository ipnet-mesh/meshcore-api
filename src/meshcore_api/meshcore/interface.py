"""Abstract interface for MeshCore implementations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, List, Optional


@dataclass
class Event:
    """Represents a MeshCore event."""

    type: str
    payload: dict


@dataclass
class Contact:
    """Represents a MeshCore contact."""

    public_key: str
    name: Optional[str] = None
    node_type: Optional[str] = None


class MeshCoreInterface(ABC):
    """Abstract base class for MeshCore implementations."""

    @abstractmethod
    async def connect(self) -> bool:
        """
        Connect to MeshCore device.

        Returns:
            True if connection successful, False otherwise
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from MeshCore device."""
        pass

    @abstractmethod
    async def is_connected(self) -> bool:
        """
        Check if connected to MeshCore device.

        Returns:
            True if connected, False otherwise
        """
        pass

    @abstractmethod
    async def subscribe_to_events(self, handler: Callable[[Event], None]) -> None:
        """
        Subscribe to all MeshCore events.

        Args:
            handler: Async callback function to handle events
        """
        pass

    @abstractmethod
    async def sync_clock(self) -> Event:
        """
        Synchronize MeshCore device clock with host time.

        Returns:
            Event with sync confirmation
        """
        pass

    @abstractmethod
    async def send_message(self, destination: str, text: str, text_type: str = "plain") -> Event:
        """
        Send a direct message to a node.

        Args:
            destination: Destination public key (full or prefix)
            text: Message content
            text_type: Message type (plain/cli_data/signed_plain)

        Returns:
            Event with send confirmation
        """
        pass

    @abstractmethod
    async def send_channel_message(self, text: str, flood: bool = True) -> Event:
        """
        Send a channel broadcast message.

        Args:
            text: Message content
            flood: Whether to flood the message

        Returns:
            Event with send confirmation
        """
        pass

    @abstractmethod
    async def send_advert(self, flood: bool = True) -> Event:
        """
        Send self-advertisement.

        Args:
            flood: Whether to flood the advertisement

        Returns:
            Event with send confirmation
        """
        pass

    @abstractmethod
    async def send_trace_path(self, destination: str) -> Event:
        """
        Initiate trace path to destination.

        Args:
            destination: Destination public key

        Returns:
            Event with trace initiation confirmation
        """
        pass

    @abstractmethod
    async def ping(self, destination: str) -> Event:
        """
        Ping a node.

        Args:
            destination: Destination public key

        Returns:
            Event with ping confirmation
        """
        pass

    @abstractmethod
    async def send_telemetry_request(self, destination: str) -> Event:
        """
        Request telemetry from a node.

        Args:
            destination: Destination public key

        Returns:
            Event with request confirmation
        """
        pass

    @abstractmethod
    async def get_device_info(self) -> Event:
        """
        Get companion device information.

        Returns:
            Event with device info payload
        """
        pass

    @abstractmethod
    async def get_battery(self) -> Event:
        """
        Get battery status.

        Returns:
            Event with battery info payload
        """
        pass

    @abstractmethod
    async def get_contacts(self) -> List[Contact]:
        """
        Get list of contacts.

        Returns:
            List of Contact objects
        """
        pass
