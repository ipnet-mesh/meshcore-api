"""FastAPI application factory and configuration."""

import logging
from typing import Optional
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from prometheus_fastapi_instrumentator import Instrumentator

from .schemas import ErrorResponse

logger = logging.getLogger(__name__)


def create_app(
    title: str = "MeshCore API",
    version: str = "1.0.0",
    enable_metrics: bool = True,
) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        title: API title for OpenAPI documentation
        version: API version
        enable_metrics: Whether to enable Prometheus metrics

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title=title,
        version=version,
        description="""
# MeshCore API

This API provides access to MeshCore network events and allows sending commands to the mesh network.

## Features

- **Query Events**: Retrieve messages, advertisements, telemetry, and other network events
- **Node Management**: List and search nodes by public key (full 64 hex characters or prefix)
- **Send Commands**: Send messages, pings, trace paths, and telemetry requests
- **Health Monitoring**: Check system and MeshCore connection status
- **Metrics**: Prometheus metrics endpoint for observability
- **Node Tags**: Manage custom metadata for nodes (friendly names, locations, etc.)

## Public Key Requirements

Most endpoints require **full 64-character hexadecimal public keys**:
- All write operations (tags, commands) require full 64-char keys
- Query endpoints (messages, advertisements, telemetry, tags) require full 64-char keys
- Use `GET /api/v1/nodes/{prefix}` to resolve partial keys to full keys first

**Workflow:**
1. Search by prefix: `GET /api/v1/nodes/abc123` (returns all matching nodes)
2. Use full key for operations: `GET /api/v1/nodes/{full-64-char-key}/messages`

## Authentication

Currently, this API does not require authentication. This may change in future versions.

## Rate Limiting

No rate limiting is currently enforced.

## Data Retention

Data is automatically cleaned up based on the configured retention period (default: 30 days).
        """,
        contact={
            "name": "MeshCore API",
            "url": "https://github.com/ipnet-mesh/meshcore-api",
        },
        license_info={
            "name": "MIT",
        },
        openapi_tags=[
            {
                "name": "health",
                "description": "Health check endpoints for monitoring system status",
            },
            {
                "name": "nodes",
                "description": "Node management and querying",
            },
            {
                "name": "messages",
                "description": "Message history and querying",
            },
            {
                "name": "advertisements",
                "description": "Node advertisement events",
            },
            {
                "name": "telemetry",
                "description": "Telemetry data from nodes",
            },
            {
                "name": "trace-paths",
                "description": "Network trace path results",
            },
            {
                "name": "commands",
                "description": "Send commands to the mesh network",
            },
            {
                "name": "tags",
                "description": "Custom node metadata and tags",
            },
        ],
    )

    # =========================================================================
    # CORS Middleware
    # =========================================================================
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, specify allowed origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # =========================================================================
    # Exception Handlers
    # =========================================================================

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Handle request validation errors."""
        # Convert errors to a JSON-serializable format
        errors = []
        for error in exc.errors():
            # Create a clean error dict with only serializable values
            error_dict = {
                "loc": list(error.get("loc", [])),
                "msg": str(error.get("msg", "")),
                "type": str(error.get("type", "")),
            }
            # Add input value if present (convert to string for safety)
            if "input" in error:
                error_dict["input"] = str(error["input"])
            errors.append(error_dict)

        logger.warning(f"Validation error on {request.url}: {len(errors)} error(s)")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "Validation error",
                "detail": errors,
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Handle unexpected exceptions."""
        logger.error(f"Unexpected error on {request.url}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "detail": str(exc) if logger.level == logging.DEBUG else None,
            },
        )

    # =========================================================================
    # Startup/Shutdown Events
    # =========================================================================

    @app.on_event("startup")
    async def startup_event():
        """Execute on application startup."""
        logger.info("FastAPI application starting up")

    @app.on_event("shutdown")
    async def shutdown_event():
        """Execute on application shutdown."""
        logger.info("FastAPI application shutting down")

    # =========================================================================
    # Import and Include Routers
    # =========================================================================

    from .routes import health, nodes, messages, advertisements
    from .routes import telemetry, trace_paths, commands, tags

    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(tags.router, prefix="/api/v1", tags=["tags"])
    app.include_router(nodes.router, prefix="/api/v1", tags=["nodes"])
    app.include_router(messages.router, prefix="/api/v1", tags=["messages"])
    app.include_router(advertisements.router, prefix="/api/v1", tags=["advertisements"])
    app.include_router(telemetry.router, prefix="/api/v1", tags=["telemetry"])
    app.include_router(trace_paths.router, prefix="/api/v1", tags=["trace-paths"])
    app.include_router(commands.router, prefix="/api/v1", tags=["commands"])

    # =========================================================================
    # Prometheus Metrics
    # =========================================================================

    if enable_metrics:
        instrumentator = Instrumentator(
            should_group_status_codes=True,
            should_ignore_untemplated=True,
            should_respect_env_var=False,  # Don't require ENABLE_METRICS env var
            should_instrument_requests_inprogress=True,
            excluded_handlers=["/metrics"],
            inprogress_name="fastapi_inprogress",
            inprogress_labels=True,
        )
        instrumentator.instrument(app).expose(app, endpoint="/metrics")
        logger.info("Prometheus metrics enabled at /metrics")

    logger.info(f"FastAPI application created: {title} v{version}")

    return app
