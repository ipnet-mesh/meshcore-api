"""Main application entry point."""

import asyncio
import logging
import signal
import sys
from typing import Optional
import uvicorn

from .config import Config
from .database.engine import init_database, session_scope
from .database.models import Node, Advertisement
from .database.cleanup import DataCleanup
from .meshcore import RealMeshCore, MockMeshCore, MeshCoreInterface
from .subscriber.event_handler import EventHandler
from .subscriber.metrics import get_metrics
from .subscriber.metrics_updater import update_database_metrics
from .utils.logging import setup_logging
from .api.app import create_app
from .api.dependencies import set_meshcore_instance, set_config_instance, set_command_queue_instance
from .webhook import WebhookHandler
from .queue import CommandQueueManager, CommandType, QueueFullBehavior

logger = logging.getLogger(__name__)


class Application:
    """Main application controller."""

    def __init__(self, config: Config):
        """
        Initialize application.

        Args:
            config: Application configuration
        """
        self.config = config
        self.meshcore: Optional[MeshCoreInterface] = None
        self.command_queue: Optional[CommandQueueManager] = None
        self.event_handler: Optional[EventHandler] = None
        self.webhook_handler: Optional[WebhookHandler] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        self.metrics_task: Optional[asyncio.Task] = None
        self.api_server_task: Optional[asyncio.Task] = None
        self.running = False

    async def start(self) -> None:
        """Start the application."""
        logger.info("Starting MeshCore API")
        logger.info(f"\n{self.config.display()}")

        # Initialize database
        logger.info("Initializing database...")
        init_database(self.config.db_path)

        # Initialize metrics
        if self.config.metrics_enabled:
            metrics = get_metrics()
            metrics.set_connection_status(False)

        # Initialize MeshCore (real or mock)
        if self.config.use_mock:
            logger.info("Initializing Mock MeshCore")
            self.meshcore = MockMeshCore(
                scenario_name=self.config.mock_scenario,
                loop_scenario=self.config.mock_loop,
                num_nodes=self.config.mock_nodes,
                min_interval=self.config.mock_min_interval,
                max_interval=self.config.mock_max_interval,
                center_lat=self.config.mock_center_lat,
                center_lon=self.config.mock_center_lon,
            )
        else:
            logger.info("Initializing Real MeshCore")
            self.meshcore = RealMeshCore(
                serial_port=self.config.serial_port,
                baud_rate=self.config.serial_baud,
            )

        # Connect to MeshCore
        logger.info("Connecting to MeshCore...")
        connected = await self.meshcore.connect()

        if not connected:
            logger.error("Failed to connect to MeshCore")
            sys.exit(1)

        logger.info("Connected to MeshCore successfully")

        if self.config.metrics_enabled:
            metrics.set_connection_status(True)

        # Initialize webhook handler if any webhook URLs are configured
        if any([
            self.config.webhook_message_direct,
            self.config.webhook_message_channel,
            self.config.webhook_advertisement,
        ]):
            logger.info("Initializing webhook handler")
            self.webhook_handler = WebhookHandler(
                message_direct_url=self.config.webhook_message_direct,
                message_channel_url=self.config.webhook_message_channel,
                advertisement_url=self.config.webhook_advertisement,
                message_direct_jsonpath=self.config.webhook_message_direct_jsonpath,
                message_channel_jsonpath=self.config.webhook_message_channel_jsonpath,
                advertisement_jsonpath=self.config.webhook_advertisement_jsonpath,
                timeout=self.config.webhook_timeout,
                retry_count=self.config.webhook_retry_count,
            )

        # Initialize event handler (needs meshcore for contact lookups)
        self.event_handler = EventHandler(
            meshcore=self.meshcore,
            webhook_handler=self.webhook_handler,
        )

        # Subscribe to events
        logger.info("Subscribing to MeshCore events...")
        await self.meshcore.subscribe_to_events(self.event_handler.handle_event)

        # Initialize command queue manager
        logger.info("Initializing command queue manager...")
        debounce_commands = set()
        if self.config.debounce_commands:
            for cmd_str in self.config.debounce_commands.split(','):
                cmd_str = cmd_str.strip()
                try:
                    debounce_commands.add(CommandType(cmd_str))
                except ValueError:
                    logger.warning(f"Invalid debounce command type: {cmd_str}")

        self.command_queue = CommandQueueManager(
            meshcore=self.meshcore,
            max_queue_size=self.config.queue_max_size,
            queue_full_behavior=QueueFullBehavior(self.config.queue_full_behavior),
            queue_timeout_seconds=self.config.queue_timeout_seconds,
            rate_limit_per_second=self.config.rate_limit_per_second,
            rate_limit_burst=self.config.rate_limit_burst,
            rate_limit_enabled=self.config.rate_limit_enabled,
            debounce_window_seconds=self.config.debounce_window_seconds,
            debounce_cache_max_size=self.config.debounce_cache_max_size,
            debounce_enabled=self.config.debounce_enabled,
            debounce_commands=debounce_commands if debounce_commands else None,
        )

        # Start command queue worker
        logger.info("Starting command queue worker...")
        await self.command_queue.start()

        # Make MeshCore, Config, and CommandQueue instances available to API routes
        set_meshcore_instance(self.meshcore)
        set_config_instance(self.config)
        set_command_queue_instance(self.command_queue)

        # Query contacts from device
        await self._query_contacts()

        # Sync device clock and announce presence
        await self._sync_clock()
        await self._send_startup_advert()

        # Start API server
        logger.info(f"Starting API server on {self.config.api_host}:{self.config.api_port}")
        self.api_server_task = asyncio.create_task(self._run_api_server())

        # Start cleanup task
        if self.config.retention_days > 0:
            logger.info(f"Starting cleanup task (every {self.config.cleanup_interval_hours} hours)")
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())

        # Start metrics update task
        if self.config.metrics_enabled:
            logger.info("Starting metrics update task (every 30 seconds)")
            self.metrics_task = asyncio.create_task(self._metrics_loop())

        self.running = True
        logger.info("Application started successfully")

    async def stop(self) -> None:
        """Stop the application."""
        logger.info("Stopping MeshCore API...")
        self.running = False

        # Cancel API server task
        if self.api_server_task:
            self.api_server_task.cancel()
            try:
                await self.api_server_task
            except asyncio.CancelledError:
                pass

        # Cancel cleanup task
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass

        # Cancel metrics task
        if self.metrics_task:
            self.metrics_task.cancel()
            try:
                await self.metrics_task
            except asyncio.CancelledError:
                pass

        # Stop command queue worker
        if self.command_queue:
            logger.info("Stopping command queue worker...")
            await self.command_queue.stop()

        # Close webhook handler
        if self.webhook_handler:
            await self.webhook_handler.close()

        # Disconnect from MeshCore
        if self.meshcore:
            await self.meshcore.disconnect()

        # Update metrics
        if self.config.metrics_enabled:
            metrics = get_metrics()
            metrics.set_connection_status(False)

        logger.info("Application stopped")

    async def _run_api_server(self) -> None:
        """Run the FastAPI server."""
        try:
            # Create FastAPI app
            app = create_app(
                title=self.config.api_title,
                version=self.config.api_version,
                enable_metrics=self.config.metrics_enabled,
                bearer_token=self.config.api_bearer_token,
            )

            # Configure uvicorn
            config = uvicorn.Config(
                app,
                host=self.config.api_host,
                port=self.config.api_port,
                log_level="info",
                access_log=True,
            )

            server = uvicorn.Server(config)

            # Run server
            await server.serve()

        except asyncio.CancelledError:
            logger.info("API server shutting down...")
            raise
        except Exception as e:
            logger.error(f"API server error: {e}", exc_info=True)
            if self.config.metrics_enabled:
                metrics = get_metrics()
                metrics.record_error("api_server", "server_failed")

    async def _cleanup_loop(self) -> None:
        """Background task for periodic database cleanup."""
        cleanup = DataCleanup(self.config.retention_days)

        while self.running:
            try:
                # Wait for interval
                await asyncio.sleep(self.config.cleanup_interval_hours * 3600)

                # Run cleanup
                logger.info("Running database cleanup...")
                deleted_counts = cleanup.cleanup_old_data()

                # Update metrics
                if self.config.metrics_enabled:
                    metrics = get_metrics()
                    for table, count in deleted_counts.items():
                        if count > 0:
                            metrics.record_cleanup(table, count)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}", exc_info=True)
                if self.config.metrics_enabled:
                    metrics = get_metrics()
                    metrics.record_error("cleanup", "cleanup_failed")

    async def _metrics_loop(self) -> None:
        """Background task for periodic metrics updates."""
        # Update metrics immediately on startup
        update_database_metrics(self.config.db_path)

        while self.running:
            try:
                # Wait for interval (30 seconds)
                await asyncio.sleep(30)

                # Update metrics
                update_database_metrics(self.config.db_path)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in metrics loop: {e}", exc_info=True)
                metrics = get_metrics()
                metrics.record_error("metrics_updater", "update_loop_failed")

    async def _sync_clock(self) -> None:
        """Synchronize MeshCore clock with host time."""
        if not self.meshcore:
            return

        try:
            logger.info("Synchronizing MeshCore clock with host time")
            result = await self.meshcore.sync_clock()
            if result.type == "ERROR":
                logger.error(f"Clock sync failed: {result.payload.get('error', result.payload)}")
            else:
                logger.info("Clock sync request sent successfully")
        except Exception as e:
            logger.error(f"Failed to sync clock: {e}", exc_info=True)

    async def _query_contacts(self) -> None:
        """Query contacts from MeshCore device during startup."""
        if not self.meshcore:
            return

        try:
            logger.info("Querying contacts from MeshCore device...")
            contacts = await self.meshcore.get_contacts()
            if contacts:
                logger.info(f"Retrieved {len(contacts)} contacts from device")
                for contact in contacts:
                    logger.debug(f"  - {contact.public_key[:8]}... ({contact.name or 'unnamed'}, {contact.node_type or 'unknown'})")
            else:
                logger.info("No contacts found on device")
        except Exception as e:
            logger.error(f"Failed to query contacts: {e}", exc_info=True)

    async def _send_startup_advert(self) -> None:
        """Send an advertisement during startup."""
        if not self.meshcore:
            return

        try:
            logger.info("Sending startup advertisement")
            result = await self.meshcore.send_advert(flood=True)
            if result.type == "ERROR":
                logger.error(f"Startup advertisement failed: {result.payload.get('error', result.payload)}")
            else:
                logger.info("Startup advertisement sent successfully")
        except Exception as e:
            logger.error(f"Failed to send startup advertisement: {e}", exc_info=True)

    async def run(self) -> None:
        """Run the application until interrupted."""
        try:
            await self.start()

            # Keep running until interrupted
            while self.running:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error(f"Application error: {e}", exc_info=True)
        finally:
            await self.stop()


def main() -> None:
    """Main entry point - delegates to CLI."""
    from .cli import cli
    cli()


if __name__ == "__main__":
    main()
