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
from .utils.logging import setup_logging
from .api.app import create_app
from .api.dependencies import set_meshcore_instance

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
        self.event_handler: Optional[EventHandler] = None
        self.cleanup_task: Optional[asyncio.Task] = None
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

        # Initialize event handler (needs meshcore for contact lookups)
        self.event_handler = EventHandler(meshcore=self.meshcore)

        # Subscribe to events
        logger.info("Subscribing to MeshCore events...")
        await self.meshcore.subscribe_to_events(self.event_handler.handle_event)

        # Make MeshCore instance available to API routes
        set_meshcore_instance(self.meshcore)

        # Start API server
        logger.info(f"Starting API server on {self.config.api_host}:{self.config.api_port}")
        self.api_server_task = asyncio.create_task(self._run_api_server())

        # Start cleanup task
        if self.config.retention_days > 0:
            logger.info(f"Starting cleanup task (every {self.config.cleanup_interval_hours} hours)")
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())

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
    """Main entry point."""
    # Load configuration
    config = Config.from_args_and_env()

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


if __name__ == "__main__":
    main()
