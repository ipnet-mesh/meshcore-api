"""Common constants used across MeshCore Sidekick."""

# Node types as delivered by MeshCore:
# 0: unknown, 1: cli (companion), 2: rep (repeater)
NODE_TYPE_MAP = {
    0: "unknown",
    1: "cli",
    2: "rep",
}


def node_type_name(value) -> str:
    """Return the canonical node type string for a value (int or str), or 'unknown'."""
    if value is None:
        return "unknown"
    try:
        return NODE_TYPE_MAP[int(value)]
    except (ValueError, TypeError, KeyError):
        pass

    if isinstance(value, str):
        key = value.strip().lower()
        for v in NODE_TYPE_MAP.values():
            if key == v:
                return v

    return "unknown"
