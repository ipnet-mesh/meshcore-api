"""Configuration management with CLI args, environment variables, and defaults."""

import os
import argparse
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    """Application configuration."""

    # === Connection ===
    serial_port: str = "/dev/ttyUSB0"
    serial_baud: int = 115200
    use_mock: bool = False
    mock_scenario: Optional[str] = None
    mock_loop: bool = False
    mock_nodes: int = 10
    mock_min_interval: float = 1.0
    mock_max_interval: float = 10.0
    mock_center_lat: float = 45.5231
    mock_center_lon: float = -122.6765

    # === Database ===
    db_path: str = "./data/meshcore.db"
    retention_days: int = 30
    cleanup_interval_hours: int = 1

    # === API ===
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_title: str = "MeshCore API"
    api_version: str = "1.0.0"

    # === Prometheus ===
    metrics_enabled: bool = True

    # === Write Operations ===
    enable_write: bool = True

    # === Logging ===
    log_level: str = "INFO"
    log_format: str = "json"  # json|text

    # === Webhooks ===
    webhook_message_direct: Optional[str] = None
    webhook_message_channel: Optional[str] = None
    webhook_advertisement: Optional[str] = None
    webhook_timeout: int = 5
    webhook_retry_count: int = 3

    @classmethod
    def from_args_and_env(cls, cli_args: Optional[dict] = None) -> "Config":
        """
        Load configuration from CLI arguments, environment variables, and defaults.

        Priority: CLI args > Environment variables > Defaults

        Args:
            cli_args: Optional dictionary of CLI arguments (if not provided, will parse from sys.argv)

        Returns:
            Config instance
        """
        # Parse CLI arguments if not provided
        if cli_args is None:
            parser = argparse.ArgumentParser(
                description="MeshCore API - Event collector and API server",
                formatter_class=argparse.ArgumentDefaultsHelpFormatter
            )
        else:
            # Use a dummy parser when cli_args is provided
            parser = argparse.ArgumentParser(
                description="MeshCore API - Event collector and API server",
                formatter_class=argparse.ArgumentDefaultsHelpFormatter
            )

        # Connection arguments
        conn_group = parser.add_argument_group('Connection')
        conn_group.add_argument(
            "--serial-port",
            type=str,
            help="Serial port device (e.g., /dev/ttyUSB0)"
        )
        conn_group.add_argument(
            "--serial-baud",
            type=int,
            help="Serial baud rate"
        )
        conn_group.add_argument(
            "--use-mock",
            action="store_true",
            help="Use mock MeshCore instead of real device"
        )
        conn_group.add_argument(
            "--mock-scenario",
            type=str,
            help="Mock scenario name for playback"
        )
        conn_group.add_argument(
            "--mock-loop",
            action="store_true",
            help="Loop mock scenario indefinitely"
        )
        conn_group.add_argument(
            "--mock-nodes",
            type=int,
            help="Number of simulated nodes in random mode"
        )
        conn_group.add_argument(
            "--mock-min-interval",
            type=float,
            help="Minimum interval between random events (seconds)"
        )
        conn_group.add_argument(
            "--mock-max-interval",
            type=float,
            help="Maximum interval between random events (seconds)"
        )
        conn_group.add_argument(
            "--mock-center-lat",
            type=float,
            help="Center latitude for simulated nodes"
        )
        conn_group.add_argument(
            "--mock-center-lon",
            type=float,
            help="Center longitude for simulated nodes"
        )

        # Database arguments
        db_group = parser.add_argument_group('Database')
        db_group.add_argument(
            "--db-path",
            type=str,
            help="SQLite database file path"
        )
        db_group.add_argument(
            "--retention-days",
            type=int,
            help="Data retention period in days"
        )
        db_group.add_argument(
            "--cleanup-interval-hours",
            type=int,
            help="Cleanup task interval in hours"
        )

        # API arguments
        api_group = parser.add_argument_group('API')
        api_group.add_argument(
            "--api-host",
            type=str,
            help="API server host"
        )
        api_group.add_argument(
            "--api-port",
            type=int,
            help="API server port"
        )
        api_group.add_argument(
            "--api-title",
            type=str,
            help="API title for OpenAPI documentation"
        )
        api_group.add_argument(
            "--api-version",
            type=str,
            help="API version"
        )

        # Prometheus arguments
        metrics_group = parser.add_argument_group('Metrics')
        metrics_group.add_argument(
            "--no-metrics",
            action="store_true",
            help="Disable Prometheus metrics"
        )

        # Write operations arguments
        write_group = parser.add_argument_group('Write Operations')
        write_group.add_argument(
            "--no-write",
            action="store_true",
            help="Disable write operations (read-only mode)"
        )

        # Logging arguments
        log_group = parser.add_argument_group('Logging')
        log_group.add_argument(
            "--log-level",
            type=str,
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            help="Logging level"
        )
        log_group.add_argument(
            "--log-format",
            type=str,
            choices=["json", "text"],
            help="Log output format"
        )

        # Webhook arguments
        webhook_group = parser.add_argument_group('Webhooks')
        webhook_group.add_argument(
            "--webhook-message-direct",
            type=str,
            help="Webhook URL for direct/contact messages"
        )
        webhook_group.add_argument(
            "--webhook-message-channel",
            type=str,
            help="Webhook URL for channel messages"
        )
        webhook_group.add_argument(
            "--webhook-advertisement",
            type=str,
            help="Webhook URL for node advertisements"
        )
        webhook_group.add_argument(
            "--webhook-timeout",
            type=int,
            help="Webhook HTTP request timeout in seconds"
        )
        webhook_group.add_argument(
            "--webhook-retry-count",
            type=int,
            help="Number of webhook retry attempts on failure"
        )

        # Only parse args if not provided
        if cli_args is None:
            args = parser.parse_args()
        else:
            # Create an argparse Namespace from the provided dict
            args = argparse.Namespace(**{
                'serial_port': cli_args.get('serial_port'),
                'serial_baud': cli_args.get('serial_baud'),
                'use_mock': cli_args.get('use_mock', False),
                'mock_scenario': cli_args.get('mock_scenario'),
                'mock_loop': cli_args.get('mock_loop', False),
                'mock_nodes': cli_args.get('mock_nodes'),
                'mock_min_interval': cli_args.get('mock_min_interval'),
                'mock_max_interval': cli_args.get('mock_max_interval'),
                'mock_center_lat': cli_args.get('mock_center_lat'),
                'mock_center_lon': cli_args.get('mock_center_lon'),
                'db_path': cli_args.get('db_path'),
                'retention_days': cli_args.get('retention_days'),
                'cleanup_interval_hours': cli_args.get('cleanup_interval_hours'),
                'api_host': cli_args.get('api_host'),
                'api_port': cli_args.get('api_port'),
                'api_title': cli_args.get('api_title'),
                'api_version': cli_args.get('api_version'),
                'no_metrics': cli_args.get('metrics') is False if 'metrics' in cli_args else False,
                'no_write': cli_args.get('enable_write') is False if 'enable_write' in cli_args else False,
                'log_level': cli_args.get('log_level'),
                'log_format': cli_args.get('log_format'),
                'webhook_message_direct': cli_args.get('webhook_message_direct'),
                'webhook_message_channel': cli_args.get('webhook_message_channel'),
                'webhook_advertisement': cli_args.get('webhook_advertisement'),
                'webhook_timeout': cli_args.get('webhook_timeout'),
                'webhook_retry_count': cli_args.get('webhook_retry_count'),
            })

        # Helper function to get value with priority: CLI > Env > Default
        def get_value(cli_arg, env_var, default, type_converter=str):
            if cli_arg is not None:
                return cli_arg
            env_value = os.getenv(env_var)
            if env_value is not None:
                if type_converter == bool:
                    return env_value.lower() in ("true", "1", "yes", "on")
                return type_converter(env_value)
            return default

        # Build config instance
        config = cls()

        # Apply values with priority
        config.serial_port = get_value(
            args.serial_port, "MESHCORE_SERIAL_PORT", config.serial_port
        )
        config.serial_baud = get_value(
            args.serial_baud, "MESHCORE_SERIAL_BAUD", config.serial_baud, int
        )
        config.use_mock = args.use_mock or get_value(
            None, "MESHCORE_USE_MOCK", config.use_mock, bool
        )
        config.mock_scenario = get_value(
            args.mock_scenario, "MESHCORE_MOCK_SCENARIO", config.mock_scenario
        )
        config.mock_loop = args.mock_loop or get_value(
            None, "MESHCORE_MOCK_LOOP", config.mock_loop, bool
        )
        config.mock_nodes = get_value(
            args.mock_nodes, "MESHCORE_MOCK_NODES", config.mock_nodes, int
        )
        config.mock_min_interval = get_value(
            args.mock_min_interval, "MESHCORE_MOCK_MIN_INTERVAL",
            config.mock_min_interval, float
        )
        config.mock_max_interval = get_value(
            args.mock_max_interval, "MESHCORE_MOCK_MAX_INTERVAL",
            config.mock_max_interval, float
        )
        config.mock_center_lat = get_value(
            args.mock_center_lat, "MESHCORE_MOCK_CENTER_LAT",
            config.mock_center_lat, float
        )
        config.mock_center_lon = get_value(
            args.mock_center_lon, "MESHCORE_MOCK_CENTER_LON",
            config.mock_center_lon, float
        )

        config.db_path = get_value(
            args.db_path, "MESHCORE_DB_PATH", config.db_path
        )
        config.retention_days = get_value(
            args.retention_days, "MESHCORE_RETENTION_DAYS", config.retention_days, int
        )
        config.cleanup_interval_hours = get_value(
            args.cleanup_interval_hours, "MESHCORE_CLEANUP_INTERVAL_HOURS",
            config.cleanup_interval_hours, int
        )

        config.api_host = get_value(
            args.api_host, "MESHCORE_API_HOST", config.api_host
        )
        config.api_port = get_value(
            args.api_port, "MESHCORE_API_PORT", config.api_port, int
        )
        config.api_title = get_value(
            args.api_title, "MESHCORE_API_TITLE", config.api_title
        )
        config.api_version = get_value(
            args.api_version, "MESHCORE_API_VERSION", config.api_version
        )

        config.metrics_enabled = not args.no_metrics and get_value(
            None, "MESHCORE_METRICS_ENABLED", config.metrics_enabled, bool
        )

        config.enable_write = not args.no_write and get_value(
            None, "MESHCORE_ENABLE_WRITE", config.enable_write, bool
        )

        config.log_level = get_value(
            args.log_level, "MESHCORE_LOG_LEVEL", config.log_level
        )
        config.log_format = get_value(
            args.log_format, "MESHCORE_LOG_FORMAT", config.log_format
        )

        config.webhook_message_direct = get_value(
            args.webhook_message_direct, "WEBHOOK_MESSAGE_DIRECT", config.webhook_message_direct
        )
        config.webhook_message_channel = get_value(
            args.webhook_message_channel, "WEBHOOK_MESSAGE_CHANNEL", config.webhook_message_channel
        )
        config.webhook_advertisement = get_value(
            args.webhook_advertisement, "WEBHOOK_ADVERTISEMENT", config.webhook_advertisement
        )
        config.webhook_timeout = get_value(
            args.webhook_timeout, "WEBHOOK_TIMEOUT", config.webhook_timeout, int
        )
        config.webhook_retry_count = get_value(
            args.webhook_retry_count, "WEBHOOK_RETRY_COUNT", config.webhook_retry_count, int
        )

        return config

    def display(self) -> str:
        """
        Display configuration in human-readable format.

        Returns:
            Formatted configuration string
        """
        lines = [
            "Configuration:",
            "  Connection:",
            f"    Mode: {'Mock' if self.use_mock else 'Real'}",
        ]

        if self.use_mock:
            lines.extend([
                f"    Scenario: {self.mock_scenario or 'Random'}",
                f"    Loop: {self.mock_loop}",
                f"    Nodes: {self.mock_nodes}",
                f"    Event Interval: {self.mock_min_interval}-{self.mock_max_interval}s",
            ])
        else:
            lines.extend([
                f"    Serial Port: {self.serial_port}",
                f"    Baud Rate: {self.serial_baud}",
            ])

        lines.extend([
            "  Database:",
            f"    Path: {self.db_path}",
            f"    Retention: {self.retention_days} days",
            f"    Cleanup Interval: {self.cleanup_interval_hours} hours",
            "  API:",
            f"    Host: {self.api_host}",
            f"    Port: {self.api_port}",
            f"    Metrics: {'Enabled' if self.metrics_enabled else 'Disabled'}",
            f"    Write Operations: {'Enabled' if self.enable_write else 'Disabled (Read-only mode)'}",
            "  Logging:",
            f"    Level: {self.log_level}",
            f"    Format: {self.log_format}",
        ])

        # Add webhook configuration if any URLs are configured
        if any([self.webhook_message_direct, self.webhook_message_channel, self.webhook_advertisement]):
            lines.append("  Webhooks:")
            if self.webhook_message_direct:
                lines.append(f"    Direct Messages: {self.webhook_message_direct}")
            if self.webhook_message_channel:
                lines.append(f"    Channel Messages: {self.webhook_message_channel}")
            if self.webhook_advertisement:
                lines.append(f"    Advertisements: {self.webhook_advertisement}")
            lines.extend([
                f"    Timeout: {self.webhook_timeout}s",
                f"    Retry Count: {self.webhook_retry_count}",
            ])

        return "\n".join(lines)
