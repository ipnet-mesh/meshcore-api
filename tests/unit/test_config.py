"""Unit tests for configuration module - fixed to match actual implementation."""

import pytest

from meshcore_api.config import Config


class TestConfig:
    """Test configuration parsing and validation."""

    def test_default_config_values(self):
        """Test default configuration values."""
        config = Config()

        # Connection defaults
        assert config.serial_port == "/dev/ttyUSB0"
        assert config.serial_baud == 115200
        assert config.use_mock is False
        assert config.mock_scenario is None
        assert config.mock_loop is False
        assert config.mock_nodes == 10
        assert config.mock_min_interval == 1.0
        assert config.mock_max_interval == 10.0
        assert config.mock_center_lat == 45.5231
        assert config.mock_center_lon == -122.6765

        # Database defaults
        assert config.db_path == "./data/meshcore.db"
        assert config.retention_days == 30
        assert config.cleanup_interval_hours == 1

        # API defaults
        assert config.api_host == "0.0.0.0"
        assert config.api_port == 8000
        assert config.api_title == "MeshCore API"
        assert config.api_version == "1.0.0"
        assert config.api_bearer_token is None

        # Other defaults
        assert config.metrics_enabled is True
        assert config.enable_write is True
        assert config.log_level == "INFO"
        assert config.log_format == "json"

        # Webhook defaults
        assert config.webhook_message_direct is None
        assert config.webhook_message_channel is None
        assert config.webhook_advertisement is None

    def test_config_custom_values(self):
        """Test configuration with custom values."""
        config = Config(
            serial_port="/dev/ttyACM0",
            use_mock=True,
            mock_nodes=20,
            api_port=9000,
            db_path="/tmp/test.db",
            log_level="DEBUG"
        )

        assert config.serial_port == "/dev/ttyACM0"
        assert config.use_mock is True
        assert config.mock_nodes == 20
        assert config.api_port == 9000
        assert config.db_path == "/tmp/test.db"
        assert config.log_level == "DEBUG"

    def test_config_webhook_configuration(self):
        """Test webhook configuration."""
        webhook_url = "http://localhost:9000/webhook"
        config = Config(
            webhook_message_direct=webhook_url,
            webhook_message_channel=webhook_url,
            webhook_advertisement=webhook_url
        )

        assert config.webhook_message_direct == webhook_url
        assert config.webhook_message_channel == webhook_url
        assert config.webhook_advertisement == webhook_url

    def test_config_mock_settings(self):
        """Test mock configuration settings."""
        config = Config(
            mock_scenario="test_scenario",
            mock_loop=True,
            mock_nodes=5,
            mock_min_interval=0.5,
            mock_max_interval=2.0,
            mock_center_lat=40.7128,
            mock_center_lon=-74.0060
        )

        assert config.mock_scenario == "test_scenario"
        assert config.mock_loop is True
        assert config.mock_nodes == 5
        assert config.mock_min_interval == 0.5
        assert config.mock_max_interval == 2.0
        assert config.mock_center_lat == 40.7128
        assert config.mock_center_lon == -74.0060

    def test_config_database_settings(self):
        """Test database configuration settings."""
        config = Config(
            db_path="/custom/path/database.db",
            retention_days=90,
            cleanup_interval_hours=24
        )

        assert config.db_path == "/custom/path/database.db"
        assert config.retention_days == 90
        assert config.cleanup_interval_hours == 24

    def test_config_api_settings(self):
        """Test API configuration settings."""
        config = Config(
            api_host="127.0.0.1",
            api_port=8080,
            api_title="Custom API",
            api_version="2.0.0",
            api_bearer_token="secret-token"
        )

        assert config.api_host == "127.0.0.1"
        assert config.api_port == 8080
        assert config.api_title == "Custom API"
        assert config.api_version == "2.0.0"
        assert config.api_bearer_token == "secret-token"

    def test_config_other_settings(self):
        """Test other configuration settings."""
        config = Config(
            metrics_enabled=False,
            enable_write=False,
            log_level="ERROR",
            log_format="text"
        )

        assert config.metrics_enabled is False
        assert config.enable_write is False
        assert config.log_level == "ERROR"
        assert config.log_format == "text"

    def test_config_dataclass_behavior(self):
        """Test that Config behaves as a dataclass."""
        config = Config(api_port=9000)

        # Test equality
        config2 = Config(api_port=9000)
        assert config == config2

        # Test inequality
        config3 = Config(api_port=8000)
        assert config != config3

        # Test string representation
        config_str = str(config)
        assert "Config" in config_str
        assert "api_port=9000" in config_str

    def test_config_optional_fields(self):
        """Test optional field handling."""
        config = Config()

        # None values for optional fields
        assert config.mock_scenario is None
        assert config.api_bearer_token is None
        assert config.webhook_message_direct is None
        assert config.webhook_message_channel is None
        assert config.webhook_advertisement is None

    def test_config_type_hints(self):
        """Test that config values have correct types."""
        config = Config()

        # Type assertions
        assert isinstance(config.serial_port, str)
        assert isinstance(config.serial_baud, int)
        assert isinstance(config.use_mock, bool)
        assert isinstance(config.mock_nodes, int)
        assert isinstance(config.mock_min_interval, float)
        assert isinstance(config.mock_max_interval, float)
        assert isinstance(config.db_path, str)
        assert isinstance(config.retention_days, int)
        assert isinstance(config.api_port, int)
        assert isinstance(config.log_level, str)

    def test_config_immutability_of_defaults(self):
        """Test that default values are appropriate."""
        config1 = Config()
        config2 = Config()

        # Ensure default values are consistent
        assert config1.serial_port == config2.serial_port
        assert config1.api_port == config2.api_port
        assert config1.use_mock == config2.use_mock