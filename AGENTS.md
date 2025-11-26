# Agent Rules

* You MUST use Python (version in `.python-version` file)
* You MUST activate a Python virtual environment in the `venv` directory or create one if it does not exist:
  - `ls ./venv` to check if it exists
  - `python -m venv .venv` to create it
- You MUST always activate the virtual environment before running any commands
  - `source .venv/bin/activate`
* You MUST install all project dependecies using `pip install -e ".[dev]"` command`

## Useful Commands:

The application provides a Click-based CLI with the following commands:

- Start server: `meshcore_api server [OPTIONS]` or `python -m meshcore_api server`
- Query database: `meshcore_api query [OPTIONS]` or `python -m meshcore_api query`
- Import tags: `meshcore_api tag JSON_FILE [OPTIONS]` or `python -m meshcore_api tag JSON_FILE`
- Show help: `meshcore_api --help`

### Server Command

Start the MeshCore API server:
```bash
meshcore_api server --use-mock --api-port 8000
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
meshcore_api query --summary
meshcore_api query --nodes 10
meshcore_api query --messages 20
```

Common options:
- `--summary`: Show summary statistics only
- `--nodes N`: Show N discovered nodes
- `--messages N`: Show N recent messages
- `--signals N`: Show N recent signal measurements
- `--activity N`: Show activity timeline for last N hours

### Tag Command

Import node tags from a JSON file for bulk tag management:
```bash
meshcore_api tag node_tags.json
meshcore_api tag node_tags.json --dry-run
meshcore_api tag node_tags.json --verbose
```

Common options:
- `--db-path PATH`: Path to SQLite database
- `--dry-run`: Preview changes without applying them
- `--verbose`: Show detailed progress for each node
- `--continue-on-error`: Continue processing even if some nodes fail
- `--validate-only`: Only validate the JSON file without applying changes

JSON file format:
```json
{
  "full_64_char_public_key": {
    "friendly_name": {"value_type": "string", "value": "Gateway Node"},
    "location": {
      "value_type": "coordinate",
      "value": {"latitude": 37.7749, "longitude": -122.4194}
    },
    "is_gateway": {"value_type": "boolean", "value": true},
    "battery_count": {"value_type": "number", "value": 4}
  }
}
```

Supported value types:
- `string`: Text values
- `number`: Numeric values (int or float)
- `boolean`: True/false values
- `coordinate`: Geographic coordinates with latitude and longitude

## Database Schema

The application stores MeshCore event data in SQLite with the following key tables:

- **nodes** - Network nodes with public keys and metadata
- **node_tags** - Custom metadata tags for nodes (friendly names, locations, device info, etc.)
- **messages** - Direct and channel messages
- **advertisements** - Node advertisements
- **telemetry** - Sensor data from nodes
- **trace_paths** - Network trace path results
- **signal_measurements** - SNR (signal strength) measurements between nodes from messages and trace paths
- **events_log** - Raw event log

## Signal Measurements Feature

The application automatically captures and stores SNR (Signal-to-Noise Ratio) measurements from MeshCore events:

### Event Sources
- **CONTACT_MSG_RECV** - Direct messages with SNR between sender and receiver
- **CHANNEL_MSG_RECV** - Channel broadcast messages with SNR
- **TRACE_DATA** - Multi-hop trace paths with SNR for each hop

### Data Captured
Each signal measurement includes:
- **Source/Destination**: Full 64-character node public keys
- **SNR Value**: Signal strength in dB (decibels)
- **Measurement Type**: `message` or `trace_hop`
- **Timestamp**: When the measurement was taken
- **Reference**: Link back to the original message or trace path

### Public Key Resolution
- **Database Storage**: Only full 64-character public keys are stored in the database
- **Event Processing**: Abbreviated prefixes from MeshCore events (2-12 chars) are resolved before storage
- **Resolution Method**: Uses indexed prefix lookups on `Node` table for performance
- **Resolution Required**: Signal measurements are only created when BOTH endpoints can be resolved to known nodes
- **Preserved Data**: Unresolved trace path data is preserved in trace_paths table (path_hashes JSON)
- **API Layer**: Prefix queries are resolved on-the-fly when filtering measurements

### API Access
Query signal measurements via REST API:
- **Endpoint**: `/api/v1/signal-measurements`
- **Filter by**: source, destination, SNR range, measurement type, date range
- **Pagination**: Standard limit/offset support

Example queries:
```bash
# Get measurements from a specific node
curl "http://localhost:8000/api/v1/signal-measurements?source_prefix=b3"

# Find weak links (SNR < 10 dB)
curl "http://localhost:8000/api/v1/signal-measurements?max_snr=10"

# Analyze trace path hop quality
curl "http://localhost:8000/api/v1/signal-measurements?measurement_type=trace_hop&min_snr=20"
```

See API documentation at `/docs` for full query options.

## Node Tags Feature

The application supports custom metadata tags for nodes with typed values:

- **String tags**: `friendly_name`, `manufacturer`, `model`, etc.
- **Number tags**: `battery_count`, `firmware_version_number`, etc.
- **Boolean tags**: `is_gateway`, `is_active`, etc.
- **Coordinate tags**: `location` with lat/long validation

Tags can be managed via:
- **CLI**: `meshcore_api tag` command for bulk imports from JSON files
- **REST API**: `/api/v1/nodes/{public_key}/tags` endpoints
- **Bulk updates**: `/api/v1/nodes/{public_key}/tags/bulk`
- **Query across nodes**: `/api/v1/tags`

See API documentation at `/docs` and `meshcore_api tag --help` for full details.
