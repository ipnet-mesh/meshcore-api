# MeshCore API

MeshCore companion application for event collection, persistence, and REST API access.

## Features

- Subscribe to all MeshCore events via Serial/BLE connection
- Persist events in SQLite database with configurable retention
- Custom node metadata tags with typed values (strings, numbers, booleans, coordinates)
- REST API for querying collected data and sending commands
- Mock MeshCore implementation for development without hardware
- Prometheus metrics for monitoring
- OpenAPI/Swagger documentation
- Docker deployment ready

## Quick Start

### Development (Mock Mode)

```bash
# Install dependencies (editable, with dev extras if available)
pip install -e ".[dev]"

# Run with mock MeshCore
meshcore_api server --use-mock --log-level DEBUG
```

### Production (Real Hardware)

```bash
# Run with real MeshCore device
meshcore_api server \
    --serial-port /dev/ttyUSB0 \
    --serial-baud 115200 \
    --db-path /data/meshcore.db \
    --retention-days 90
```

## Configuration

### CLI Arguments

```bash
meshcore_api --help
```

### Environment Variables

```bash
MESHCORE_SERIAL_PORT=/dev/ttyUSB0
MESHCORE_USE_MOCK=true
MESHCORE_DB_PATH=/data/meshcore.db
MESHCORE_RETENTION_DAYS=30
MESHCORE_API_PORT=8000
MESHCORE_LOG_LEVEL=INFO
```

See full configuration options in documentation.

## Querying the Database

View captured data with the query tool:

```bash
# Full report (all tracked tables)
meshcore_api query

# Summary only
meshcore_api query --summary

# Recent messages (last 20)
meshcore_api query --messages 20

# Discovered nodes
meshcore_api query --nodes 10

# Recent advertisements
meshcore_api query --advertisements 10

# Telemetry data
meshcore_api query --telemetry 5

# Trace paths
meshcore_api query --traces 5

# Custom database location
meshcore_api query --db-path /data/meshcore.db
```

### Docker

Build and run with Docker/Compose:

```bash
# Build image (uses BuildKit caching for faster rebuilds)
docker build -t meshcore-api:local .

# Build with explicit BuildKit (if not default)
DOCKER_BUILDKIT=1 docker build -t meshcore-api:local .

# Run (mock mode by default)
docker run --rm -p 8080:8080 -v $(pwd)/data:/data meshcore-api:local

# Or with docker-compose
docker compose up --build
```

**Note:** The Dockerfile uses BuildKit cache mounts to speed up pip installations. BuildKit is enabled by default in Docker 20.10+. If using an older version, set `DOCKER_BUILDKIT=1`.

## API Overview

OpenAPI docs are available at `/docs` when the server is running. Core endpoints:

- `GET /api/v1/messages` — message history
- `GET /api/v1/advertisements` — node adverts
- `GET /api/v1/telemetry` — telemetry data
- `GET /api/v1/trace_paths` — trace results (meshcore trace data)
- `GET /api/v1/nodes` — list all nodes
- `GET /api/v1/nodes/{prefix}` — search nodes by public key prefix (2-64 chars)
- `GET /api/v1/nodes/{public_key}/messages` — messages for a node (requires full 64-char key)
- `GET /api/v1/nodes/{public_key}/telemetry` — telemetry for a node (requires full 64-char key)
- `PUT/POST /api/v1/nodes/{public_key}/tags` — node tags (requires full 64-char key)
- `POST /api/v1/commands/*` — send messages, channel messages, adverts, trace, telemetry requests
- `GET /api/v1/health` — health/status

### Public Key Requirements

**Most endpoints require full 64-character hexadecimal public keys.** If you only have a partial key or prefix:

1. **Resolve the prefix** using `GET /api/v1/nodes/{prefix}` (returns all matching nodes)
2. **Use the full key** from the response for subsequent operations

Example workflow:
```bash
# Step 1: Search by prefix
curl http://localhost:8000/api/v1/nodes/abc123
# Returns: [{"public_key": "abc123...full64chars...", ...}, ...]

# Step 2: Use full key for operations
curl http://localhost:8000/api/v1/nodes/abc123...full64chars.../messages
curl http://localhost:8000/api/v1/nodes/abc123...full64chars.../tags
```

