# Agent Rules

* You MUST use Python (version in `.python-version` file)
* You MUST activate a Python virtual environment in the `venv` directory or create one if it does not exist:
  - `ls ./venv` to check if it exists
  - `python -m venv .venv` to create it
- You MUST always activate the virtual environment before running any commands
  - `source .venv/bin/activate`
* You MUST install all project dependencies using `pip install -e ".[dev]"` command`
* Before commiting:
  - Run tests with `pytest` and fix any issues

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
- `--api-bearer-token`: Bearer token for API authentication (optional)
- `--log-level`: Set logging level (DEBUG, INFO, WARNING, ERROR)
- `--db-path`: Path to SQLite database
- `--queue-max-size`: Maximum command queue size (default: 100)
- `--rate-limit-per-second`: Commands per second rate limit (default: 0.02 = 1 per 50 seconds for LoRa duty cycle)
- `--no-rate-limit`: Disable rate limiting
- `--debounce-window`: Debounce window in seconds (default: 60.0)
- `--no-debounce`: Disable debouncing

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
- **events_log** - Raw event log

**For complete event payload schemas, see [SCHEMAS.md](SCHEMAS.md)**

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

## Webhooks Feature

The application can send HTTP POST notifications to external URLs when specific MeshCore events occur.

### Supported Events

- **Direct/Contact Messages** (`CONTACT_MSG_RECV`)
- **Channel Messages** (`CHANNEL_MSG_RECV`)
- **Advertisements** (`ADVERTISEMENT`, `NEW_ADVERT`)

**For detailed event payload schemas, see [SCHEMAS.md](SCHEMAS.md)**

### Configuration

Configure webhooks via environment variables or CLI arguments:

**Environment Variables:**
```bash
WEBHOOK_MESSAGE_DIRECT=https://example.com/webhooks/direct
WEBHOOK_MESSAGE_CHANNEL=https://example.com/webhooks/channel
WEBHOOK_ADVERTISEMENT=https://example.com/webhooks/adverts
WEBHOOK_TIMEOUT=10              # HTTP timeout in seconds (default: 5)
WEBHOOK_RETRY_COUNT=5           # Number of retry attempts (default: 3)

# JSONPath expressions to filter webhook payloads (default: "$" for full payload)
WEBHOOK_MESSAGE_DIRECT_JSONPATH="$.data.text"
WEBHOOK_MESSAGE_CHANNEL_JSONPATH="$.data.text"
WEBHOOK_ADVERTISEMENT_JSONPATH="$"
```

**CLI Arguments:**
```bash
meshcore_api server \
  --use-mock \
  --webhook-message-direct https://example.com/webhooks/direct \
  --webhook-message-channel https://example.com/webhooks/channel \
  --webhook-advertisement https://example.com/webhooks/adverts \
  --webhook-timeout 10 \
  --webhook-retry-count 5 \
  --webhook-message-direct-jsonpath "$.data.text" \
  --webhook-message-channel-jsonpath "$.data.text" \
  --webhook-advertisement-jsonpath "$"
```

### Webhook Payload

All webhooks send HTTP POST with JSON:
```json
{
  "event_type": "CHANNEL_MSG_RECV",
  "timestamp": "2025-11-28T19:41:38.748379Z",
  "data": {
    "channel_idx": 4,
    "text": "Hello from the mesh!",
    "SNR": 8.5,
    ...
  }
}
```

### JSONPath Payload Filtering

Use JSONPath expressions to filter which portion of the webhook payload to send. This is useful for integrating with AI agents (like Pydantic AI) that expect simple text input.

**Examples:**
- Send only message text: `$.data.text` → `"Hello from the mesh!"` (plain text)
- Send only data object: `$.data` → `{"channel_idx": 4, "text": "...", ...}` (JSON)
- Send entire payload: `$` → Full payload with event_type, timestamp, and data (default)

**Behavior:**
- Primitive values (string/number/boolean) sent as plain text or JSON value
- Objects/Arrays sent as JSON
- Invalid expressions or empty results fall back to full payload
- Errors logged without affecting event processing

### Testing Webhooks

Use the included test receiver:
```bash
# Start webhook receiver
python test_webhooks.py

