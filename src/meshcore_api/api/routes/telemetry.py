"""Telemetry querying endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ...database.models import Telemetry
from ...utils.address import normalize_public_key, validate_public_key
from ..dependencies import get_db
from ..schemas import TelemetryListResponse

router = APIRouter()


@router.get(
    "/telemetry",
    response_model=TelemetryListResponse,
    summary="Query telemetry data",
    description="Get telemetry data with optional filters for node public key (full 64 chars) and date range",
)
async def query_telemetry(
    node_public_key: Optional[str] = Query(
        None,
        min_length=64,
        max_length=64,
        description="Filter by node public key (full 64 hex characters)",
    ),
    start_date: Optional[datetime] = Query(
        None, description="Filter telemetry after this date (ISO 8601)"
    ),
    end_date: Optional[datetime] = Query(
        None, description="Filter telemetry before this date (ISO 8601)"
    ),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of telemetry records to return"
    ),
    offset: int = Query(0, ge=0, description="Number of telemetry records to skip"),
    db: Session = Depends(get_db),
) -> TelemetryListResponse:
    """
    Query telemetry data with filters.

    Args:
        node_public_key: Filter by node public key (must be exactly 64 hex characters)
        start_date: Only include telemetry after this timestamp
        end_date: Only include telemetry before this timestamp
        limit: Maximum number of records to return (1-1000)
        offset: Number of records to skip for pagination
        db: Database session

    Returns:
        Paginated list of telemetry records matching the filters
    """
    # Start with base query
    query = db.query(Telemetry)

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
        # Use full key for query (telemetry table stores full 64-char keys)
        query = query.filter(Telemetry.node_public_key == normalized_key)

    # Apply date filters
    if start_date:
        query = query.filter(Telemetry.received_at >= start_date)
    if end_date:
        query = query.filter(Telemetry.received_at <= end_date)

    # Order by received_at (newest first)
    query = query.order_by(desc(Telemetry.received_at))

    # Get total count before pagination
    total = query.count()

    # Apply pagination
    telemetry = query.limit(limit).offset(offset).all()

    return TelemetryListResponse(
        telemetry=[t.__dict__ for t in telemetry],
        total=total,
        limit=limit,
        offset=offset,
    )
