"""Shared configuration utilities and constants.

This module provides the foundation for consistent configuration handling
across all commands (server, query, tag, mcp).
"""

import os
from typing import Any, Optional, TypeVar, Union

# Type variable for config classes
T = TypeVar("T")

# === Environment Variable Prefixes ===
# All environment variables should use these prefixes for consistency

ENV_PREFIX_MESHCORE = "MESHCORE_"
ENV_PREFIX_MCP = "MCP_"

# === Environment Variable Names ===
# Centralized definition of all environment variable names


class EnvVars:
    """Centralized environment variable names for consistent access."""

    # === Connection ===
    SERIAL_PORT = f"{ENV_PREFIX_MESHCORE}SERIAL_PORT"
    SERIAL_BAUD = f"{ENV_PREFIX_MESHCORE}SERIAL_BAUD"
    USE_MOCK = f"{ENV_PREFIX_MESHCORE}USE_MOCK"
    MOCK_SCENARIO = f"{ENV_PREFIX_MESHCORE}MOCK_SCENARIO"
    MOCK_LOOP = f"{ENV_PREFIX_MESHCORE}MOCK_LOOP"
    MOCK_NODES = f"{ENV_PREFIX_MESHCORE}MOCK_NODES"
    MOCK_MIN_INTERVAL = f"{ENV_PREFIX_MESHCORE}MOCK_MIN_INTERVAL"
    MOCK_MAX_INTERVAL = f"{ENV_PREFIX_MESHCORE}MOCK_MAX_INTERVAL"
    MOCK_CENTER_LAT = f"{ENV_PREFIX_MESHCORE}MOCK_CENTER_LAT"
    MOCK_CENTER_LON = f"{ENV_PREFIX_MESHCORE}MOCK_CENTER_LON"

    # === Database ===
    DB_PATH = f"{ENV_PREFIX_MESHCORE}DB_PATH"
    RETENTION_DAYS = f"{ENV_PREFIX_MESHCORE}RETENTION_DAYS"
    CLEANUP_INTERVAL_HOURS = f"{ENV_PREFIX_MESHCORE}CLEANUP_INTERVAL_HOURS"

    # === API ===
    API_HOST = f"{ENV_PREFIX_MESHCORE}API_HOST"
    API_PORT = f"{ENV_PREFIX_MESHCORE}API_PORT"
    API_TITLE = f"{ENV_PREFIX_MESHCORE}API_TITLE"
    API_VERSION = f"{ENV_PREFIX_MESHCORE}API_VERSION"
    API_BEARER_TOKEN = f"{ENV_PREFIX_MESHCORE}API_BEARER_TOKEN"

    # === Metrics ===
    METRICS_ENABLED = f"{ENV_PREFIX_MESHCORE}METRICS_ENABLED"

    # === Write Operations ===
    ENABLE_WRITE = f"{ENV_PREFIX_MESHCORE}ENABLE_WRITE"

    # === Logging ===
    LOG_LEVEL = f"{ENV_PREFIX_MESHCORE}LOG_LEVEL"
    LOG_FORMAT = f"{ENV_PREFIX_MESHCORE}LOG_FORMAT"

    # === Webhooks (now with MESHCORE_ prefix for consistency) ===
    WEBHOOK_MESSAGE_DIRECT = f"{ENV_PREFIX_MESHCORE}WEBHOOK_MESSAGE_DIRECT"
    WEBHOOK_MESSAGE_CHANNEL = f"{ENV_PREFIX_MESHCORE}WEBHOOK_MESSAGE_CHANNEL"
    WEBHOOK_ADVERTISEMENT = f"{ENV_PREFIX_MESHCORE}WEBHOOK_ADVERTISEMENT"
    WEBHOOK_TIMEOUT = f"{ENV_PREFIX_MESHCORE}WEBHOOK_TIMEOUT"
    WEBHOOK_RETRY_COUNT = f"{ENV_PREFIX_MESHCORE}WEBHOOK_RETRY_COUNT"
    WEBHOOK_MESSAGE_DIRECT_JSONPATH = f"{ENV_PREFIX_MESHCORE}WEBHOOK_MESSAGE_DIRECT_JSONPATH"
    WEBHOOK_MESSAGE_CHANNEL_JSONPATH = f"{ENV_PREFIX_MESHCORE}WEBHOOK_MESSAGE_CHANNEL_JSONPATH"
    WEBHOOK_ADVERTISEMENT_JSONPATH = f"{ENV_PREFIX_MESHCORE}WEBHOOK_ADVERTISEMENT_JSONPATH"

    # === Command Queue ===
    QUEUE_MAX_SIZE = f"{ENV_PREFIX_MESHCORE}QUEUE_MAX_SIZE"
    QUEUE_FULL_BEHAVIOR = f"{ENV_PREFIX_MESHCORE}QUEUE_FULL_BEHAVIOR"
    RATE_LIMIT_ENABLED = f"{ENV_PREFIX_MESHCORE}RATE_LIMIT_ENABLED"
    RATE_LIMIT_PER_SECOND = f"{ENV_PREFIX_MESHCORE}RATE_LIMIT_PER_SECOND"
    RATE_LIMIT_BURST = f"{ENV_PREFIX_MESHCORE}RATE_LIMIT_BURST"
    DEBOUNCE_ENABLED = f"{ENV_PREFIX_MESHCORE}DEBOUNCE_ENABLED"
    DEBOUNCE_WINDOW_SECONDS = f"{ENV_PREFIX_MESHCORE}DEBOUNCE_WINDOW_SECONDS"
    DEBOUNCE_CACHE_MAX_SIZE = f"{ENV_PREFIX_MESHCORE}DEBOUNCE_CACHE_MAX_SIZE"
    DEBOUNCE_COMMANDS = f"{ENV_PREFIX_MESHCORE}DEBOUNCE_COMMANDS"

    # === MCP Server ===
    MCP_HOST = f"{ENV_PREFIX_MCP}HOST"
    MCP_PORT = f"{ENV_PREFIX_MCP}PORT"
    MCP_API_BEARER_TOKEN = f"{ENV_PREFIX_MCP}API_BEARER_TOKEN"
    MCP_API_URL = f"{ENV_PREFIX_MCP}API_URL"
    MCP_API_TOKEN = f"{ENV_PREFIX_MCP}API_TOKEN"
    MCP_LOG_LEVEL = f"{ENV_PREFIX_MCP}LOG_LEVEL"

    # === Legacy Environment Variables (for backward compatibility) ===
    # These are the old names that we'll continue to support with fallback
    LEGACY_WEBHOOK_MESSAGE_DIRECT = "WEBHOOK_MESSAGE_DIRECT"
    LEGACY_WEBHOOK_MESSAGE_CHANNEL = "WEBHOOK_MESSAGE_CHANNEL"
    LEGACY_WEBHOOK_ADVERTISEMENT = "WEBHOOK_ADVERTISEMENT"
    LEGACY_WEBHOOK_TIMEOUT = "WEBHOOK_TIMEOUT"
    LEGACY_WEBHOOK_RETRY_COUNT = "WEBHOOK_RETRY_COUNT"
    LEGACY_WEBHOOK_MESSAGE_DIRECT_JSONPATH = "WEBHOOK_MESSAGE_DIRECT_JSONPATH"
    LEGACY_WEBHOOK_MESSAGE_CHANNEL_JSONPATH = "WEBHOOK_MESSAGE_CHANNEL_JSONPATH"
    LEGACY_WEBHOOK_ADVERTISEMENT_JSONPATH = "WEBHOOK_ADVERTISEMENT_JSONPATH"
    LEGACY_MCP_API_URL = f"{ENV_PREFIX_MESHCORE}API_URL"
    LEGACY_MCP_API_TOKEN = f"{ENV_PREFIX_MESHCORE}API_TOKEN"


