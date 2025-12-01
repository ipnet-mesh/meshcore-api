"""Prometheus metrics collector."""

import logging

from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collects and exposes Prometheus metrics."""

    def __init__(self):
        """Initialize metrics."""

        # Event counters
        self.events_total = Counter(
            "meshcore_events_total", "Total MeshCore events received", ["event_type"]
        )

        self.messages_total = Counter(
            "meshcore_messages_total", "Total messages processed", ["direction", "message_type"]
        )

        self.advertisements_total = Counter(
            "meshcore_advertisements_total", "Total advertisements received", ["adv_type"]
        )

        # Latency metrics
        self.message_roundtrip_seconds = Histogram(
            "meshcore_message_roundtrip_seconds",
            "Message round-trip time in seconds",
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
        )

        # Node connectivity
        self.nodes_total = Gauge("meshcore_nodes_total", "Total unique nodes in database")

        self.nodes_active = Gauge("meshcore_nodes_active", "Nodes seen in last hour", ["node_type"])

        self.path_hop_count = Histogram(
            "meshcore_path_hop_count",
            "Distribution of path hop counts",
            buckets=[1, 2, 3, 4, 5, 6, 7, 8, 10, 15, 20],
        )

        # Signal quality
        self.snr_db = Histogram(
            "meshcore_snr_db",
            "Signal-to-noise ratio in dB",
            buckets=[-20, -10, 0, 5, 10, 15, 20, 25, 30, 40],
        )

        self.rssi_dbm = Histogram(
            "meshcore_rssi_dbm",
            "Received signal strength in dBm",
            buckets=[-120, -110, -100, -90, -80, -70, -60, -50, -40],
        )

        # Device statistics
        self.battery_voltage = Gauge("meshcore_battery_voltage", "Device battery voltage")

        self.battery_percentage = Gauge("meshcore_battery_percentage", "Device battery percentage")

        self.storage_used_bytes = Gauge("meshcore_storage_used_bytes", "Storage used in bytes")

        self.storage_total_bytes = Gauge(
            "meshcore_storage_total_bytes", "Total storage capacity in bytes"
        )

        # Radio statistics
        self.radio_noise_floor_dbm = Gauge(
            "meshcore_radio_noise_floor_dbm", "Radio noise floor in dBm"
        )

        self.radio_airtime_percent = Gauge(
            "meshcore_radio_airtime_percent", "Radio airtime utilization percentage"
        )

        self.packets_total = Counter(
            "meshcore_packets_total", "Total packets", ["direction", "status"]
        )

        # Database metrics
        self.db_table_rows = Gauge(
            "meshcore_db_table_rows", "Number of rows in database tables", ["table"]
        )

        self.db_size_bytes = Gauge("meshcore_db_size_bytes", "Database file size in bytes")

        self.db_cleanup_rows_deleted = Counter(
            "meshcore_db_cleanup_rows_deleted", "Rows deleted during retention cleanup", ["table"]
        )

        # Tag metrics
        self.nodes_by_area = Gauge("meshcore_nodes_by_area", "Number of nodes by area", ["area"])

        self.nodes_by_role = Gauge(
            "meshcore_nodes_by_role", "Number of nodes by mesh role", ["role"]
        )

        self.nodes_online = Gauge(
            "meshcore_nodes_online", "Number of nodes currently online (based on is_online tag)"
        )

        self.nodes_with_tags = Gauge(
            "meshcore_nodes_with_tags", "Number of nodes that have at least one tag"
        )

        # Application health
        self.connection_status = Gauge(
            "meshcore_connection_status", "MeshCore connection status (1=connected, 0=disconnected)"
        )

        self.errors_total = Counter(
            "meshcore_errors_total", "Total errors encountered", ["component", "error_type"]
        )

    def record_event(self, event_type: str) -> None:
        """Record an event."""
        self.events_total.labels(event_type=event_type).inc()

    def record_message(self, direction: str, message_type: str) -> None:
        """Record a message."""
        self.messages_total.labels(direction=direction, message_type=message_type).inc()

    def record_advertisement(self, adv_type: str) -> None:
        """Record an advertisement."""
        self.advertisements_total.labels(adv_type=adv_type or "unknown").inc()

    def record_roundtrip(self, milliseconds: int) -> None:
        """Record message round-trip time."""
        self.message_roundtrip_seconds.observe(milliseconds / 1000.0)

    def record_hop_count(self, hops: int) -> None:
        """Record path hop count."""
        self.path_hop_count.observe(hops)

    def record_snr(self, snr: float) -> None:
        """Record SNR measurement."""
        self.snr_db.observe(snr)

    def record_rssi(self, rssi: float) -> None:
        """Record RSSI measurement."""
        self.rssi_dbm.observe(rssi)

    def update_battery(self, voltage: float = None, percentage: int = None) -> None:
        """Update battery metrics."""
        if voltage is not None:
            self.battery_voltage.set(voltage)
        if percentage is not None:
            self.battery_percentage.set(percentage)

    def update_storage(self, used: int = None, total: int = None) -> None:
        """Update storage metrics."""
        if used is not None:
            self.storage_used_bytes.set(used)
        if total is not None:
            self.storage_total_bytes.set(total)

    def update_radio_stats(self, noise_floor: float = None, airtime: float = None) -> None:
        """Update radio statistics."""
        if noise_floor is not None:
            self.radio_noise_floor_dbm.set(noise_floor)
        if airtime is not None:
            self.radio_airtime_percent.set(airtime)

    def record_packet(self, direction: str, status: str) -> None:
        """Record packet transmission."""
        self.packets_total.labels(direction=direction, status=status).inc()

    def update_db_table_rows(self, table: str, count: int) -> None:
        """Update database table row count."""
        self.db_table_rows.labels(table=table).set(count)

    def update_db_size(self, size_bytes: int) -> None:
        """Update database size."""
        self.db_size_bytes.set(size_bytes)

    def record_cleanup(self, table: str, count: int) -> None:
        """Record cleanup operation."""
        self.db_cleanup_rows_deleted.labels(table=table).inc(count)

    def set_connection_status(self, connected: bool) -> None:
        """Set connection status."""
        self.connection_status.set(1 if connected else 0)

    def record_error(self, component: str, error_type: str) -> None:
        """Record an error."""
        self.errors_total.labels(component=component, error_type=error_type).inc()


# Global metrics collector instance
_metrics: MetricsCollector = None


def get_metrics() -> MetricsCollector:
    """Get or create global metrics collector."""
    global _metrics
    if _metrics is None:
        _metrics = MetricsCollector()
    return _metrics
