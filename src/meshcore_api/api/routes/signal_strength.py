"""Signal strength querying endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ...database.models import SignalStrength
from ...utils.address import normalize_public_key, validate_public_key
from ..dependencies import get_db
from ..schemas import SignalStrengthListResponse

router = APIRouter()


@router.get(
    "/signal-strength",
    response_model=SignalStrengthListResponse,
    summary="Query signal strength measurements",
    description=(
        "Get signal strength measurements between nodes with optional filters. "
        "All public keys must be full 64 hex characters."
    ),
)
async def query_signal_strength(
    source_public_key: Optional[str] = Query(
        None,
        min_length=64,
        max_length=64,
        description="Filter by source node public key (full 64 hex characters)",
    ),
    destination_public_key: Optional[str] = Query(
        None,
        min_length=64,
        max_length=64,
        description="Filter by destination node public key (full 64 hex characters)",
    ),
    start_date: Optional[datetime] = Query(
        None, description="Filter signal strength records after this date (ISO 8601)"
    ),
    end_date: Optional[datetime] = Query(
        None, description="Filter signal strength records before this date (ISO 8601)"
    ),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    db: Session = Depends(get_db),
) -> SignalStrengthListResponse:
    """
    Query signal strength measurements with filters.

    Args:
        source_public_key: Filter by source node public key (must be exactly 64 hex characters)
        destination_public_key: Filter by destination node public key (exactly 64 hex characters)
        start_date: Only include records after this timestamp
        end_date: Only include records before this timestamp
        limit: Maximum number of records to return (1-1000)
        offset: Number of records to skip for pagination
        db: Database session

    Returns:
        Paginated list of signal strength records matching the filters
    """
    # Start with base query
    query = db.query(SignalStrength)

    # Apply source_public_key filter
    if source_public_key:
        try:
            normalized_key = normalize_public_key(source_public_key)
            if not validate_public_key(normalized_key, allow_prefix=False):
                raise ValueError("Invalid public key length")
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="source_public_key must be exactly 64 hexadecimal characters",
            )
        query = query.filter(SignalStrength.source_public_key == normalized_key)

    # Apply destination_public_key filter
    if destination_public_key:
        try:
            normalized_key = normalize_public_key(destination_public_key)
            if not validate_public_key(normalized_key, allow_prefix=False):
                raise ValueError("Invalid public key length")
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="destination_public_key must be exactly 64 hexadecimal characters",
            )
        query = query.filter(SignalStrength.destination_public_key == normalized_key)

    # Apply date filters
    if start_date:
        query = query.filter(SignalStrength.recorded_at >= start_date)
    if end_date:
        query = query.filter(SignalStrength.recorded_at <= end_date)

    # Order by recorded_at (newest first)
    query = query.order_by(desc(SignalStrength.recorded_at))

    # Get total count before pagination
    total = query.count()

    # Apply pagination
    signal_strengths = query.limit(limit).offset(offset).all()

    return SignalStrengthListResponse(
        signal_strengths=[s.__dict__ for s in signal_strengths],
        total=total,
        limit=limit,
        offset=offset,
    )
