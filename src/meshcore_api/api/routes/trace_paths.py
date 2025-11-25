"""Trace path querying endpoints."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..dependencies import get_db
from ..schemas import TracePathListResponse
from ...database.models import TracePath

router = APIRouter()


@router.get(
    "/trace_paths",
    response_model=TracePathListResponse,
    summary="Query trace path results",
    description="Get trace path results with optional filters for destination and date range",
)
async def query_trace_paths(
    start_date: Optional[datetime] = Query(None, description="Filter trace paths after this date (ISO 8601)"),
    end_date: Optional[datetime] = Query(None, description="Filter trace paths before this date (ISO 8601)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of trace paths to return"),
    offset: int = Query(0, ge=0, description="Number of trace paths to skip"),
    db: Session = Depends(get_db),
) -> TracePathListResponse:
    """
    Query trace path results with filters.

    Args:
        start_date: Only include trace paths after this timestamp
        end_date: Only include trace paths before this timestamp
        limit: Maximum number of trace paths to return (1-1000)
        offset: Number of trace paths to skip for pagination
        db: Database session

    Returns:
        Paginated list of trace path results matching the filters
    """
    # Start with base query
    query = db.query(TracePath)

    # Apply date filters
    if start_date:
        query = query.filter(TracePath.completed_at >= start_date)
    if end_date:
        query = query.filter(TracePath.completed_at <= end_date)

    # Order by completed_at (newest first)
    query = query.order_by(desc(TracePath.completed_at))

    # Get total count before pagination
    total = query.count()

    # Apply pagination
    trace_paths = query.limit(limit).offset(offset).all()

    return TracePathListResponse(
        trace_paths=[tp.__dict__ for tp in trace_paths],
        total=total,
        limit=limit,
        offset=offset,
    )
