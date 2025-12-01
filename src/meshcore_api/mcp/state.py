"""Server state management for MeshCore MCP Server."""

from typing import Optional


class ServerState:
    """Maintains global server state for API connectivity."""

    # API configuration
    api_url: Optional[str] = None
    api_token: Optional[str] = None

    def configure(self, api_url: Optional[str] = None, api_token: Optional[str] = None):
        """
        Configure the API connection settings.

        Args:
            api_url: Base URL for the MeshCore API (e.g., "http://localhost:8080")
            api_token: Bearer token for authentication (optional if API is public)
        """
        self.api_url = api_url
        self.api_token = api_token

    @property
    def is_configured(self) -> bool:
        """Check if the API URL is configured."""
        return self.api_url is not None

    def get_auth_headers(self) -> dict:
        """Get authentication headers for API requests."""
        if self.api_token:
            return {"Authorization": f"Bearer {self.api_token}"}
        return {}


# Global state instance
state = ServerState()
