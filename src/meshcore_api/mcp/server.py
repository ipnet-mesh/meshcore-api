"""
MeshCore MCP Server - HTTP Implementation

Provides MCP tools for interacting with MeshCore API.
Supports message and advertisement operations via HTTP/Streamable transport.
"""

import logging
import sys

from mcp.server.fastmcp import FastMCP

from .config import MCPConfig
from .state import state
from .tools import advertisements, messages

logger = logging.getLogger(__name__)

# Initialize MCP server with FastMCP
mcp = FastMCP("meshcore-mcp")

# Register all tools
messages.register_tools(mcp)
advertisements.register_tools(mcp)


def create_app(config: MCPConfig):
    """
    Create and configure the MCP server application.

    Args:
        config: MCP server configuration

    Returns:
        Starlette application for streamable HTTP transport
    """
    # Configure API connection via global state
    state.configure(api_url=config.api_url, api_token=config.api_token)

    if not state.is_configured:
        logger.warning(
            "No API URL configured. Set --api-url or MESHCORE_API_URL environment variable."
        )
        logger.warning("Tools will return errors until API is configured.")

    # Get the Starlette app for streamable HTTP transport
    return mcp.streamable_http_app()


def run_server(config: MCPConfig):
    """
    Run the MCP server with the given configuration.

    Args:
        config: MCP server configuration
    """
    import uvicorn

    logger.info(f"Starting MeshCore MCP Server on {config.host}:{config.port}")
    logger.info(f"Server URL: http://{config.host}:{config.port}")

    if config.api_url:
        logger.info(f"API URL: {config.api_url}")
    else:
        logger.warning(
            "No API URL configured. Set --api-url or MESHCORE_API_URL environment variable."
        )

    # Create the application
    app = create_app(config)

    # Run with uvicorn
    uvicorn.run(app, host=config.host, port=config.port)


def run_stdio(config: MCPConfig):
    """
    Run the MCP server in stdio mode for direct integration.

    Args:
        config: MCP server configuration
    """
    # Configure API connection via global state
    state.configure(api_url=config.api_url, api_token=config.api_token)

    if not state.is_configured:
        print(
            "Warning: No API URL configured. Set MESHCORE_API_URL environment variable.",
            file=sys.stderr,
        )

    # Run in stdio mode
    mcp.run()
