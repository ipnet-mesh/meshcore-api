"""Pydantic models for webhook payload structures."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class WebhookPayload(BaseModel):
    """Base webhook payload structure sent to external URLs."""

    event_type: str
    timestamp: datetime
    data: dict[str, Any]


class MessageData(BaseModel):
    """Message webhook data structure matching database Message model."""

    id: int
    direction: str
    message_type: str
    pubkey_prefix: Optional[str] = None
    channel_idx: Optional[int] = None
    content: str
    snr: Optional[float] = None
    sender_timestamp: Optional[datetime] = None
    received_at: datetime


class AdvertisementData(BaseModel):
    """Advertisement webhook data structure matching database Advertisement model."""

    id: int
    public_key: str
    adv_type: Optional[str] = None
    name: Optional[str] = None
    flags: Optional[int] = None
    received_at: datetime
