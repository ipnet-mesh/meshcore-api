"""Statistics and device information endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..dependencies import get_db
from ..schemas import StatisticsListResponse, DeviceInfoListResponse
from ...database.models import Statistics, DeviceInfo

router = APIRouter()


@router.get(
    "/statistics",
    response_model=StatisticsListResponse,
    summary="Get device statistics",
    description="Get the latest device statistics, optionally filtered by type (core/radio/packets)",
)
async def get_statistics(
    stat_type: Optional[str] = Query(None, description="Filter by statistics type (core/radio/packets)"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of statistics records to return"),
    db: Session = Depends(get_db),
) -> StatisticsListResponse:
    """
    Get device statistics.

    Args:
        stat_type: Filter by statistics type (core, radio, or packets)
        limit: Maximum number of records to return (1-100)
        db: Database session

    Returns:
        List of statistics records, ordered by most recent first
    """
    # Start with base query
    query = db.query(Statistics)

    # Apply stat_type filter
    if stat_type:
        query = query.filter(Statistics.stat_type == stat_type.lower())

    # Order by recorded_at (newest first)
    query = query.order_by(desc(Statistics.recorded_at))

    # Get total count
    total = query.count()

    # Apply limit
    statistics = query.limit(limit).all()

    return StatisticsListResponse(
        statistics=[stat.__dict__ for stat in statistics],
        total=total,
    )


@router.get(
    "/device_info",
    response_model=DeviceInfoListResponse,
    summary="Get companion device information",
    description="Get information about the companion device including battery, storage, and firmware",
)
async def get_device_info(
    limit: int = Query(10, ge=1, le=100, description="Maximum number of device info records to return"),
    db: Session = Depends(get_db),
) -> DeviceInfoListResponse:
    """
    Get companion device information.

    Args:
        limit: Maximum number of records to return (1-100)
        db: Database session

    Returns:
        List of device information records, ordered by most recent first
    """
    # Query device info
    query = db.query(DeviceInfo).order_by(desc(DeviceInfo.recorded_at))

    # Get total count
    total = query.count()

    # Apply limit
    device_info = query.limit(limit).all()

    return DeviceInfoListResponse(
        device_info=[info.__dict__ for info in device_info],
        total=total,
    )
