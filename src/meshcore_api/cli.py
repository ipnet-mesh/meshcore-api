"""Command-line interface for MeshCore API."""

import asyncio
import logging
import signal
import sys
from pathlib import Path

import click

from .config import Config, MCPConfig
from .query import DatabaseQuery
from .utils.logging import setup_logging

logger = logging.getLogger(__name__)


@click.group()
def cli():
    """MeshCore API - Event collection and REST API for MeshCore networks."""
    pass


@cli.command()
@click.option(
    "--serial-port",
    type=str,
    help="Serial port for MeshCore device (e.g., /dev/ttyUSB0)",
)
@click.option(
    "--serial-baud",
    type=int,
    help="Serial baud rate (default: 115200)",
)
@click.option(
    "--db-path",
    type=click.Path(),
    help="Path to SQLite database file (default: ./data/meshcore.db)",
)
@click.option(
    "--api-host",
    type=str,
    help="API server host (default: 0.0.0.0)",
)
@click.option(
    "--api-port",
    type=int,
    help="API server port (default: 8000)",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    help="Logging level (default: INFO)",
)
@click.option(
    "--log-format",
    type=click.Choice(["text", "json"], case_sensitive=False),
    help="Log format (default: text)",
)
@click.option(
    "--use-mock",
    is_flag=True,
    help="Use mock MeshCore instead of real device",
)
@click.option(
    "--mock-scenario",
    type=str,
    help="Mock scenario name (default: default)",
)
@click.option(
    "--mock-nodes",
    type=int,
    help="Number of mock nodes (default: 5)",
)
@click.option(
    "--retention-days",
    type=int,
    help="Data retention period in days (default: 30)",
)
@click.option(
    "--cleanup-interval-hours",
    type=int,
    help="Cleanup interval in hours (default: 24)",
)
@click.option(
    "--metrics/--no-metrics",
    default=None,
    help="Enable/disable Prometheus metrics (default: enabled)",
)
@click.option(
    "--enable-write/--no-write",
    default=None,
    help="Enable/disable write operations (default: enabled)",
)
@click.option(
    "--webhook-message-direct",
    type=str,
    help="Webhook URL for direct/contact messages",
)
@click.option(
    "--webhook-message-channel",
    type=str,
    help="Webhook URL for channel messages",
)
@click.option(
    "--webhook-advertisement",
    type=str,
    help="Webhook URL for node advertisements",
)
@click.option(
    "--webhook-timeout",
    type=int,
    help="Webhook HTTP request timeout in seconds (default: 5)",
)
@click.option(
    "--webhook-retry-count",
    type=int,
    help="Number of webhook retry attempts on failure (default: 3)",
)
@click.option(
    "--api-bearer-token",
    type=str,
    help="Bearer token for API authentication (if set, all endpoints except /docs, /redoc require authentication)",
)
@click.option(
    "--queue-max-size",
    type=int,
    help="Maximum command queue size (default: 100)",
)
@click.option(
    "--queue-full-behavior",
    type=click.Choice(["reject", "drop_oldest"], case_sensitive=False),
    help="Behavior when queue is full (default: reject)",
)
@click.option(
    "--rate-limit-per-second",
    type=float,
    help="Commands per second (average rate) (default: 0.02 = 1 per 50 seconds for LoRa duty cycle)",
)
@click.option(
    "--rate-limit-burst",
    type=int,
    help="Maximum burst size for rate limiting (default: 2)",
)
@click.option(
    "--no-rate-limit",
    is_flag=True,
    help="Disable rate limiting",
)
@click.option(
    "--debounce-window",
    type=float,
    help="Debounce window in seconds (default: 60.0)",
)
@click.option(
    "--debounce-cache-size",
    type=int,
    help="Maximum debounce cache size (default: 1000)",
)
@click.option(
    "--debounce-commands",
    type=str,
    help="Comma-separated list of command types to debounce (default: send_message,send_channel_message,send_advert)",
)
@click.option(
    "--no-debounce",
    is_flag=True,
    help="Disable debouncing",
)
def server(**kwargs):
    """Start the MeshCore API server."""
    from .__main__ import Application

    # Filter out None values (unspecified options)
    cli_args = {k: v for k, v in kwargs.items() if v is not None}

    # Load configuration from args and environment
    config = Config.from_args_and_env(cli_args)

    # Setup logging
    setup_logging(level=config.log_level, format_type=config.log_format)

    # Create and run application
    app = Application(config)

    # Setup signal handlers
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}")
        loop.create_task(app.stop())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        loop.run_until_complete(app.run())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt")
    finally:
        loop.close()


