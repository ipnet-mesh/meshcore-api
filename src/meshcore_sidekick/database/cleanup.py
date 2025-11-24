"""Database cleanup for data retention."""

import logging
from datetime import datetime, timedelta
from sqlalchemy import delete
from .models import (
    Message,
    Advertisement,
    Telemetry,
    TracePath,
    Acknowledgment,
    StatusResponse,
    Statistics,
    BinaryResponse,
    ControlData,
    RawData,
    EventLog,
)
from .engine import session_scope

logger = logging.getLogger(__name__)


class DataCleanup:
    """Handles automatic cleanup of old data based on retention policy."""

    def __init__(self, retention_days: int):
        """
        Initialize cleanup handler.

        Args:
            retention_days: Number of days to retain data
        """
        self.retention_days = retention_days

    def cleanup_old_data(self) -> dict:
        """
        Remove data older than retention period.

        Returns:
            Dictionary with counts of deleted records per table
        """
        cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
        deleted_counts = {}

        logger.info(f"Starting cleanup of data older than {cutoff_date.isoformat()}")

        with session_scope() as session:
            # Cleanup messages
            result = session.execute(
                delete(Message).where(Message.received_at < cutoff_date)
            )
            deleted_counts["messages"] = result.rowcount

            # Cleanup advertisements
            result = session.execute(
                delete(Advertisement).where(Advertisement.received_at < cutoff_date)
            )
            deleted_counts["advertisements"] = result.rowcount

            # Cleanup telemetry
            result = session.execute(
                delete(Telemetry).where(Telemetry.received_at < cutoff_date)
            )
            deleted_counts["telemetry"] = result.rowcount

            # Cleanup trace paths
            result = session.execute(
                delete(TracePath).where(TracePath.completed_at < cutoff_date)
            )
            deleted_counts["trace_paths"] = result.rowcount

            # Cleanup acknowledgments
            result = session.execute(
                delete(Acknowledgment).where(Acknowledgment.confirmed_at < cutoff_date)
            )
            deleted_counts["acknowledgments"] = result.rowcount

            # Cleanup status responses
            result = session.execute(
                delete(StatusResponse).where(StatusResponse.received_at < cutoff_date)
            )
            deleted_counts["status_responses"] = result.rowcount

            # Cleanup statistics
            result = session.execute(
                delete(Statistics).where(Statistics.recorded_at < cutoff_date)
            )
            deleted_counts["statistics"] = result.rowcount

            # Cleanup binary responses
            result = session.execute(
                delete(BinaryResponse).where(BinaryResponse.received_at < cutoff_date)
            )
            deleted_counts["binary_responses"] = result.rowcount

            # Cleanup control data
            result = session.execute(
                delete(ControlData).where(ControlData.received_at < cutoff_date)
            )
            deleted_counts["control_data"] = result.rowcount

            # Cleanup raw data
            result = session.execute(
                delete(RawData).where(RawData.received_at < cutoff_date)
            )
            deleted_counts["raw_data"] = result.rowcount

            # Cleanup event log
            result = session.execute(
                delete(EventLog).where(EventLog.created_at < cutoff_date)
            )
            deleted_counts["events_log"] = result.rowcount

        total_deleted = sum(deleted_counts.values())
        logger.info(f"Cleanup complete: {total_deleted} total records deleted")
        logger.debug(f"Deleted by table: {deleted_counts}")

        return deleted_counts
