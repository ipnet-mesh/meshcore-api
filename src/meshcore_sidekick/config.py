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
    db_path: str = "./meshcore.db"
    retention_days: int = 30
    cleanup_interval_hours: int = 1

    # === API ===
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_title: str = "MeshCore Sidekick API"
    api_version: str = "1.0.0"

    # === Prometheus ===
    metrics_enabled: bool = True

    # === Logging ===
    log_level: str = "INFO"
    log_format: str = "json"  # json|text

    @classmethod
    def from_args_and_env(cls) -> "Config":
        """
        Load configuration from CLI arguments, environment variables, and defaults.

        Priority: CLI args > Environment variables > Defaults

        Returns:
            Config instance
        """
        # Parse CLI arguments
        parser = argparse.ArgumentParser(
            description="MeshCore Sidekick - Event collector and API server",
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

        args = parser.parse_args()

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

        config.log_level = get_value(
            args.log_level, "MESHCORE_LOG_LEVEL", config.log_level
        )
        config.log_format = get_value(
            args.log_format, "MESHCORE_LOG_FORMAT", config.log_format
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
            "  Logging:",
            f"    Level: {self.log_level}",
            f"    Format: {self.log_format}",
        ])

        return "\n".join(lines)
