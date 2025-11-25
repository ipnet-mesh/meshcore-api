# Agent Rules

* You MUST use Python (version in `.python-version` file)
* You MUST create and activate a Python virtual environment in the `venv` directory
  - `python -m venv .venv`
- You MUST always activate the virtual environment before running any commands
  - `source .venv/bin/activate`
* You MUST install all project dependecies using `pip install -r ".[dev]"` command`

## Useful Commands:

- Start application: `python -m meshcore_sidekick`
- Query tool: `python -m meshcore_sidekick.query`

## Database Schema

The application stores MeshCore event data in SQLite with the following key tables:

- **nodes** - Network nodes with public keys and metadata
- **node_tags** - Custom metadata tags for nodes (friendly names, locations, device info, etc.)
- **messages** - Direct and channel messages
- **advertisements** - Node advertisements
- **telemetry** - Sensor data from nodes
- **trace_paths** - Network trace path results
- **events_log** - Raw event log

## Node Tags Feature

The application supports custom metadata tags for nodes with typed values:

- **String tags**: `friendly_name`, `manufacturer`, `model`, etc.
- **Number tags**: `battery_count`, `firmware_version_number`, etc.
- **Boolean tags**: `is_gateway`, `is_active`, etc.
- **Coordinate tags**: `location` with lat/long validation

Tags can be managed via:
- REST API: `/api/v1/nodes/{public_key}/tags` endpoints
- Bulk updates: `/api/v1/nodes/{public_key}/tags/bulk`
- Query across nodes: `/api/v1/tags`

See API documentation at `/docs` for full details.
