"""Pydantic schemas for API request and response validation."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Common/Shared Schemas
# ============================================================================

class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""

    limit: int = Field(100, ge=1, le=1000, description="Number of items to return")
    offset: int = Field(0, ge=0, description="Number of items to skip")


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")


# ============================================================================
# Node Schemas
# ============================================================================

class NodeResponse(BaseModel):
    """Response model for a single node."""

    id: int
    public_key: str
    node_type: Optional[str] = None
    name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    last_seen: Optional[datetime] = None
    first_seen: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class NodeListResponse(BaseModel):
    """Response model for node list."""

    nodes: List[NodeResponse]
    total: int
    limit: int
    offset: int


# ============================================================================
# Message Schemas
# ============================================================================

class MessageResponse(BaseModel):
    """Response model for a message."""

    id: int
    direction: str
    message_type: str
    text_type: str
    from_public_key: Optional[str] = None
    to_public_key: Optional[str] = None
    content: str
    snr: Optional[float] = None
    rssi: Optional[float] = None
    timestamp: datetime
    received_at: datetime

    class Config:
        from_attributes = True


class MessageListResponse(BaseModel):
    """Response model for message list."""

    messages: List[MessageResponse]
    total: int
    limit: int
    offset: int


class MessageFilters(BaseModel):
    """Query filters for messages."""

    from_prefix: Optional[str] = Field(None, min_length=2, max_length=64, description="Filter by sender public key prefix")
    to_prefix: Optional[str] = Field(None, min_length=2, max_length=64, description="Filter by recipient public key prefix")
    message_type: Optional[str] = Field(None, description="Filter by message type (contact/channel)")
    start_date: Optional[datetime] = Field(None, description="Filter messages after this date")
    end_date: Optional[datetime] = Field(None, description="Filter messages before this date")


# ============================================================================
# Advertisement Schemas
# ============================================================================

class AdvertisementResponse(BaseModel):
    """Response model for an advertisement."""

    id: int
    public_key: str
    adv_type: Optional[str] = None
    name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    flags: Optional[int] = None
    received_at: datetime

    class Config:
        from_attributes = True


class AdvertisementListResponse(BaseModel):
    """Response model for advertisement list."""

    advertisements: List[AdvertisementResponse]
    total: int
    limit: int
    offset: int


class AdvertisementFilters(BaseModel):
    """Query filters for advertisements."""

    node_prefix: Optional[str] = Field(None, min_length=2, max_length=64, description="Filter by node public key prefix")
    adv_type: Optional[str] = Field(None, description="Filter by advertisement type")
    start_date: Optional[datetime] = Field(None, description="Filter advertisements after this date")
    end_date: Optional[datetime] = Field(None, description="Filter advertisements before this date")


# ============================================================================
# Path Schemas
# ============================================================================

class PathResponse(BaseModel):
    """Response model for a routing path."""

    id: int
    node_public_key: str
    hop_count: Optional[int] = None
    updated_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class PathListResponse(BaseModel):
    """Response model for path list."""

    paths: List[PathResponse]
    total: int


# ============================================================================
# Trace Path Schemas
# ============================================================================

class TracePathResponse(BaseModel):
    """Response model for a trace path result."""

    id: int
    initiator_tag: int
    destination_public_key: Optional[str] = None
    path_hashes: Optional[str] = None
    snr_values: Optional[str] = None
    hop_count: Optional[int] = None
    completed_at: datetime

    class Config:
        from_attributes = True


class TracePathListResponse(BaseModel):
    """Response model for trace path list."""

    trace_paths: List[TracePathResponse]
    total: int
    limit: int
    offset: int


class TracePathFilters(BaseModel):
    """Query filters for trace paths."""

    destination_prefix: Optional[str] = Field(None, min_length=2, max_length=64, description="Filter by destination public key prefix")
    start_date: Optional[datetime] = Field(None, description="Filter trace paths after this date")
    end_date: Optional[datetime] = Field(None, description="Filter trace paths before this date")


# ============================================================================
# Telemetry Schemas
# ============================================================================

class TelemetryResponse(BaseModel):
    """Response model for telemetry data."""

    id: int
    node_public_key: str
    parsed_data: Optional[str] = None
    received_at: datetime

    class Config:
        from_attributes = True


class TelemetryListResponse(BaseModel):
    """Response model for telemetry list."""

    telemetry: List[TelemetryResponse]
    total: int
    limit: int
    offset: int


class TelemetryFilters(BaseModel):
    """Query filters for telemetry."""

    node_prefix: Optional[str] = Field(None, min_length=2, max_length=64, description="Filter by node public key prefix")
    start_date: Optional[datetime] = Field(None, description="Filter telemetry after this date")
    end_date: Optional[datetime] = Field(None, description="Filter telemetry before this date")


# ============================================================================
# Statistics Schemas
# ============================================================================

class StatisticsResponse(BaseModel):
    """Response model for statistics."""

    id: int
    stat_type: str
    data: str
    recorded_at: datetime

    class Config:
        from_attributes = True


class StatisticsListResponse(BaseModel):
    """Response model for statistics list."""

    statistics: List[StatisticsResponse]
    total: int


# ============================================================================
# Device Info Schemas
# ============================================================================

class DeviceInfoResponse(BaseModel):
    """Response model for device information."""

    id: int
    battery_voltage: Optional[float] = None
    battery_percentage: Optional[int] = None
    storage_used: Optional[int] = None
    storage_total: Optional[int] = None
    device_time: Optional[datetime] = None
    firmware_version: Optional[str] = None
    capabilities: Optional[str] = None
    recorded_at: datetime

    class Config:
        from_attributes = True


class DeviceInfoListResponse(BaseModel):
    """Response model for device info list."""

    device_info: List[DeviceInfoResponse]
    total: int


# ============================================================================
# Command Request Schemas
# ============================================================================

class SendMessageRequest(BaseModel):
    """Request to send a direct message."""

    destination: str = Field(..., min_length=64, max_length=64, description="64-character destination public key")
    text: str = Field(..., min_length=1, max_length=1000, description="Message text content")
    text_type: str = Field("plain", description="Text type (plain/cli_data/signed_plain)")

    @field_validator('destination')
    @classmethod
    def validate_hex(cls, v: str) -> str:
        """Validate that destination is a valid hex string."""
        if not all(c in '0123456789abcdefABCDEF' for c in v):
            raise ValueError('Destination must be a valid hexadecimal string')
        return v.lower()


class SendChannelMessageRequest(BaseModel):
    """Request to send a channel message."""

    text: str = Field(..., min_length=1, max_length=1000, description="Message text content")
    flood: bool = Field(False, description="Enable flooding")


class SendAdvertRequest(BaseModel):
    """Request to send an advertisement."""

    flood: bool = Field(False, description="Enable flooding")


class SendTracePathRequest(BaseModel):
    """Request to initiate a trace path."""

    destination: str = Field(..., min_length=64, max_length=64, description="64-character destination public key")

    @field_validator('destination')
    @classmethod
    def validate_hex(cls, v: str) -> str:
        """Validate that destination is a valid hex string."""
        if not all(c in '0123456789abcdefABCDEF' for c in v):
            raise ValueError('Destination must be a valid hexadecimal string')
        return v.lower()


class PingRequest(BaseModel):
    """Request to ping a node."""

    destination: str = Field(..., min_length=64, max_length=64, description="64-character destination public key")

    @field_validator('destination')
    @classmethod
    def validate_hex(cls, v: str) -> str:
        """Validate that destination is a valid hex string."""
        if not all(c in '0123456789abcdefABCDEF' for c in v):
            raise ValueError('Destination must be a valid hexadecimal string')
        return v.lower()


class SendTelemetryRequestRequest(BaseModel):
    """Request to send a telemetry request."""

    destination: str = Field(..., min_length=64, max_length=64, description="64-character destination public key")

    @field_validator('destination')
    @classmethod
    def validate_hex(cls, v: str) -> str:
        """Validate that destination is a valid hex string."""
        if not all(c in '0123456789abcdefABCDEF' for c in v):
            raise ValueError('Destination must be a valid hexadecimal string')
        return v.lower()


# ============================================================================
# Command Response Schemas
# ============================================================================

class SendMessageResponse(BaseModel):
    """Response from sending a message."""

    success: bool
    message: str
    estimated_delivery_ms: Optional[int] = None


class SendChannelMessageResponse(BaseModel):
    """Response from sending a channel message."""

    success: bool
    message: str


class SendAdvertResponse(BaseModel):
    """Response from sending an advertisement."""

    success: bool
    message: str


class SendTracePathResponse(BaseModel):
    """Response from initiating a trace path."""

    success: bool
    message: str
    initiator_tag: Optional[int] = None


class PingResponse(BaseModel):
    """Response from pinging a node."""

    success: bool
    message: str


class SendTelemetryRequestResponse(BaseModel):
    """Response from sending a telemetry request."""

    success: bool
    message: str


# ============================================================================
# Health Check Schemas
# ============================================================================

class HealthCheckResponse(BaseModel):
    """Response model for overall health check."""

    status: str = Field(..., description="Overall status (healthy/unhealthy)")
    meshcore_connected: bool
    database_connected: bool
    uptime_seconds: float
    events_processed: int


class DatabaseHealthResponse(BaseModel):
    """Response model for database health check."""

    status: str = Field(..., description="Database status (healthy/unhealthy)")
    connected: bool
    database_size_bytes: Optional[int] = None
    table_counts: dict


class MeshCoreHealthResponse(BaseModel):
    """Response model for MeshCore health check."""

    status: str = Field(..., description="MeshCore status (connected/disconnected)")
    connected: bool
    mode: str = Field(..., description="Connection mode (real/mock)")
    device_info: Optional[dict] = None
