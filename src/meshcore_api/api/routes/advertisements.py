"""Advertisement querying endpoints."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..dependencies import get_db
from ..schemas import AdvertisementListResponse
from ...database.models import Advertisement, Node
from ...utils.address import normalize_public_key

router = APIRouter()


@router.get(
    "/advertisements",
    response_model=AdvertisementListResponse,
    summary="Query advertisements",
    description="Get node advertisements with optional filters for node, type, and date range",
)
async def query_advertisements(
    node_prefix: Optional[str] = Query(None, min_length=2, max_length=64, description="Filter by node public key prefix"),
    adv_type: Optional[str] = Query(None, description="Filter by advertisement type (none/chat/repeater/room)"),
    start_date: Optional[datetime] = Query(None, description="Filter advertisements after this date (ISO 8601)"),
    end_date: Optional[datetime] = Query(None, description="Filter advertisements before this date (ISO 8601)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of advertisements to return"),
    offset: int = Query(0, ge=0, description="Number of advertisements to skip"),
    db: Session = Depends(get_db),
) -> AdvertisementListResponse:
    """
    Query advertisements with filters.

    Args:
        node_prefix: Filter by node public key prefix (2-64 chars)
        adv_type: Filter by advertisement type
        start_date: Only include advertisements after this timestamp
        end_date: Only include advertisements before this timestamp
        limit: Maximum number of advertisements to return (1-1000)
        offset: Number of advertisements to skip for pagination
        db: Database session

    Returns:
        Paginated list of advertisements matching the filters
    """
    # Start with base query
    query = db.query(Advertisement)

    # Apply node_prefix filter
    if node_prefix:
        normalized_prefix = normalize_public_key(node_prefix)
        # Find all nodes matching the prefix
        matching_nodes = Node.find_by_prefix(db, normalized_prefix)
        if matching_nodes:
            node_keys = [node.public_key for node in matching_nodes]
            query = query.filter(Advertisement.public_key.in_(node_keys))
        else:
            # No matching nodes, return empty result
            return AdvertisementListResponse(
                advertisements=[],
                total=0,
                limit=limit,
                offset=offset,
            )

    # Apply adv_type filter
    if adv_type:
        query = query.filter(Advertisement.adv_type == adv_type.lower())

    # Apply date filters
    if start_date:
        query = query.filter(Advertisement.received_at >= start_date)
    if end_date:
        query = query.filter(Advertisement.received_at <= end_date)

    # Order by received_at (newest first)
    query = query.order_by(desc(Advertisement.received_at))

    # Get total count before pagination
    total = query.count()

    # Apply pagination
    advertisements = query.limit(limit).offset(offset).all()

    return AdvertisementListResponse(
        advertisements=[adv.__dict__ for adv in advertisements],
        total=total,
        limit=limit,
        offset=offset,
    )