## Node Tags

Add custom metadata to nodes beyond what's captured in MeshCore events. Tags support typed values for validation and efficient querying.

### Tag Types

- **String**: Friendly names, device manufacturers, models, notes
- **Number**: Battery counts, firmware versions, hop counts
- **Boolean**: Feature flags (is_gateway, is_active, etc.)
- **Coordinate**: GPS locations with latitude/longitude validation

### Managing Tags via API

**Note:** All tag operations require the **full 64-character public key**. Use `GET /api/v1/nodes/{prefix}` to resolve partial keys first.

```bash
# Set a friendly name (string tag) - key is in URL, not needed in body
curl -X PUT http://localhost:8000/api/v1/nodes/abc123...full64chars.../tags/friendly_name \
  -H "Content-Type: application/json" \
  -d '{"value_type": "string", "value": "Router-1"}'

# Set GPS location (coordinate tag)
curl -X PUT http://localhost:8000/api/v1/nodes/abc123...full64chars.../tags/location \
  -H "Content-Type: application/json" \
  -d '{"value_type": "coordinate", "value": {"latitude": 45.52, "longitude": -122.68}}'

# Bulk update multiple tags at once
curl -X POST http://localhost:8000/api/v1/nodes/abc123...full64chars.../tags/bulk \
  -H "Content-Type: application/json" \
  -d '{
    "tags": [
      {"key": "manufacturer", "value_type": "string", "value": "Meshtastic"},
      {"key": "battery_count", "value_type": "number", "value": 2},
      {"key": "is_gateway", "value_type": "boolean", "value": true}
    ]
  }'

# Get all tags for a node
curl http://localhost:8000/api/v1/nodes/abc123...full64chars.../tags

# Query tags across all nodes (filter by key, value_type, or node_public_key)
curl "http://localhost:8000/api/v1/tags?key=manufacturer"
curl "http://localhost:8000/api/v1/tags?node_public_key=abc123...full64chars..."

# Get all unique tag keys
curl http://localhost:8000/api/v1/tags/keys

# Delete a tag
curl -X DELETE http://localhost:8000/api/v1/nodes/abc123...full64chars.../tags/battery_count
```

### Querying Nodes by Tags

Find nodes matching specific tag criteria:

```bash
# Query all gateway nodes
curl "http://localhost:8000/api/v1/nodes/by-tag?tag_key=is_gateway&tag_value=true"

# Query all nodes from specific manufacturer
curl "http://localhost:8000/api/v1/nodes/by-tag?tag_key=manufacturer&tag_value=Meshtastic"

# Query all nodes with a specific hop count
curl "http://localhost:8000/api/v1/nodes/by-tag?tag_key=hop_count&tag_value=3"

# Query all nodes that have a location tag (any value)
curl "http://localhost:8000/api/v1/nodes/by-tag?tag_key=location&tag_value=EXISTS"

# With pagination and sorting
curl "http://localhost:8000/api/v1/nodes/by-tag?tag_key=is_gateway&tag_value=true&limit=50&offset=0&sort_by=last_seen&order=desc"
```

The endpoint automatically detects value types:
- `true`/`false` (case-insensitive) → queries boolean tags
- Numeric values → queries number tags
- Other strings → queries string tags
- `EXISTS` → finds any node with that tag key

### Viewing Tags in Query Tool

Tags are automatically displayed when viewing nodes:

```bash
meshcore_api query --nodes 10
```

Output includes tags for each node:
```
  Node: Router-1
    Public Key: 01abcdef...
    Type: Repeater
    First Seen: 2025-11-25 12:00:00
    Last Seen: 2025-11-25 18:00:00
    Tags:
      friendly_name: Router-1
      is_gateway: True
      location: (45.52, -122.68)
      manufacturer: Meshtastic
```

## API Documentation

Once running, access interactive API docs at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI Schema: http://localhost:8000/openapi.json

## Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest
```

## License

See LICENSE file.
