"""Configuration for the MCP (Model Context Protocol) server.

This module defines the MCPConfig class used by the MCP command.
All MCP-specific configuration uses the MCP_* environment variable prefix.
"""

from dataclasses import dataclass
from typing import Optional

from .base import EnvVars, get_config_value


@dataclass
class MCPConfig:
    """MCP server configuration.

    Configuration can be set via:
    1. CLI arguments (highest priority)
    2. Environment variables
    3. Default values (lowest priority)

    Environment variable naming convention:
    - All MCP config uses MCP_* prefix
    - MCP_HOST, MCP_PORT for server binding
    - MCP_API_BEARER_TOKEN for MCP server authentication
    - MCP_API_URL, MCP_API_TOKEN for connecting to the MeshCore API
    - MCP_LOG_LEVEL for logging (note: uses MCP_ prefix, not MESHCORE_)
    """

    # === Server ===
    host: str = "0.0.0.0"
    port: int = 8081

    # === MCP Server Authentication ===
    mcp_api_bearer_token: Optional[str] = None  # Bearer token to protect the MCP server itself

    # === API Connection ===
    api_url: Optional[str] = None
    api_token: Optional[str] = None  # Bearer token for authenticating with MeshCore API

    # === Logging ===
    log_level: str = "INFO"

    @classmethod
    def from_args_and_env(cls, cli_args: Optional[dict] = None) -> "MCPConfig":
        """
        Load configuration from CLI arguments, environment variables, and defaults.

        Priority: CLI args > Environment variables > Defaults

        Args:
            cli_args: Optional dictionary of CLI arguments

        Returns:
            MCPConfig instance
        """
        if cli_args is None:
            cli_args = {}

        config = cls()

        # === Server settings ===
        config.host = get_config_value(cli_args.get("host"), EnvVars.MCP_HOST, config.host)
        config.port = get_config_value(cli_args.get("port"), EnvVars.MCP_PORT, config.port, int)

        # === MCP Server Authentication ===
        config.mcp_api_bearer_token = get_config_value(
            cli_args.get("mcp_api_bearer_token"),
            EnvVars.MCP_API_BEARER_TOKEN,
            config.mcp_api_bearer_token,
        )

        # === API Connection (with backward compatibility for legacy env vars) ===
        config.api_url = get_config_value(
            cli_args.get("api_url"),
            EnvVars.MCP_API_URL,
            config.api_url,
            str,
            EnvVars.LEGACY_MCP_API_URL,  # Fallback to MESHCORE_API_URL
        )
        config.api_token = get_config_value(
            cli_args.get("api_token"),
            EnvVars.MCP_API_TOKEN,
            config.api_token,
            str,
            EnvVars.LEGACY_MCP_API_TOKEN,  # Fallback to MESHCORE_API_TOKEN
        )

        # === Logging (MCP-specific, with fallback to MESHCORE_LOG_LEVEL) ===
        config.log_level = get_config_value(
            cli_args.get("log_level"),
            EnvVars.MCP_LOG_LEVEL,
            config.log_level,
            str,
            EnvVars.LOG_LEVEL,  # Fallback to MESHCORE_LOG_LEVEL
        )

        return config

    @property
    def is_configured(self) -> bool:
        """Check if the API URL is configured."""
        return self.api_url is not None

    def display(self) -> str:
        """Display configuration in human-readable format."""
        lines = [
            "MCP Server Configuration:",
            f"  Host: {self.host}",
            f"  Port: {self.port}",
            f"  MCP API Bearer Token: {'configured' if self.mcp_api_bearer_token else 'not configured'}",
            f"  API URL: {self.api_url or '(not configured)'}",
            f"  API Token: {'configured' if self.api_token else 'not configured'}",
            f"  Log Level: {self.log_level}",
        ]
        return "\n".join(lines)