# Start API with webhooks
meshcore_api server \
  --use-mock \
  --webhook-message-direct http://localhost:9000/webhooks/direct \
  --webhook-message-channel http://localhost:9000/webhooks/channel \
  --webhook-advertisement http://localhost:9000/webhooks/advertisement
```

Features:
- **Non-blocking**: Webhook failures don't affect event processing
- **Retry logic**: Exponential backoff (2s, 4s, 8s delays)
- **Logging**: Debug/warning/error logs for all webhook attempts

## Bearer Authentication

The application supports optional Bearer token authentication for the REST API.

### Configuration

When a bearer token is configured, all API endpoints (except `/docs`, `/redoc`, `/openapi.json`, and `/metrics`) require authentication.

**Environment Variable:**
```bash
export MESHCORE_API_BEARER_TOKEN="your-secret-token-here"
meshcore_api server --use-mock
```

**CLI Argument:**
```bash
meshcore_api server --use-mock --api-bearer-token "your-secret-token-here"
```

**Priority:** CLI arguments > Environment variables > Not configured (public API)

### Making Authenticated Requests

When authentication is enabled, include the Bearer token in the `Authorization` header:

```bash
# Health check
curl -H "Authorization: Bearer your-secret-token-here" \
  http://localhost:8000/api/v1/health

# Get nodes
curl -H "Authorization: Bearer your-secret-token-here" \
  http://localhost:8000/api/v1/nodes

# Set a node tag
curl -X PUT \
  -H "Authorization: Bearer your-secret-token-here" \
  -H "Content-Type: application/json" \
  -d '{"value_type": "string", "value": "Gateway Node"}' \
  http://localhost:8000/api/v1/nodes/{public_key}/tags/friendly_name
```

### Public Endpoints

These endpoints are always accessible without authentication:
- `/docs` - Swagger UI documentation
- `/redoc` - ReDoc documentation
- `/openapi.json` - OpenAPI schema
- `/metrics` - Prometheus metrics endpoint

### Security Notes

- Store bearer tokens securely (environment variables, secrets management)
- Use HTTPS in production to protect tokens in transit
- Rotate tokens periodically
- Never commit tokens to version control

## API Rate Limiting & Command Queue

The application includes a command queue system with rate limiting and debouncing to prevent network flooding and abuse.

### Features

- **Queue Management**: All outbound commands are queued and processed sequentially
- **Rate Limiting**: Token bucket algorithm controls command throughput
- **Debouncing**: Prevents duplicate commands within a time window
- **Configurable**: All limits adjustable via environment variables or CLI arguments

### Configuration

**Environment Variables:**
```bash
# Queue Configuration
export MESHCORE_QUEUE_MAX_SIZE=100              # Max queued commands (default: 100)
export MESHCORE_QUEUE_FULL_BEHAVIOR="reject"    # "reject" or "drop_oldest" (default: reject)

# Rate Limiting
export MESHCORE_RATE_LIMIT_ENABLED=true         # Enable rate limiting (default: true)
export MESHCORE_RATE_LIMIT_PER_SECOND=0.02      # Commands per second (default: 0.02 = 1 per 50 seconds for LoRa duty cycle)
export MESHCORE_RATE_LIMIT_BURST=2              # Max burst size (default: 2)

# Debouncing
export MESHCORE_DEBOUNCE_ENABLED=true                      # Enable debouncing (default: true)
export MESHCORE_DEBOUNCE_WINDOW_SECONDS=60.0               # Time window for duplicates (default: 60s)
export MESHCORE_DEBOUNCE_CACHE_MAX_SIZE=1000               # Max cache entries (default: 1000)
export MESHCORE_DEBOUNCE_COMMANDS="send_message,send_channel_message,send_advert"  # Commands to debounce
```

**CLI Arguments:**
```bash
meshcore_api server \
  --use-mock \
  --queue-max-size 100 \
  --queue-full-behavior reject \
  --rate-limit-per-second 0.02 \
  --rate-limit-burst 2 \
  --debounce-window 60.0 \
  --debounce-cache-size 1000 \
  --debounce-commands "send_message,send_channel_message,send_advert"