@cli.command()
@click.option(
    "--db-path",
    type=click.Path(),
    help="Path to database file",
)
@click.option(
    "--summary",
    is_flag=True,
    help="Show summary statistics only",
)
@click.option(
    "--events",
    type=int,
    metavar="N",
    help="Show N recent events",
)
@click.option(
    "--nodes",
    type=int,
    default=None,
    help="Show N discovered nodes (default: 10)",
)
@click.option(
    "--messages",
    type=int,
    default=None,
    help="Show N recent messages (default: 10)",
)
@click.option(
    "--advertisements",
    type=int,
    default=None,
    help="Show N recent advertisements (default: 10)",
)
@click.option(
    "--telemetry",
    type=int,
    default=None,
    help="Show N recent telemetry entries (default: 5)",
)
@click.option(
    "--traces",
    type=int,
    default=None,
    help="Show N recent trace paths (default: 5)",
)
@click.option(
    "--activity",
    type=int,
    default=None,
    help="Show activity timeline for last N hours (default: 24)",
)
def query(db_path, summary, events, nodes, messages, advertisements, telemetry, traces, activity):
    """Query MeshCore API database.

    Examples:

      # Full report
      meshcore-api query

      # Summary only
      meshcore-api query --summary

      # Recent messages
      meshcore-api query --messages 20

      # Nodes discovered
      meshcore-api query --nodes 15

      # Activity in last 6 hours
      meshcore-api query --activity 6
    """
    # Use Config to resolve db_path with same priority as server command
    cli_args = {}
    if db_path is not None:
        cli_args["db_path"] = db_path

    config = Config.from_args_and_env(cli_args)

    try:
        db = DatabaseQuery(config.db_path)

        # If no specific options, show full report
        if not any(
            [
                summary,
                events,
                nodes is not None,
                messages is not None,
                advertisements is not None,
                telemetry is not None,
                traces is not None,
                activity is not None,
            ]
        ):
            db.print_full_report()
        else:
            # Show requested sections
            if summary or any([events, nodes, messages, advertisements]):
                db.print_summary()

            if events:
                db.print_recent_events(events)

            if nodes is not None:
                db.print_nodes(nodes if nodes > 0 else 10)

            if messages is not None:
                db.print_messages(messages if messages > 0 else 10)

            if advertisements is not None:
                db.print_advertisements(advertisements if advertisements > 0 else 10)

            if telemetry is not None:
                db.print_telemetry(telemetry if telemetry > 0 else 5)

            if traces is not None:
                db.print_trace_paths(traces if traces > 0 else 5)

            if activity is not None:
                db.print_activity_timeline(activity if activity > 0 else 24)

            print()  # Final newline

        db.close()

    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Database error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("json_file", type=click.Path(exists=True))