def get_env_value(
    env_var: str,
    default: T,
    type_converter: type = str,
    fallback_env_var: Optional[str] = None,
) -> T:
    """
    Get a value from an environment variable with type conversion.

    Args:
        env_var: Primary environment variable name
        default: Default value if not found
        type_converter: Type to convert to (str, int, float, bool)
        fallback_env_var: Optional legacy/fallback environment variable name

    Returns:
        The environment value converted to the specified type, or the default
    """
    # Try primary env var first
    env_value = os.getenv(env_var)

    # If not found and fallback exists, try fallback
    if env_value is None and fallback_env_var:
        env_value = os.getenv(fallback_env_var)

    if env_value is not None:
        if type_converter == bool:
            return env_value.lower() in ("true", "1", "yes", "on")  # type: ignore
        return type_converter(env_value)

    return default


def get_config_value(
    cli_arg: Optional[Any],
    env_var: str,
    default: T,
    type_converter: type = str,
    fallback_env_var: Optional[str] = None,
) -> T:
    """
    Get a configuration value with priority: CLI > Environment > Default.

    This is the standard helper function used by all config classes to
    resolve configuration values with consistent priority.

    Args:
        cli_arg: CLI argument value (highest priority)
        env_var: Primary environment variable name
        default: Default value (lowest priority)
        type_converter: Type to convert to (str, int, float, bool)
        fallback_env_var: Optional legacy/fallback environment variable name

    Returns:
        The resolved configuration value
    """
    # CLI arguments take highest priority
    if cli_arg is not None:
        return cli_arg

    # Then try environment variables (primary, then fallback)
    return get_env_value(env_var, default, type_converter, fallback_env_var)


def get_bool_config_value(
    cli_flag: bool,
    env_var: str,
    default: bool,
    fallback_env_var: Optional[str] = None,
    invert_cli: bool = False,
) -> bool:
    """
    Get a boolean configuration value with special handling for flags.

    This handles the common pattern where CLI uses --no-feature flags
    that need to be inverted.

    Args:
        cli_flag: CLI flag value (e.g., args.no_rate_limit)
        env_var: Environment variable name
        default: Default value
        fallback_env_var: Optional legacy/fallback environment variable
        invert_cli: If True, invert the CLI flag value (for --no-* flags)

    Returns:
        The resolved boolean value
    """
    # If CLI flag was set (for --no-* flags, this means feature is disabled)
    if cli_flag:
        return not invert_cli if invert_cli else cli_flag

    # Otherwise check environment variable
    return get_env_value(env_var, default, bool, fallback_env_var)
