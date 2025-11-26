"""Signal measurement querying endpoints."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, and_, or_
from sqlalchemy.orm import Session

from ..dependencies import get_db
from ..schemas import SignalMeasurementListResponse
from ...database.models import SignalMeasurement, Node
from ...utils.address import normalize_public_key

router = APIRouter()


@router.get(
    "/signal-measurements",
    response_model=SignalMeasurementListResponse,
    summary="Query signal measurements",
    description="Get SNR (signal strength) measurements with optional filters for source, destination, type, SNR range, and timestamp",
)
async def query_signal_measurements(
    source_prefix: Optional[str] = Query(None, min_length=2, max_length=64, description="Filter by source node public key prefix"),
    destination_prefix: Optional[str] = Query(None, min_length=2, max_length=64, description="Filter by destination node public key prefix"),
    measurement_type: Optional[str] = Query(None, description="Filter by measurement type (message/trace_hop)"),
    min_snr: Optional[float] = Query(None, description="Filter for SNR >= this value (in dB)"),
    max_snr: Optional[float] = Query(None, description="Filter for SNR <= this value (in dB)"),
    start_date: Optional[datetime] = Query(None, description="Filter measurements after this timestamp (ISO 8601)"),
    end_date: Optional[datetime] = Query(None, description="Filter measurements before this timestamp (ISO 8601)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of measurements to return"),
    offset: int = Query(0, ge=0, description="Number of measurements to skip"),
    db: Session = Depends(get_db),
) -> SignalMeasurementListResponse:
    """
    Query signal measurements with filters.

    Args:
        source_prefix: Filter by source node public key prefix (2-64 chars)
        destination_prefix: Filter by destination node public key prefix (2-64 chars)
        measurement_type: Filter by measurement type (message or trace_hop)
        min_snr: Only include measurements with SNR >= this value
        max_snr: Only include measurements with SNR <= this value
        start_date: Only include measurements after this timestamp
        end_date: Only include measurements before this timestamp
        limit: Maximum number of measurements to return (1-1000)
        offset: Number of measurements to skip for pagination
        db: Database session

    Returns:
        Paginated list of signal measurements matching the filters
    """
    # Start with base query
    query = db.query(SignalMeasurement)

    # Apply source prefix filter - resolve to full keys
    if source_prefix:
        normalized_prefix = normalize_public_key(source_prefix)
        # Find all nodes matching this prefix
        matching_nodes = Node.find_by_prefix(db, normalized_prefix)
        if matching_nodes:
            # Filter measurements by any of the matching source keys
            source_keys = [node.public_key for node in matching_nodes]
            query = query.filter(SignalMeasurement.source_public_key.in_(source_keys))
        else:
            # No matching nodes - return empty result
            query = query.filter(SignalMeasurement.source_public_key == None)

    # Apply destination prefix filter - resolve to full keys
    if destination_prefix:
        normalized_prefix = normalize_public_key(destination_prefix)
        # Find all nodes matching this prefix
        matching_nodes = Node.find_by_prefix(db, normalized_prefix)
        if matching_nodes:
            # Filter measurements by any of the matching destination keys
            dest_keys = [node.public_key for node in matching_nodes]
            query = query.filter(SignalMeasurement.destination_public_key.in_(dest_keys))
        else:
            # No matching nodes - return empty result
            query = query.filter(SignalMeasurement.destination_public_key == None)

    # Apply measurement_type filter
    if measurement_type:
        query = query.filter(SignalMeasurement.measurement_type == measurement_type.lower())

    # Apply SNR range filters
    if min_snr is not None:
        query = query.filter(SignalMeasurement.snr_db >= min_snr)
    if max_snr is not None:
        query = query.filter(SignalMeasurement.snr_db <= max_snr)

    # Apply date filters
    if start_date:
        query = query.filter(SignalMeasurement.timestamp >= start_date)
    if end_date:
        query = query.filter(SignalMeasurement.timestamp <= end_date)

    # Order by timestamp (newest first)
    query = query.order_by(desc(SignalMeasurement.timestamp))

    # Get total count before pagination
    total = query.count()

    # Apply pagination
    measurements = query.limit(limit).offset(offset).all()

    return SignalMeasurementListResponse(
        measurements=[m.__dict__ for m in measurements],
        total=total,
        limit=limit,
        offset=offset,
    )
