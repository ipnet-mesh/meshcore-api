"""SQLAlchemy database models for MeshCore events."""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Boolean,
    Integer,
    String,
    Float,
    Text,
    LargeBinary,
    DateTime,
    Index,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class Node(Base):
    """Represents a MeshCore node (repeater or companion device)."""

    __tablename__ = "nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    public_key_prefix_2: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    public_key_prefix_8: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    node_type: Mapped[Optional[str]] = mapped_column(String(32))  # chat/repeater/room/none
    name: Mapped[Optional[str]] = mapped_column(String(128))
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    @classmethod
    def find_by_prefix(cls, session, prefix: str) -> List["Node"]:
        """Find all nodes matching a public key prefix."""
        prefix_lower = prefix.lower()
        prefix_len = len(prefix_lower)

        if prefix_len <= 2:
            return session.query(cls).filter(
                cls.public_key_prefix_2.like(f"{prefix_lower}%")
            ).all()
        elif prefix_len <= 8:
            return session.query(cls).filter(
                cls.public_key_prefix_8.like(f"{prefix_lower}%")
            ).all()
        else:
            return session.query(cls).filter(
                cls.public_key.like(f"{prefix_lower}%")
            ).all()


class Message(Base):
    """Represents a direct or channel message."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)  # inbound/outbound
    message_type: Mapped[str] = mapped_column(String(16), nullable=False)  # contact/channel
    text_type: Mapped[str] = mapped_column(String(32), default="plain")  # plain/cli_data/signed_plain
    from_public_key: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    to_public_key: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    snr: Mapped[Optional[float]] = mapped_column(Float)
    rssi: Mapped[Optional[float]] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    __table_args__ = (
        Index("idx_messages_timestamp", "timestamp"),
    )


class Advertisement(Base):
    """Represents a node advertisement."""

    __tablename__ = "advertisements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    adv_type: Mapped[Optional[str]] = mapped_column(String(32))  # none/chat/repeater/room
    name: Mapped[Optional[str]] = mapped_column(String(128))
    flags: Mapped[Optional[int]] = mapped_column(Integer)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)


class Path(Base):
    """Represents a routing path to a node."""

    __tablename__ = "paths"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    node_public_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    path_data: Mapped[Optional[bytes]] = mapped_column(LargeBinary)  # 64-byte outbound path
    hop_count: Mapped[Optional[int]] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class TracePath(Base):
    """Represents a trace path result with SNR data."""

    __tablename__ = "trace_paths"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    initiator_tag: Mapped[int] = mapped_column(Integer, nullable=False)
    destination_public_key: Mapped[Optional[str]] = mapped_column(String(64))
    path_hashes: Mapped[Optional[str]] = mapped_column(Text)  # JSON array of 2-char hashes
    snr_values: Mapped[Optional[str]] = mapped_column(Text)  # JSON array of SNR values
    hop_count: Mapped[Optional[int]] = mapped_column(Integer)
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)


class Telemetry(Base):
    """Represents telemetry data from a node."""

    __tablename__ = "telemetry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    node_public_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    lpp_data: Mapped[Optional[bytes]] = mapped_column(LargeBinary)  # LPP-formatted sensor data
    parsed_data: Mapped[Optional[str]] = mapped_column(Text)  # JSON parsed sensors
    received_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)


class Acknowledgment(Base):
    """Represents a message acknowledgment with timing."""

    __tablename__ = "acknowledgments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[Optional[int]] = mapped_column(Integer)  # Reference to messages table
    destination_public_key: Mapped[Optional[str]] = mapped_column(String(64))
    round_trip_ms: Mapped[Optional[int]] = mapped_column(Integer)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)


class StatusResponse(Base):
    """Represents a status response from a node."""

    __tablename__ = "status_responses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    node_public_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status_data: Mapped[str] = mapped_column(Text, nullable=False)  # JSON status payload
    received_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)


class Statistics(Base):
    """Represents device statistics (core/radio/packets)."""

    __tablename__ = "statistics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stat_type: Mapped[str] = mapped_column(String(32), nullable=False)  # core/radio/packets
    data: Mapped[str] = mapped_column(Text, nullable=False)  # JSON statistics data
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)


class BinaryResponse(Base):
    """Represents a binary response matched by tag."""

    __tablename__ = "binary_responses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tag: Mapped[int] = mapped_column(Integer, nullable=False)  # 32-bit matching tag
    payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)


class ControlData(Base):
    """Represents control packet data."""

    __tablename__ = "control_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_public_key: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)


class RawData(Base):
    """Represents raw packet data."""

    __tablename__ = "raw_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_public_key: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)


class DeviceInfo(Base):
    """Represents companion device information and status."""

    __tablename__ = "device_info"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    battery_voltage: Mapped[Optional[float]] = mapped_column(Float)
    battery_percentage: Mapped[Optional[int]] = mapped_column(Integer)
    storage_used: Mapped[Optional[int]] = mapped_column(Integer)
    storage_total: Mapped[Optional[int]] = mapped_column(Integer)
    device_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    firmware_version: Mapped[Optional[str]] = mapped_column(String(32))
    capabilities: Mapped[Optional[str]] = mapped_column(Text)  # JSON
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)


class EventLog(Base):
    """Raw event log for all MeshCore events."""

    __tablename__ = "events_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_data: Mapped[str] = mapped_column(Text, nullable=False)  # JSON full event payload
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)
