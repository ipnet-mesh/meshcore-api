"""Telemetry querying endpoints."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..dependencies import get_db
from ..schemas import TelemetryListResponse
from ...database.models import Telemetry, Node
from ...utils.address import normalize_public_key

router = APIRouter()


@router.get(
    "/telemetry",
    response_model=TelemetryListResponse,
    summary="Query telemetry data",
    description="Get telemetry data with optional filters for node and date range",
)
async def query_telemetry(
    node_prefix: Optional[str] = Query(None, min_length=2, max_length=64, description="Filter by node public key prefix"),
    start_date: Optional[datetime] = Query(None, description="Filter telemetry after this date (ISO 8601)"),
    end_date: Optional[datetime] = Query(None, description="Filter telemetry before this date (ISO 8601)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of telemetry records to return"),
    offset: int = Query(0, ge=0, description="Number of telemetry records to skip"),
    db: Session = Depends(get_db),
) -> TelemetryListResponse:
    """
    Query telemetry data with filters.

    Args:
        node_prefix: Filter by node public key prefix (2-64 chars)
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

    # Apply node_prefix filter
    if node_prefix:
        normalized_prefix = normalize_public_key(node_prefix)
        # Find all nodes matching the prefix
        matching_nodes = Node.find_by_prefix(db, normalized_prefix)
        if matching_nodes:
            node_keys = [node.public_key for node in matching_nodes]
            query = query.filter(Telemetry.node_public_key.in_(node_keys))
        else:
            # No matching nodes, return empty result
            return TelemetryListResponse(
                telemetry=[],
                total=0,
                limit=limit,
                offset=offset,
            )

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
