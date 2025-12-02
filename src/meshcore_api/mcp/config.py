"""MCP Configuration - redirects to meshcore_api.config.mcp module.

This file maintains backward compatibility for existing imports.
The MCPConfig class is now defined in meshcore_api.config.mcp.

Usage (both work):
    # New recommended import
    from meshcore_api.config import MCPConfig

    # Old import (still works for backward compatibility)
    from meshcore_api.mcp.config import MCPConfig
"""

# Re-export MCPConfig for backward compatibility
from meshcore_api.config.mcp import MCPConfig

__all__ = ["MCPConfig"]