@click.option(
    "--db-path",
    type=click.Path(),
    help="Path to database file",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview changes without applying them",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Show detailed progress for each node",
)
@click.option(
    "--continue-on-error",
    is_flag=True,
    help="Continue processing even if some nodes fail",
)
@click.option(
    "--validate-only",
    is_flag=True,
    help="Only validate the JSON file without applying changes",
)
def tag(json_file, db_path, dry_run, verbose, continue_on_error, validate_only):
    """Import node tags from a JSON file.

    The JSON file should contain a mapping of node public keys (64 hex chars)
    to tag objects. Each tag object should have 'value_type' and 'value' fields.

    Example JSON format:

    \b
    {
      "abc123...def": {
        "friendly_name": {"value_type": "string", "value": "Gateway"},
        "location": {
          "value_type": "coordinate",
          "value": {"latitude": 37.7749, "longitude": -122.4194}
        },
        "is_gateway": {"value_type": "boolean", "value": true},
        "battery_count": {"value_type": "number", "value": 4}
      }
    }

    Examples:

    \b
      # Apply tags from file
      meshcore_api tag node_tags.json

      # Preview changes
      meshcore_api tag node_tags.json --dry-run

      # Use custom database path with verbose output
      meshcore_api tag node_tags.json --db-path ./custom.db --verbose

      # Validate only without applying
      meshcore_api tag node_tags.json --validate-only
    """
    from .database.engine import DatabaseEngine
    from .tag_importer import TagImporter

    # Use Config to resolve db_path with same priority as server command
    cli_args = {}
    if db_path is not None:
        cli_args["db_path"] = db_path

    config = Config.from_args_and_env(cli_args)

    try:
        # Initialize database engine
        db_engine = DatabaseEngine(config.db_path)
        db_engine.initialize()

        # Create importer and process file
        importer = TagImporter(db_engine)
        result = importer.import_from_file(
            json_file,
            dry_run=dry_run,
            continue_on_error=continue_on_error,
            validate_only=validate_only,
            verbose=verbose,
        )

        # Close database
        db_engine.close()

        # Exit with appropriate code
        if result.success:
            sys.exit(0)
        else:
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--host",
    type=str,
    help="MCP server host (default: 0.0.0.0)",
)
@click.option(
    "--port",
    type=int,
    help="MCP server port (default: 8081)",
)
@click.option(
    "--mcp-api-bearer-token",
    type=str,
    help="Bearer token for MCP server authentication (optional)",
)
@click.option(
    "--api-url",
    type=str,
    help="MeshCore API URL (e.g., http://localhost:8080)",
)
@click.option(
    "--api-token",
    type=str,
    help="MeshCore API bearer token for authentication",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    help="Logging level (default: INFO)",
)
@click.option(
    "--stdio",
    is_flag=True,
    help="Run in stdio mode instead of HTTP server",
)
def mcp(host, port, mcp_api_bearer_token, api_url, api_token, log_level, stdio):
    """Start the MeshCore MCP server.

    The MCP server provides Model Context Protocol tools for interacting
    with the MeshCore API. It can run as an HTTP server (default) or in
    stdio mode for direct integration.

    Examples:

    \b
      # Start MCP server pointing to local API
      meshcore_api mcp --api-url http://localhost:8000

      # With MCP server authentication (protects the MCP server itself)
      meshcore_api mcp --api-url http://localhost:8000 --mcp-api-bearer-token "mcp-secret"

      # With MeshCore API authentication (for API that requires auth)
      meshcore_api mcp --api-url http://localhost:8000 --api-token "api-secret"

      # With both authentications
      meshcore_api mcp --api-url http://localhost:8000 --mcp-api-bearer-token "mcp-secret" --api-token "api-secret"

      # Custom port
      meshcore_api mcp --api-url http://localhost:8000 --port 9000

      # Debug logging
      meshcore_api mcp --api-url http://localhost:8000 --log-level DEBUG

      # Stdio mode for direct MCP integration
      meshcore_api mcp --api-url http://localhost:8000 --stdio
    """
    from .mcp.server import run_server, run_stdio

    # Build CLI args dict
    cli_args = {}
    if host is not None:
        cli_args["host"] = host
    if port is not None:
        cli_args["port"] = port
    if mcp_api_bearer_token is not None:
        cli_args["mcp_api_bearer_token"] = mcp_api_bearer_token
    if api_url is not None:
        cli_args["api_url"] = api_url
    if api_token is not None:
        cli_args["api_token"] = api_token
    if log_level is not None:
        cli_args["log_level"] = log_level

    # Load configuration
    config = MCPConfig.from_args_and_env(cli_args)

    # Setup logging
    setup_logging(level=config.log_level)

    # Log configuration
    logger.info(config.display())

    # Run server
    if stdio:
        run_stdio(config)
    else:
        run_server(config)


if __name__ == "__main__":
    cli()
