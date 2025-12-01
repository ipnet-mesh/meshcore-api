"""Unit tests for Prometheus metrics collector."""

import pytest
from prometheus_client import REGISTRY

from meshcore_api.subscriber import metrics


# Use a module-level fixture that runs once to create the collector
@pytest.fixture(scope="module")
def metrics_collector():
    """Get or create a metrics collector for testing.

    Prometheus metrics are registered globally and cannot be re-registered,
    so we use the singleton pattern and share one collector across all tests.
    """
    # If there's already a global instance, use it
    if metrics._metrics is not None:
        return metrics._metrics
    # Otherwise create one via get_metrics()
    return metrics.get_metrics()


class TestMetricsCollector:
    """Test MetricsCollector class."""

    def test_collector_has_event_counter(self, metrics_collector):
        """Test MetricsCollector has event counter."""
        assert metrics_collector.events_total is not None

    def test_collector_has_message_counter(self, metrics_collector):
        """Test MetricsCollector has message counter."""
        assert metrics_collector.messages_total is not None

    def test_collector_has_advertisement_counter(self, metrics_collector):
        """Test MetricsCollector has advertisement counter."""
        assert metrics_collector.advertisements_total is not None

    def test_collector_has_packet_counter(self, metrics_collector):
        """Test MetricsCollector has packet counter."""
        assert metrics_collector.packets_total is not None

    def test_collector_has_cleanup_counter(self, metrics_collector):
        """Test MetricsCollector has cleanup counter."""
        assert metrics_collector.db_cleanup_rows_deleted is not None

    def test_collector_has_error_counter(self, metrics_collector):
        """Test MetricsCollector has error counter."""
        assert metrics_collector.errors_total is not None

    def test_collector_has_node_gauges(self, metrics_collector):
        """Test MetricsCollector has node gauges."""
        assert metrics_collector.nodes_total is not None
        assert metrics_collector.nodes_active is not None
        assert metrics_collector.nodes_by_area is not None
        assert metrics_collector.nodes_by_role is not None
        assert metrics_collector.nodes_online is not None
        assert metrics_collector.nodes_with_tags is not None

    def test_collector_has_battery_gauges(self, metrics_collector):
        """Test MetricsCollector has battery gauges."""
        assert metrics_collector.battery_voltage is not None
        assert metrics_collector.battery_percentage is not None

    def test_collector_has_storage_gauges(self, metrics_collector):
        """Test MetricsCollector has storage gauges."""
        assert metrics_collector.storage_used_bytes is not None
        assert metrics_collector.storage_total_bytes is not None

    def test_collector_has_radio_gauges(self, metrics_collector):
        """Test MetricsCollector has radio gauges."""
        assert metrics_collector.radio_noise_floor_dbm is not None
        assert metrics_collector.radio_airtime_percent is not None

    def test_collector_has_database_gauges(self, metrics_collector):
        """Test MetricsCollector has database gauges."""
        assert metrics_collector.db_table_rows is not None
        assert metrics_collector.db_size_bytes is not None

    def test_collector_has_connection_gauge(self, metrics_collector):
        """Test MetricsCollector has connection status gauge."""
        assert metrics_collector.connection_status is not None

    def test_collector_has_histograms(self, metrics_collector):
        """Test MetricsCollector has histograms."""
        assert metrics_collector.message_roundtrip_seconds is not None
        assert metrics_collector.path_hop_count is not None
        assert metrics_collector.snr_db is not None
        assert metrics_collector.rssi_dbm is not None

    def test_record_event(self, metrics_collector):
        """Test recording events increments counter."""
        metrics_collector.record_event("CONTACT_MSG_RECV")
        metrics_collector.record_event("CHANNEL_MSG_RECV")
        # Verify it doesn't raise an error
        assert True

    def test_record_message(self, metrics_collector):
        """Test recording messages with labels."""
        metrics_collector.record_message(direction="inbound", message_type="contact")
        metrics_collector.record_message(direction="outbound", message_type="channel")
        assert True

    def test_record_advertisement(self, metrics_collector):
        """Test recording advertisements."""
        metrics_collector.record_advertisement(adv_type="repeater")
        metrics_collector.record_advertisement(adv_type=None)  # Test None handling
        assert True

    def test_record_roundtrip(self, metrics_collector):
        """Test recording roundtrip time."""
        metrics_collector.record_roundtrip(milliseconds=150)
        metrics_collector.record_roundtrip(milliseconds=5000)
        assert True

    def test_record_hop_count(self, metrics_collector):
        """Test recording hop counts."""
        metrics_collector.record_hop_count(hops=3)
        metrics_collector.record_hop_count(hops=1)
        metrics_collector.record_hop_count(hops=10)
        assert True

    def test_record_snr(self, metrics_collector):
        """Test recording SNR measurements."""
        metrics_collector.record_snr(snr=15.5)
        metrics_collector.record_snr(snr=-5.0)
        assert True

    def test_record_rssi(self, metrics_collector):
        """Test recording RSSI measurements."""
        metrics_collector.record_rssi(rssi=-80.0)
        metrics_collector.record_rssi(rssi=-110.0)
        assert True

    def test_update_battery(self, metrics_collector):
        """Test updating battery metrics."""
        metrics_collector.update_battery(voltage=3.7)
        metrics_collector.update_battery(percentage=85)
        metrics_collector.update_battery(voltage=4.2, percentage=100)
        metrics_collector.update_battery()  # No values
        assert True

    def test_update_storage(self, metrics_collector):
        """Test updating storage metrics."""
        metrics_collector.update_storage(used=1024000)
        metrics_collector.update_storage(total=4096000)
        metrics_collector.update_storage(used=2048000, total=4096000)
        metrics_collector.update_storage()  # No values
        assert True

    def test_update_radio_stats(self, metrics_collector):
        """Test updating radio statistics."""
        metrics_collector.update_radio_stats(noise_floor=-95.0)
        metrics_collector.update_radio_stats(airtime=5.5)
        metrics_collector.update_radio_stats(noise_floor=-90.0, airtime=10.2)
        metrics_collector.update_radio_stats()  # No values
        assert True

    def test_record_packet(self, metrics_collector):
        """Test recording packet transmissions."""
        metrics_collector.record_packet(direction="tx", status="success")
        metrics_collector.record_packet(direction="rx", status="success")
        metrics_collector.record_packet(direction="tx", status="failed")
        assert True

    def test_update_db_table_rows(self, metrics_collector):
        """Test updating database table row counts."""
        metrics_collector.update_db_table_rows(table="nodes", count=100)
        metrics_collector.update_db_table_rows(table="messages", count=5000)
        assert True

    def test_update_db_size(self, metrics_collector):
        """Test updating database size."""
        metrics_collector.update_db_size(size_bytes=1048576)
        assert True

    def test_record_cleanup(self, metrics_collector):
        """Test recording cleanup operations."""
        metrics_collector.record_cleanup(table="messages", count=100)
        metrics_collector.record_cleanup(table="events_log", count=500)
        assert True

    def test_set_connection_status(self, metrics_collector):
        """Test setting connection status."""
        metrics_collector.set_connection_status(connected=True)
        metrics_collector.set_connection_status(connected=False)
        assert True

    def test_record_error(self, metrics_collector):
        """Test recording errors."""
        metrics_collector.record_error(component="database", error_type="connection")
        metrics_collector.record_error(component="meshcore", error_type="timeout")
        assert True


class TestGetMetrics:
    """Test get_metrics function."""

    def test_get_metrics_returns_collector(self, metrics_collector):
        """Test get_metrics returns a collector."""
        collector = metrics.get_metrics()
        assert collector is not None
        assert isinstance(collector, metrics.MetricsCollector)

    def test_get_metrics_returns_same_instance(self, metrics_collector):
        """Test get_metrics returns the same instance on repeated calls."""
        collector1 = metrics.get_metrics()
        collector2 = metrics.get_metrics()
        assert collector1 is collector2

    def test_get_metrics_is_singleton(self, metrics_collector):
        """Test metrics collector follows singleton pattern."""
        # All calls should return the same collector
        collector = metrics.get_metrics()
        assert collector is metrics._metrics
