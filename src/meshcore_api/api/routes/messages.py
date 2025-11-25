"""Message querying endpoints."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..dependencies import get_db
from ..schemas import MessageListResponse
from ...database.models import Message
from ...utils.address import normalize_public_key

router = APIRouter()


@router.get(
    "/messages",
    response_model=MessageListResponse,
    summary="Query messages",
    description="Get messages with optional filters for sender prefix, channel, type, and sender timestamp range",
)
async def query_messages(
    pubkey_prefix: Optional[str] = Query(None, min_length=2, max_length=12, description="Filter by sender pubkey prefix (contact messages)"),
    channel_idx: Optional[int] = Query(None, description="Filter by channel index (channel messages)"),
    message_type: Optional[str] = Query(None, description="Filter by message type (contact/channel)"),
    start_date: Optional[datetime] = Query(None, description="Filter messages after this sender_timestamp (ISO 8601)"),
    end_date: Optional[datetime] = Query(None, description="Filter messages before this sender_timestamp (ISO 8601)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of messages to return"),
    offset: int = Query(0, ge=0, description="Number of messages to skip"),
    db: Session = Depends(get_db),
) -> MessageListResponse:
    """
    Query messages with filters.

    Args:
        pubkey_prefix: Filter by sender pubkey prefix (2-12 chars)
        channel_idx: Filter by channel index
        message_type: Filter by message type (contact or channel)
        start_date: Only include messages after this sender_timestamp
        end_date: Only include messages before this sender_timestamp
        limit: Maximum number of messages to return (1-1000)
        offset: Number of messages to skip for pagination
        db: Database session

    Returns:
        Paginated list of messages matching the filters
    """
    # Start with base query
    query = db.query(Message)

    # Apply pubkey_prefix filter
    if pubkey_prefix:
        normalized_prefix = normalize_public_key(pubkey_prefix)
        query = query.filter(Message.pubkey_prefix.like(f"{normalized_prefix}%"))

    # Apply channel filter
    if channel_idx is not None:
        query = query.filter(Message.channel_idx == channel_idx)

    # Apply message_type filter
    if message_type:
        query = query.filter(Message.message_type == message_type.lower())

    # Apply date filters
    if start_date:
        query = query.filter(Message.sender_timestamp >= start_date)
    if end_date:
        query = query.filter(Message.sender_timestamp <= end_date)

    # Order by timestamp (newest first)
    query = query.order_by(desc(Message.sender_timestamp))

    # Get total count before pagination
    total = query.count()

    # Apply pagination
    messages = query.limit(limit).offset(offset).all()

    return MessageListResponse(
        messages=[msg.__dict__ for msg in messages],
        total=total,
        limit=limit,
        offset=offset,
    )
