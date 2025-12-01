"""HTTP client for MeshCore API."""

import logging
from typing import Any, Optional

import httpx

from .state import state

logger = logging.getLogger(__name__)

# Default timeout for API requests (in seconds)
DEFAULT_TIMEOUT = 30.0


class APIError(Exception):
    """Exception raised for API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, detail: Any = None):
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)


def _check_configured() -> Optional[str]:
    """Check if the API is configured and return error message if not."""
    if not state.is_configured:
        return (
            "Error: API not configured. "
            "Set MESHCORE_API_URL environment variable or use --api-url argument."
        )
    return None


def _build_url(path: str) -> str:
    """Build full URL from base URL and path."""
    base = state.api_url.rstrip("/")
    path = path.lstrip("/")
    return f"{base}/{path}"


async def api_get(
    path: str, params: Optional[dict] = None, timeout: float = DEFAULT_TIMEOUT
) -> dict:
    """
    Make a GET request to the MeshCore API.

    Args:
        path: API path (e.g., "/api/v1/messages")
        params: Query parameters
        timeout: Request timeout in seconds

    Returns:
        JSON response as dict

    Raises:
        APIError: If the request fails
    """
    error = _check_configured()
    if error:
        logger.error(f"API not configured: {error}")
        raise APIError(error)

    url = _build_url(path)
    headers = state.get_auth_headers()

    # Filter out None values from params
    if params:
        params = {k: v for k, v in params.items() if v is not None}

    logger.debug(f"API GET: {url}")

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, params=params, headers=headers)

            if response.status_code == 422:
                detail = response.json().get("detail", [])
                logger.error(f"Validation error: {detail}")
                raise APIError(f"Validation error: {detail}", status_code=422, detail=detail)

            response.raise_for_status()
            return response.json()

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
        raise APIError(
            f"HTTP error {e.response.status_code}: {e.response.text}",
            status_code=e.response.status_code,
        )
    except httpx.RequestError as e:
        logger.error(f"Request error: {e}")
        raise APIError(f"Request failed: {e}")


async def api_post(
    path: str, json_data: Optional[dict] = None, timeout: float = DEFAULT_TIMEOUT
) -> dict:
    """
    Make a POST request to the MeshCore API.

    Args:
        path: API path (e.g., "/api/v1/commands/send_message")
        json_data: JSON body data
        timeout: Request timeout in seconds

    Returns:
        JSON response as dict

    Raises:
        APIError: If the request fails
    """
    error = _check_configured()
    if error:
        logger.error(f"API not configured: {error}")
        raise APIError(error)

    url = _build_url(path)
    headers = state.get_auth_headers()

    logger.debug(f"API POST: {url}")

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=json_data or {}, headers=headers)

            if response.status_code == 422:
                detail = response.json().get("detail", [])
                logger.error(f"Validation error: {detail}")
                raise APIError(f"Validation error: {detail}", status_code=422, detail=detail)

            response.raise_for_status()
            return response.json()

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
        raise APIError(
            f"HTTP error {e.response.status_code}: {e.response.text}",
            status_code=e.response.status_code,
        )
    except httpx.RequestError as e:
        logger.error(f"Request error: {e}")
        raise APIError(f"Request failed: {e}")
