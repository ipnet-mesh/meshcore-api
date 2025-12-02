"""Configuration module for MeshCore API.

This module provides centralized configuration management with consistent
environment variable naming across all commands.

Usage:
    from meshcore_api.config import Config, MCPConfig
    from meshcore_api.config.base import EnvVars, get_config_value

Environment Variable Naming Convention:
    - Server/API/Database/Webhook: MESHCORE_* prefix
    - MCP Server: MCP_* prefix

For detailed documentation, see AGENTS.md.
"""

from .base import (
    ENV_PREFIX_MESHCORE,
    ENV_PREFIX_MCP,
    EnvVars,
    get_bool_config_value,
    get_config_value,
    get_env_value,
)
from .mcp import MCPConfig
from .server import Config

__all__ = [
    # Config classes
    "Config",
    "MCPConfig",
    # Environment variable utilities
    "EnvVars",
    "get_config_value",
    "get_env_value",
    "get_bool_config_value",
    # Constants
    "ENV_PREFIX_MESHCORE",
    "ENV_PREFIX_MCP",
]
