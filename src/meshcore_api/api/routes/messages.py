"""Message querying endpoints."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..dependencies import get_db
from ..schemas import MessageListResponse
from ...database.models import Message
from ...utils.address import normalize_public_key, validate_public_key

router = APIRouter()


@router.get(
    "/messages",
    response_model=MessageListResponse,
    summary="Query messages",
    description="Get messages with optional filters for sender public key (full 64 chars), channel, type, and sender timestamp range",
)
async def query_messages(
    sender_public_key: Optional[str] = Query(None, min_length=64, max_length=64, description="Filter by sender public key (full 64 hex characters)"),
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
        sender_public_key: Filter by sender public key (must be exactly 64 hex characters)
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

    # Apply sender_public_key filter
    if sender_public_key:
        # Validate and normalize the full public key
        try:
            normalized_key = normalize_public_key(sender_public_key)
            if not validate_public_key(normalized_key, allow_prefix=False):
                raise ValueError("Invalid public key length")
        except (ValueError, TypeError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="sender_public_key must be exactly 64 hexadecimal characters",
            )
        # Truncate to 12 chars to match database storage
        pubkey_prefix_12 = normalized_key[:12]
        query = query.filter(Message.pubkey_prefix == pubkey_prefix_12)

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
