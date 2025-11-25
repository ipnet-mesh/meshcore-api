"""Message querying endpoints."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..dependencies import get_db
from ..schemas import MessageListResponse
from ...database.models import Message, Node
from ...utils.address import normalize_public_key

router = APIRouter()


@router.get(
    "/messages",
    response_model=MessageListResponse,
    summary="Query messages",
    description="Get messages with optional filters for sender, recipient, type, and date range",
)
async def query_messages(
    from_prefix: Optional[str] = Query(None, min_length=2, max_length=64, description="Filter by sender public key prefix"),
    to_prefix: Optional[str] = Query(None, min_length=2, max_length=64, description="Filter by recipient public key prefix"),
    message_type: Optional[str] = Query(None, description="Filter by message type (contact/channel)"),
    start_date: Optional[datetime] = Query(None, description="Filter messages after this date (ISO 8601)"),
    end_date: Optional[datetime] = Query(None, description="Filter messages before this date (ISO 8601)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of messages to return"),
    offset: int = Query(0, ge=0, description="Number of messages to skip"),
    db: Session = Depends(get_db),
) -> MessageListResponse:
    """
    Query messages with filters.

    Args:
        from_prefix: Filter by sender public key prefix (2-64 chars)
        to_prefix: Filter by recipient public key prefix (2-64 chars)
        message_type: Filter by message type (contact or channel)
        start_date: Only include messages after this timestamp
        end_date: Only include messages before this timestamp
        limit: Maximum number of messages to return (1-1000)
        offset: Number of messages to skip for pagination
        db: Database session

    Returns:
        Paginated list of messages matching the filters
    """
    # Start with base query
    query = db.query(Message)

    # Apply from_prefix filter
    if from_prefix:
        normalized_prefix = normalize_public_key(from_prefix)
        # Find all nodes matching the prefix
        matching_nodes = Node.find_by_prefix(db, normalized_prefix)
        if matching_nodes:
            node_keys = [node.public_key for node in matching_nodes]
            query = query.filter(Message.from_public_key.in_(node_keys))
        else:
            # No matching nodes, return empty result
            return MessageListResponse(
                messages=[],
                total=0,
                limit=limit,
                offset=offset,
            )

    # Apply to_prefix filter
    if to_prefix:
        normalized_prefix = normalize_public_key(to_prefix)
        # Find all nodes matching the prefix
        matching_nodes = Node.find_by_prefix(db, normalized_prefix)
        if matching_nodes:
            node_keys = [node.public_key for node in matching_nodes]
            query = query.filter(Message.to_public_key.in_(node_keys))
        else:
            # No matching nodes, return empty result
            return MessageListResponse(
                messages=[],
                total=0,
                limit=limit,
                offset=offset,
            )

    # Apply message_type filter
    if message_type:
        query = query.filter(Message.message_type == message_type.lower())

    # Apply date filters
    if start_date:
        query = query.filter(Message.timestamp >= start_date)
    if end_date:
        query = query.filter(Message.timestamp <= end_date)

    # Order by timestamp (newest first)
    query = query.order_by(desc(Message.timestamp))

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
