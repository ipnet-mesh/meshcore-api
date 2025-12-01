"""Configuration management for MCP server."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class MCPConfig:
    """MCP server configuration."""

    # === Server ===
    host: str = "0.0.0.0"
    port: int = 8081

    # === API Connection ===
    api_url: Optional[str] = None
    api_token: Optional[str] = None

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

        def get_value(cli_key: str, env_var: str, default, type_converter=str):
            """Get value with priority: CLI > Env > Default."""
            cli_value = cli_args.get(cli_key)
            if cli_value is not None:
                return cli_value
            env_value = os.getenv(env_var)
            if env_value is not None:
                if type_converter == bool:
                    return env_value.lower() in ("true", "1", "yes", "on")
                return type_converter(env_value)
            return default

        config = cls()

        config.host = get_value("host", "MCP_HOST", config.host)
        config.port = get_value("port", "MCP_PORT", config.port, int)
        config.api_url = get_value("api_url", "MESHCORE_API_URL", config.api_url)
        config.api_token = get_value("api_token", "MESHCORE_API_TOKEN", config.api_token)
        config.log_level = get_value("log_level", "MESHCORE_LOG_LEVEL", config.log_level)

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
            f"  API URL: {self.api_url or '(not configured)'}",
            f"  API Token: {'configured' if self.api_token else 'not configured'}",
            f"  Log Level: {self.log_level}",
        ]
        return "\n".join(lines)
