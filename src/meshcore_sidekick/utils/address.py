"""Public address utility functions for MeshCore nodes."""

import re


def is_valid_public_key(key: str) -> bool:
    """
    Check if a string is a valid hexadecimal public key.

    Args:
        key: Public key string to validate

    Returns:
        True if valid hex string, False otherwise
    """
    if not key:
        return False
    return bool(re.match(r'^[0-9a-fA-F]+$', key))


def normalize_public_key(key: str) -> str:
    """
    Normalize public key to lowercase hex.

    Args:
        key: Public key string

    Returns:
        Lowercase hex string

    Raises:
        ValueError: If key is not valid hex
    """
    if not is_valid_public_key(key):
        raise ValueError(f"Invalid public key: {key}")
    return key.lower()


def extract_prefix(key: str, length: int = 2) -> str:
    """
    Extract prefix of specified length from public key.

    Args:
        key: Public key string
        length: Number of characters to extract (default 2)

    Returns:
        Prefix string of specified length

    Raises:
        ValueError: If key is too short or invalid
    """
    normalized = normalize_public_key(key)
    if len(normalized) < length:
        raise ValueError(f"Public key too short for prefix length {length}")
    return normalized[:length]


def matches_prefix(full_key: str, prefix: str) -> bool:
    """
    Check if a full public key matches a given prefix.

    Args:
        full_key: Full public key to check
        prefix: Prefix to match against

    Returns:
        True if full_key starts with prefix (case-insensitive)
    """
    if not is_valid_public_key(full_key) or not is_valid_public_key(prefix):
        return False
    return normalize_public_key(full_key).startswith(normalize_public_key(prefix))