```

**Priority:** CLI arguments > Environment variables > Defaults

### Disabling Features

Disable rate limiting or debouncing if needed:

```bash
# Disable rate limiting
meshcore_api server --use-mock --no-rate-limit

# Disable debouncing
meshcore_api server --use-mock --no-debounce

# Disable both
export MESHCORE_RATE_LIMIT_ENABLED=false
export MESHCORE_DEBOUNCE_ENABLED=false
meshcore_api server --use-mock
```

### How It Works

#### Queue Management

All outbound commands (messages, advertisements, pings, etc.) are added to an asynchronous FIFO queue. **API requests return immediately after queuing** - they do NOT wait for command execution.

1. **Enqueue**: API endpoint adds command to queue and returns immediately
2. **Background Worker**: Processes commands sequentially
3. **Debounce Check**: Duplicate commands are merged
4. **Rate Limit**: Worker waits for rate limit token before executing
5. **Execute**: Command sent to MeshCore device

#### Rate Limiting (Token Bucket)

The rate limiter uses a token bucket algorithm:

- **Rate**: Tokens added per second (average rate)
- **Burst**: Maximum tokens available (burst capacity)
- **Behavior**: Commands consume 1 token; if no tokens available, command waits in queue

**Example (default LoRa settings):**
- Rate: 0.02 commands/second (1 per 50 seconds)
- Burst: 2 tokens
- Result: Can send 2 commands instantly, then ~1 per 50 seconds sustained (respects LoRa duty cycle)

#### Debouncing

Prevents duplicate commands within a time window:

- **Hash-Based**: Commands hashed by type + parameters (excludes timestamp)
- **Time Window**: Duplicates within window are merged
- **Cache**: Recent command hashes stored with TTL
- **Result Sharing**: Duplicate requests receive the same result

**Debounced Commands (default):**
- `send_message` - Same message to same destination
- `send_channel_message` - Same broadcast text
- `send_advert` - Advertisement broadcasts

**Not Debounced:**
- `send_trace_path` - Path discovery results change over time
- `ping` - Status may change frequently
- `send_telemetry_request` - Telemetry changes frequently

### API Response Format

All command endpoints now return queue information:

```json
{
  "success": true,
  "message": "Command queued successfully",
  "queue_info": {
    "position": 3,
    "estimated_wait_seconds": 1.5,
    "queue_size": 15,
    "debounced": false
  }
}
```

**Debounced Command Response:**
```json
{
  "success": true,
  "message": "Command already pending (debounced)",
  "queue_info": {
    "position": 1,
    "estimated_wait_seconds": 0.5,
    "queue_size": 10,
    "debounced": true,
    "original_request_time": "2025-11-28T19:30:00Z"
  }
}
```

### Error Handling

#### Queue Full (HTTP 429 Too Many Requests)

If the queue is full and behavior is set to `reject`:

```json
{
  "error": "Command queue is full. Please try again later."
}
```

**Solution:** Wait and retry, or increase `queue_max_size`

### Monitoring

Check queue stats via the health endpoint:

```bash
curl http://localhost:8000/api/v1/health
```

Response includes queue statistics:

```json
{
  "status": "healthy",
  "meshcore_connected": true,
  "database_connected": true,
  "uptime_seconds": 3600,
  "events_processed": 1234,
  "queue": {
    "queue_size": 5,
    "max_queue_size": 100,
    "rate_limit_tokens_available": 3.5,
    "debounce_cache_size": 42,
    "commands_processed_total": 567,
    "commands_dropped_total": 0,
    "commands_debounced_total": 23
  }
}
```

### Performance Impact

- **Queue Overhead**: < 1ms per command (in-memory queue)
- **Debounce Hash**: O(1) dictionary lookup
- **Token Bucket**: O(1) token check
- **Memory Usage**: ~100KB queue + ~1MB debounce cache

### Best Practices

1. **Production Settings (LoRa Networks)**:
   - Enable both rate limiting and debouncing
   - Use default rate limits (0.02 commands/sec = 1 per 50 seconds) to respect LoRa duty cycle
   - Monitor queue stats regularly
   - Use longer debounce windows (60+ seconds) to prevent duplicate transmissions

2. **Development/Testing**:
   - Disable rate limiting for faster testing: `--no-rate-limit`
   - Disable debouncing to test all commands: `--no-debounce`
   - Increase queue size: `--queue-max-size 500`

3. **High-Traffic Scenarios (Non-LoRa)**:
   - If NOT using LoRa, increase rate: `--rate-limit-per-second 2.0`
   - Increase burst size: `--rate-limit-burst 10`
   - Use `drop_oldest` behavior: `--queue-full-behavior drop_oldest`

4. **Low-Latency Requirements (Non-LoRa)**:
   - Reduce debounce window: `--debounce-window 1.0`
   - Increase rate limit if hardware allows
   - Consider disabling debouncing: `--no-debounce`

## REST API - Public Key Requirements

**IMPORTANT:** Most REST API endpoints require **full 64-character hexadecimal public keys**.

### Endpoints Requiring Full 64-Char Keys:
- `GET /api/v1/nodes/{public_key}/messages` - Get messages for a node
- `GET /api/v1/nodes/{public_key}/telemetry` - Get telemetry for a node
- `GET /api/v1/nodes/{public_key}/tags` - Get/manage tags for a node
- `PUT /api/v1/nodes/{public_key}/tags/{key}` - Set a tag
- `POST /api/v1/nodes/{public_key}/tags/bulk` - Bulk update tags
- `DELETE /api/v1/nodes/{public_key}/tags/{key}` - Delete a tag
- `GET /api/v1/messages?sender_public_key=...` - Query messages by sender
- `GET /api/v1/advertisements?node_public_key=...` - Query advertisements
- `GET /api/v1/telemetry?node_public_key=...` - Query telemetry
- `GET /api/v1/tags?node_public_key=...` - Query tags
- All `/api/v1/commands/*` endpoints - Send commands to nodes

### Resolving Partial Keys to Full Keys:

If you only have a partial public key (prefix), use the prefix search endpoint first:

```bash
# Search by prefix (2-64 characters) - returns ALL matching nodes
GET /api/v1/nodes/{prefix}

# Example: Search for nodes starting with "abc123"
curl http://localhost:8000/api/v1/nodes/abc123
# Returns: {"nodes": [{"public_key": "abc123...full64chars...", ...}], "total": 1}
```

Then use the full `public_key` from the response for subsequent operations.

### Example Workflow:

```bash
# 1. Resolve prefix to full key(s)
curl http://localhost:8000/api/v1/nodes/abc123
# If multiple matches returned, user selects the correct one

# 2. Use full key for operations
FULL_KEY="abc123...full64chars..."
curl http://localhost:8000/api/v1/nodes/$FULL_KEY/messages
curl http://localhost:8000/api/v1/nodes/$FULL_KEY/tags
curl -X PUT http://localhost:8000/api/v1/nodes/$FULL_KEY/tags/location \
  -H "Content-Type: application/json" \
  -d '{"value_type": "coordinate", "value": {"latitude": 37.7749, "longitude": -122.4194}}'
```

### Database Storage:

- **Nodes table**: Stores full 64-char keys in `public_key` column (lowercase)
- **Messages table**: Stores first 12 chars in `pubkey_prefix` column (lowercase, from MeshCore events)
- **Advertisements/Telemetry tables**: Store full 64-char keys (lowercase)
- **Trace paths**: Store 2-char hashes (lowercase, from MeshCore events)

The API automatically handles truncation where needed (e.g., messages query).

### Public Key Normalization:

**All public keys and their shortened versions are stored and queried in lowercase** to ensure case-insensitive matching:

- **Storage**: All keys normalized to lowercase before persisting to database
  - Full keys via `normalize_public_key()` function
  - Shortened prefixes from MeshCore events converted to lowercase
  - Trace path hashes converted to lowercase
- **Queries**: All API inputs normalized to lowercase via `normalize_public_key()`
- **Consistency**: Case-insensitive operations throughout the application
