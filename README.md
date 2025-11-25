# MeshCore Sidekick

MeshCore companion application for event collection, persistence, and REST API access.

## Features

- Subscribe to all MeshCore events via Serial/BLE connection
- Persist events in SQLite database with configurable retention
- **Custom node metadata tags** with typed values (strings, numbers, booleans, coordinates)
- REST API for querying collected data and sending commands
- Mock MeshCore implementation for development without hardware
- Prometheus metrics for monitoring
- OpenAPI/Swagger documentation
- Docker deployment ready

## Quick Start

### Development (Mock Mode)

```bash
# Install dependencies
pip install -r requirements.txt

# Run with mock MeshCore
python -m meshcore_sidekick --use-mock --log-level DEBUG
```

### Production (Real Hardware)

```bash
# Run with real MeshCore device
python -m meshcore_sidekick \
    --serial-port /dev/ttyUSB0 \
    --serial-baud 115200 \
    --db-path /data/meshcore.db \
    --retention-days 90
```

### Docker

```bash
# Development with mock
docker-compose up --build

# Production with real hardware
docker-compose -f docker-compose.prod.yml up -d
```

## Configuration

Configuration priority: **CLI Arguments > Environment Variables > Defaults**

### CLI Arguments

```bash
python -m meshcore_sidekick --help
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
# Full report (all tables and statistics)
python -m meshcore_sidekick.query

# Summary statistics only
python -m meshcore_sidekick.query --summary

# Recent messages (last 20)
python -m meshcore_sidekick.query --messages 20

# Discovered nodes
python -m meshcore_sidekick.query --nodes 10

# Recent advertisements
python -m meshcore_sidekick.query --advertisements 10

# Telemetry data
python -m meshcore_sidekick.query --telemetry 5

# Trace paths
python -m meshcore_sidekick.query --traces 5

# Activity in last 6 hours
python -m meshcore_sidekick.query --activity 6

# Custom database location
python -m meshcore_sidekick.query --db-path /data/meshcore.db
```

## Node Tags

Add custom metadata to nodes beyond what's captured in MeshCore events. Tags support typed values for validation and efficient querying.

### Tag Types

- **String**: Friendly names, device manufacturers, models, notes
- **Number**: Battery counts, firmware versions, hop counts
- **Boolean**: Feature flags (is_gateway, is_active, etc.)
- **Coordinate**: GPS locations with latitude/longitude validation

### Managing Tags via API

```bash
# Set a friendly name (string tag) - key is in URL, not needed in body
curl -X PUT http://localhost:8000/api/v1/nodes/{public_key}/tags/friendly_name \
  -H "Content-Type: application/json" \
  -d '{"value_type": "string", "value": "Router-1"}'

# Set GPS location (coordinate tag)
curl -X PUT http://localhost:8000/api/v1/nodes/{public_key}/tags/location \
  -H "Content-Type: application/json" \
  -d '{"value_type": "coordinate", "value": {"latitude": 45.52, "longitude": -122.68}}'

# Bulk update multiple tags at once
curl -X POST http://localhost:8000/api/v1/nodes/{public_key}/tags/bulk \
  -H "Content-Type: application/json" \
  -d '{
    "tags": [
      {"key": "manufacturer", "value_type": "string", "value": "Meshtastic"},
      {"key": "battery_count", "value_type": "number", "value": 2},
      {"key": "is_gateway", "value_type": "boolean", "value": true}
    ]
  }'

# Get all tags for a node
curl http://localhost:8000/api/v1/nodes/{public_key}/tags

# Query tags across all nodes
curl "http://localhost:8000/api/v1/tags?key=manufacturer"

# Get all unique tag keys
curl http://localhost:8000/api/v1/tags/keys

# Delete a tag
curl -X DELETE http://localhost:8000/api/v1/nodes/{public_key}/tags/battery_count
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
python -m meshcore_sidekick.query --nodes 10
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

## Prometheus Metrics

Metrics available at: http://localhost:8000/metrics

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest

# Format code
black src/ tests/

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

## License

See LICENSE file.
