"""Database cleanup for data retention."""

import logging
from datetime import datetime, timedelta
from sqlalchemy import delete
from .models import Message, Advertisement, Telemetry, TracePath, EventLog
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

            # Cleanup event log
            result = session.execute(
                delete(EventLog).where(EventLog.created_at < cutoff_date)
            )
            deleted_counts["events_log"] = result.rowcount

        total_deleted = sum(deleted_counts.values())
        logger.info(f"Cleanup complete: {total_deleted} total records deleted")
        logger.debug(f"Deleted by table: {deleted_counts}")

        return deleted_counts
