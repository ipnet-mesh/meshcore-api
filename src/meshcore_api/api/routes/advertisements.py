"""Advertisement querying endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ...database.models import Advertisement
from ...utils.address import normalize_public_key, validate_public_key
from ..dependencies import get_db
from ..schemas import AdvertisementListResponse

router = APIRouter()


@router.get(
    "/advertisements",
    response_model=AdvertisementListResponse,
    summary="Query advertisements",
    description="Get node advertisements with optional filters for node public key (full 64 chars), type, and date range",
)
async def query_advertisements(
    node_public_key: Optional[str] = Query(
        None,
        min_length=64,
        max_length=64,
        description="Filter by node public key (full 64 hex characters)",
    ),
    adv_type: Optional[str] = Query(
        None, description="Filter by advertisement type (none/chat/repeater/room)"
    ),
    start_date: Optional[datetime] = Query(
        None, description="Filter advertisements after this date (ISO 8601)"
    ),
    end_date: Optional[datetime] = Query(
        None, description="Filter advertisements before this date (ISO 8601)"
    ),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of advertisements to return"
    ),
    offset: int = Query(0, ge=0, description="Number of advertisements to skip"),
    db: Session = Depends(get_db),
) -> AdvertisementListResponse:
    """
    Query advertisements with filters.

    Args:
        node_public_key: Filter by node public key (must be exactly 64 hex characters)
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

    # Apply node_public_key filter
    if node_public_key:
        # Validate and normalize the full public key
        try:
            normalized_key = normalize_public_key(node_public_key)
            if not validate_public_key(normalized_key, allow_prefix=False):
                raise ValueError("Invalid public key length")
        except (ValueError, TypeError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="node_public_key must be exactly 64 hexadecimal characters",
            )
        # Use full key for query (advertisements table stores full 64-char keys)
        query = query.filter(Advertisement.public_key == normalized_key)

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
