"""Health check endpoints."""

import os
import time
from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..dependencies import get_db, get_meshcore
from ..schemas import HealthCheckResponse, DatabaseHealthResponse, MeshCoreHealthResponse
from ...database.models import (
    Node, Message, Advertisement, Path, TracePath, Telemetry,
    Acknowledgment, StatusResponse, Statistics, BinaryResponse,
    ControlData, RawData, DeviceInfo, EventLog
)
from ...meshcore.interface import MeshCoreInterface

router = APIRouter()

# Track application start time
_start_time = time.time()
_events_processed = 0


def increment_event_counter():
    """Increment the events processed counter."""
    global _events_processed
    _events_processed += 1


def get_events_processed() -> int:
    """Get the number of events processed."""
    return _events_processed


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Overall health check",
    description="Check the overall health status of the application including MeshCore and database connectivity",
)
async def health_check(
    db: Session = Depends(get_db),
    meshcore: MeshCoreInterface = Depends(get_meshcore),
) -> HealthCheckResponse:
    """
    Get overall application health status.

    Returns:
        Health check response with connection statuses and uptime
    """
    # Check database connectivity
    db_connected = False
    try:
        db.execute(text("SELECT 1"))
        db_connected = True
    except Exception:
        pass

    # Check MeshCore connectivity
    meshcore_connected = await meshcore.is_connected() if hasattr(meshcore, 'is_connected') else True

    # Calculate uptime
    uptime = time.time() - _start_time

    # Overall status
    overall_status = "healthy" if (db_connected and meshcore_connected) else "unhealthy"

    return HealthCheckResponse(
        status=overall_status,
        meshcore_connected=meshcore_connected,
        database_connected=db_connected,
        uptime_seconds=uptime,
        events_processed=_events_processed,
    )


@router.get(
    "/health/db",
    response_model=DatabaseHealthResponse,
    summary="Database health check",
    description="Check database connectivity and get statistics about stored data",
)
async def database_health(db: Session = Depends(get_db)) -> DatabaseHealthResponse:
    """
    Get database health status and statistics.

    Returns:
        Database health response with table row counts and size
    """
    db_connected = False
    table_counts: Dict[str, int] = {}
    db_size_bytes = None

    try:
        # Test connectivity
        db.execute(text("SELECT 1"))
        db_connected = True

        # Get table row counts
        table_counts = {
            "nodes": db.query(Node).count(),
            "messages": db.query(Message).count(),
            "advertisements": db.query(Advertisement).count(),
            "paths": db.query(Path).count(),
            "trace_paths": db.query(TracePath).count(),
            "telemetry": db.query(Telemetry).count(),
            "acknowledgments": db.query(Acknowledgment).count(),
            "status_responses": db.query(StatusResponse).count(),
            "statistics": db.query(Statistics).count(),
            "binary_responses": db.query(BinaryResponse).count(),
            "control_data": db.query(ControlData).count(),
            "raw_data": db.query(RawData).count(),
            "device_info": db.query(DeviceInfo).count(),
            "events_log": db.query(EventLog).count(),
        }

        # Get database file size
        db_path = db.bind.url.database
        if db_path and os.path.exists(db_path):
            db_size_bytes = os.path.getsize(db_path)

    except Exception as e:
        db_connected = False

    status_text = "healthy" if db_connected else "unhealthy"

    return DatabaseHealthResponse(
        status=status_text,
        connected=db_connected,
        database_size_bytes=db_size_bytes,
        table_counts=table_counts,
    )


@router.get(
    "/health/meshcore",
    response_model=MeshCoreHealthResponse,
    summary="MeshCore health check",
    description="Check MeshCore connection status and get device information",
)
async def meshcore_health(
    meshcore: MeshCoreInterface = Depends(get_meshcore),
) -> MeshCoreHealthResponse:
    """
    Get MeshCore connection health status.

    Returns:
        MeshCore health response with connection status and device info
    """
    # Check if connected
    connected = await meshcore.is_connected() if hasattr(meshcore, 'is_connected') else True

    # Determine mode (real or mock)
    mode = "mock" if "Mock" in meshcore.__class__.__name__ else "real"

    # Get device info if available
    device_info = None
    # TODO: Add method to get device info from meshcore if available

    status_text = "connected" if connected else "disconnected"

    return MeshCoreHealthResponse(
        status=status_text,
        connected=connected,
        mode=mode,
        device_info=device_info,
    )
