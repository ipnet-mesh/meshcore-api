"""SQLAlchemy database models for MeshCore events."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
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
            return session.query(cls).filter(cls.public_key_prefix_2.like(f"{prefix_lower}%")).all()
        elif prefix_len <= 8:
            return session.query(cls).filter(cls.public_key_prefix_8.like(f"{prefix_lower}%")).all()
        else:
            return session.query(cls).filter(cls.public_key.like(f"{prefix_lower}%")).all()


class NodeTag(Base):
    """Custom metadata tags for nodes with typed values."""

    __tablename__ = "node_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    node_public_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    value_type: Mapped[str] = mapped_column(
        String(16), nullable=False
    )  # string/number/boolean/coordinate
    value_string: Mapped[Optional[str]] = mapped_column(String(512))
    value_number: Mapped[Optional[float]] = mapped_column(Float)
    value_boolean: Mapped[Optional[bool]] = mapped_column(Boolean)
    latitude: Mapped[Optional[float]] = mapped_column(Float)  # For coordinate type
    longitude: Mapped[Optional[float]] = mapped_column(Float)  # For coordinate type
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_node_tags_unique", "node_public_key", "key", unique=True),
        Index("idx_node_tags_node", "node_public_key"),
        Index("idx_node_tags_key", "key"),
    )


class Message(Base):
    """Represents a direct or channel message."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)  # inbound/outbound
    message_type: Mapped[str] = mapped_column(String(16), nullable=False)  # contact/channel
    pubkey_prefix: Mapped[Optional[str]] = mapped_column(String(12), index=True)
    channel_idx: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    txt_type: Mapped[Optional[int]] = mapped_column(Integer)  # raw meshcore txt_type byte
    path_len: Mapped[Optional[int]] = mapped_column(Integer)
    signature: Mapped[Optional[str]] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    snr: Mapped[Optional[float]] = mapped_column(Float)
    sender_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    __table_args__ = (Index("idx_messages_sender_timestamp", "sender_timestamp"),)


class Advertisement(Base):
    """Represents a node advertisement."""

    __tablename__ = "advertisements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    adv_type: Mapped[Optional[str]] = mapped_column(String(32))  # none/chat/repeater/room
    name: Mapped[Optional[str]] = mapped_column(String(128))
    flags: Mapped[Optional[int]] = mapped_column(Integer)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)


class TracePath(Base):
    """Represents a trace path result with SNR data."""

    __tablename__ = "trace_paths"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    initiator_tag: Mapped[int] = mapped_column(Integer, nullable=False)
    path_len: Mapped[Optional[int]] = mapped_column(Integer)
    flags: Mapped[Optional[int]] = mapped_column(Integer)
    auth: Mapped[Optional[int]] = mapped_column(Integer)
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


class EventLog(Base):
    """Raw event log for all MeshCore events."""

    __tablename__ = "events_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_data: Mapped[str] = mapped_column(Text, nullable=False)  # JSON full event payload
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)
