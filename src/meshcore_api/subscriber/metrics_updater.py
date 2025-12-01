"""Periodic metrics updater for database statistics."""

import logging
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import func

from ..database.engine import session_scope
from ..database.models import (
    Advertisement,
    EventLog,
    Message,
    Node,
    NodeTag,
    Telemetry,
    TracePath,
)
from .metrics import get_metrics

logger = logging.getLogger(__name__)


def update_database_metrics(db_path: str) -> None:
    """
    Update Prometheus metrics with current database statistics.

    Args:
        db_path: Path to the database file
    """
    try:
        metrics = get_metrics()

        with session_scope() as session:
            # Update table row counts
            tables = [
                ("nodes", Node),
                ("messages", Message),
                ("advertisements", Advertisement),
                ("telemetry", Telemetry),
                ("trace_paths", TracePath),
                ("events_log", EventLog),
                ("node_tags", NodeTag),
            ]

            for table_name, model in tables:
                count = session.query(func.count(model.id)).scalar()
                metrics.update_db_table_rows(table_name, count)

            # Update total nodes count
            total_nodes = session.query(func.count(Node.id)).scalar()
            metrics.nodes_total.set(total_nodes)

            # Update active nodes (seen in last hour) by type
            one_hour_ago = datetime.now() - timedelta(hours=1)

            # Count active nodes by type
            node_types = (
                session.query(Node.node_type, func.count(Node.id))
                .filter(Node.last_seen >= one_hour_ago)
                .group_by(Node.node_type)
                .all()
            )

            # Set all known types to 0 first, then update with actual counts
            for node_type in ["rep", "cli", "room", "none", None]:
                type_label = node_type if node_type else "unknown"
                metrics.nodes_active.labels(node_type=type_label).set(0)

            for node_type, count in node_types:
                type_label = node_type if node_type else "unknown"
                metrics.nodes_active.labels(node_type=type_label).set(count)

            # Database file size
            db_file = Path(db_path)
            if db_file.exists():
                db_size = db_file.stat().st_size
                metrics.update_db_size(db_size)

            # Calculate average SNR from recent messages (last 1000)
            recent_messages = (
                session.query(Message.snr)
                .filter(Message.snr.isnot(None))
                .order_by(Message.received_at.desc())
                .limit(1000)
                .all()
            )

            for msg in recent_messages:
                if msg.snr is not None:
                    metrics.record_snr(msg.snr)

            # Count messages by type
            message_stats = (
                session.query(Message.direction, Message.message_type, func.count(Message.id))
                .group_by(Message.direction, Message.message_type)
                .all()
            )

            # Note: These are cumulative counters, we just log the info
            for direction, msg_type, count in message_stats:
                logger.debug(f"Messages {direction}/{msg_type}: {count}")

            # Count advertisements by type
            advert_stats = (
                session.query(Advertisement.adv_type, func.count(Advertisement.id))
                .group_by(Advertisement.adv_type)
                .all()
            )

            for adv_type, count in advert_stats:
                logger.debug(f"Advertisements {adv_type}: {count}")

            # Count trace paths
            trace_count = session.query(func.count(TracePath.id)).scalar()
            logger.debug(f"Trace paths: {trace_count}")

            # Average hop count from trace paths
            avg_hops = (
                session.query(func.avg(TracePath.hop_count))
                .filter(TracePath.hop_count.isnot(None))
                .scalar()
            )

            if avg_hops:
                logger.debug(f"Average hop count: {avg_hops:.2f}")

            # Tag-based metrics
            # Count nodes by area
            area_counts = (
                session.query(
                    NodeTag.value_string, func.count(func.distinct(NodeTag.node_public_key))
                )
                .filter(NodeTag.key == "area", NodeTag.value_type == "string")
                .group_by(NodeTag.value_string)
                .all()
            )

            # Reset all area counts to 0 first
            for area, _ in area_counts:
                metrics.nodes_by_area.labels(area=area).set(0)

            # Set actual counts
            for area, count in area_counts:
                metrics.nodes_by_area.labels(area=area).set(count)
                logger.debug(f"Nodes in area {area}: {count}")

            # Count nodes by mesh role
            role_counts = (
                session.query(
                    NodeTag.value_string, func.count(func.distinct(NodeTag.node_public_key))
                )
                .filter(NodeTag.key == "mesh_role", NodeTag.value_type == "string")
                .group_by(NodeTag.value_string)
                .all()
            )

            # Reset all role counts to 0 first
            for role, _ in role_counts:
                metrics.nodes_by_role.labels(role=role).set(0)

            # Set actual counts
            for role, count in role_counts:
                metrics.nodes_by_role.labels(role=role).set(count)
                logger.debug(f"Nodes with role {role}: {count}")

            # Count online nodes
            online_count = (
                session.query(func.count(func.distinct(NodeTag.node_public_key)))
                .filter(
                    NodeTag.key == "is_online",
                    NodeTag.value_type == "boolean",
                    NodeTag.value_boolean == True,
                )
                .scalar()
            )

            if online_count:
                metrics.nodes_online.set(online_count)
                logger.debug(f"Online nodes: {online_count}")
            else:
                metrics.nodes_online.set(0)

            # Count nodes with at least one tag
            nodes_with_tags = session.query(
                func.count(func.distinct(NodeTag.node_public_key))
            ).scalar()

            if nodes_with_tags:
                metrics.nodes_with_tags.set(nodes_with_tags)
                logger.debug(f"Nodes with tags: {nodes_with_tags}")
            else:
                metrics.nodes_with_tags.set(0)

            logger.debug("Database metrics updated successfully")

    except Exception as e:
        logger.error(f"Failed to update database metrics: {e}", exc_info=True)
        metrics = get_metrics()
        metrics.record_error("metrics_updater", "update_failed")
