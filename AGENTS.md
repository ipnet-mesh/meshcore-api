# Agent Rules

* You MUST use Python (version in `.python-version` file)
* You MUST create and activate a Python virtual environment in the `venv` directory
  - `python -m venv .venv`
- You MUST always activate the virtual environment before running any commands
  - `source .venv/bin/activate`
* You MUST install all project dependecies using `pip install -e ".[dev]"` command`

## Useful Commands:

The application provides a Click-based CLI with the following commands:

- Start server: `meshcore-api server [OPTIONS]` or `python -m meshcore_api server`
- Query database: `meshcore-api query [OPTIONS]` or `python -m meshcore_api query`
- Show help: `meshcore-api --help`

### Server Command

Start the MeshCore API server:
```bash
meshcore-api server --use-mock --api-port 8000
```

Common options:
- `--serial-port`: Serial port for MeshCore device
- `--use-mock`: Use mock MeshCore for testing
- `--api-host`, `--api-port`: Configure API server
- `--log-level`: Set logging level (DEBUG, INFO, WARNING, ERROR)
- `--db-path`: Path to SQLite database

### Query Command

Query the database for captured MeshCore data:
```bash
meshcore-api query --summary
meshcore-api query --nodes 10
meshcore-api query --messages 20
```

Common options:
- `--summary`: Show summary statistics only
- `--nodes N`: Show N discovered nodes
- `--messages N`: Show N recent messages
- `--activity N`: Show activity timeline for last N hours

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
