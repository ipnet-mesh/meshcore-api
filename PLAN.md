# MeshCore Sidekick - Implementation Plan

## Project Overview

MeshCore companion application that:
- Subscribes to all MeshCore events via Serial/BLE
- Persists events in SQLite database with configurable retention
- Provides REST API for querying data and sending commands
- Includes mock MeshCore for development without hardware
- Exposes Prometheus metrics for monitoring
- Generates OpenAPI/Swagger documentation

## Technology Stack

- **Language**: Python 3.11+
- **Database**: SQLite with SQLAlchemy ORM
- **API Framework**: FastAPI
- **MeshCore Library**: meshcore_py (v2.2.1+)
- **Metrics**: Prometheus
- **Configuration**: CLI arguments > Environment variables > Defaults

---

## Phase 1: Foundation ✅ COMPLETE

**Goal**: Working application with database persistence and mock support

### Completed Components

#### 1.1 Project Setup ✅
- [x] Python package structure with pyproject.toml
- [x] Dependencies: meshcore, FastAPI, SQLAlchemy, Prometheus, etc.
- [x] README with quick start guide
- [x] .gitignore configuration

#### 1.2 Database Layer ✅
- [x] SQLAlchemy models (14 tables):
  - `nodes` - Node tracking with prefix indexing
  - `messages` - Direct and channel messages
  - `advertisements` - Node advertisements
  - `paths` - Routing path information
  - `trace_paths` - Trace path results with SNR
  - `telemetry` - Sensor data from nodes
  - `acknowledgments` - Message confirmations
  - `status_responses` - Node status data
  - `statistics` - Device statistics (core/radio/packets)
  - `binary_responses` - Binary protocol responses
  - `control_data` - Control packet data
  - `raw_data` - Raw packet data
  - `device_info` - Companion device information
  - `events_log` - Raw event log
- [x] Database engine with connection pooling
- [x] Session management with context managers
- [x] Data cleanup for retention policy
- [x] Indexes for fast prefix queries

#### 1.3 MeshCore Interface ✅
- [x] Abstract `MeshCoreInterface` base class
- [x] `RealMeshCore` - meshcore_py wrapper
- [x] `MockMeshCore` - Two operation modes:
  - Random event generation (configurable intervals)
  - Scenario playback (5 built-in scenarios)

#### 1.4 Built-in Mock Scenarios ✅
- [x] `simple_chat` - Two nodes exchanging messages
- [x] `trace_path_test` - Multi-hop network tracing
- [x] `telemetry_collection` - Periodic sensor data
- [x] `network_stress` - High-traffic simulation
- [x] `battery_drain` - Battery degradation over time

#### 1.5 Event Subscriber ✅
- [x] Event handler for all MeshCore event types
- [x] Database persistence logic
- [x] Node upsert (create/update) logic
- [x] Error handling and logging
- [x] Prometheus metrics collection points

#### 1.6 Configuration Management ✅
- [x] CLI argument parsing with argparse
- [x] Environment variable support
- [x] Priority: CLI > Env > Defaults
- [x] 20+ configuration options
- [x] Connection settings (serial/mock)
- [x] Database settings (path, retention)
- [x] API settings (host, port)
- [x] Logging settings (level, format)

#### 1.7 Utilities ✅
- [x] Public key address utilities:
  - Normalization (lowercase)
  - Validation (hex check)
  - Prefix extraction
  - Prefix matching
- [x] Logging setup:
  - JSON formatter for structured logs
  - Text formatter with colors
  - Configurable log levels
- [x] Prometheus metrics collectors (defined, not yet wired)

#### 1.8 Main Application ✅
- [x] Application lifecycle management
- [x] MeshCore connection handling
- [x] Event subscription setup
- [x] Background cleanup task
- [x] Signal handlers (SIGINT, SIGTERM)
- [x] Graceful shutdown

### Test Results ✅
- Database created with 14 tables
- Events captured and persisted
- Mock scenarios working (simple_chat verified)
- Node tracking functional
- Message/advertisement storage working
- Configuration system operational

---

## Phase 2: REST API ✅ COMPLETE

**Goal**: Full REST API with OpenAPI docs

### 2.1 FastAPI Application Setup
- [x] Create FastAPI app with metadata
- [x] Configure CORS middleware
- [x] Add exception handlers
- [x] Setup startup/shutdown events
- [x] Configure OpenAPI customization:
  - Title, version, description
  - Contact and license information
  - API grouping with tags
  - Example values for all models

### 2.2 Pydantic Models
- [x] Request models for all command endpoints
- [x] Response models for all endpoints
- [x] Validation rules and constraints
- [x] Field descriptions and examples
- [x] Nested models for complex data

### 2.3 Command Endpoints (POST)
- [x] `POST /api/v1/commands/send_message`
  - Send direct message to node
  - Input: destination, text, text_type
  - Output: message_id, estimated_delivery_ms
- [x] `POST /api/v1/commands/send_channel_message`
  - Send channel broadcast
  - Input: text, flood
- [x] `POST /api/v1/commands/send_advert`
  - Send self-advertisement
  - Input: flood
- [x] `POST /api/v1/commands/send_trace_path`
  - Initiate trace path
  - Input: destination
  - Output: trace_id, initiator_tag
- [x] `POST /api/v1/commands/ping`
  - Ping a node
  - Input: destination
- [x] `POST /api/v1/commands/send_telemetry_request`
  - Request telemetry
  - Input: destination

### 2.4 Query Endpoints (GET)
- [x] `GET /api/v1/messages`
  - List messages with filters:
    - from/to (public key prefix)
    - type (contact/channel)
    - start_date/end_date
    - limit/offset (pagination)
- [x] `GET /api/v1/advertisements`
  - List advertisements with filters:
    - node (public key prefix)
    - adv_type
    - date range, pagination
- [x] `GET /api/v1/telemetry`
  - List telemetry data
  - Filters: node, date range, pagination
- [x] `GET /api/v1/trace_paths`
  - List trace path results
  - Filters: destination, date range, pagination
- [x] `GET /api/v1/statistics`
  - Get latest statistics
  - Query param: stat_type (core/radio/packets)
- [x] `GET /api/v1/device_info`
  - Get companion device information

### 2.5 Node Endpoints (GET)
- [x] `GET /api/v1/nodes`
  - List all nodes
  - Filters: sort, order, pagination
- [x] `GET /api/v1/nodes/{prefix}`
  - Search by prefix (2-64 chars)
  - Returns all matching nodes
- [x] `GET /api/v1/nodes/{public_key}/messages`
  - Get messages for specific node
  - Filters: date range, pagination
- [x] `GET /api/v1/nodes/{public_key}/paths`
  - Get routing paths for node
- [x] `GET /api/v1/nodes/{public_key}/telemetry`
  - Get telemetry for node
  - Filters: date range, pagination

### 2.6 Health Endpoints (GET)
- [x] `GET /api/v1/health`
  - Overall health status
  - MeshCore connection status
  - Database connection status
  - Uptime, events processed
- [x] `GET /api/v1/health/db`
  - Database connectivity check
  - Database size
  - Table row counts
- [x] `GET /api/v1/health/meshcore`
  - MeshCore connection status
  - Device info (if connected)

### 2.7 Dependencies and Middleware
- [x] Database session dependency
- [x] MeshCore instance dependency
- [x] Request logging middleware
- [x] Error response formatting
- [x] CORS configuration

### 2.8 Integration
- [x] Integrate FastAPI with main application
- [x] Run API server in background task
- [x] Share MeshCore instance with API routes
- [x] Add API configuration options

### Test Results ✅
- API server starts successfully on port 8000
- Health endpoints working (`/api/v1/health`, `/api/v1/health/db`, `/api/v1/health/meshcore`)
- Node endpoints working (list nodes, search by prefix)
- Message endpoints working (query with filters)
- All query endpoints functional with pagination
- Command endpoints implemented and ready for testing
- OpenAPI documentation available at `/docs` and `/redoc`
- CORS middleware configured
- Exception handling working correctly

---

## Phase 3: Observability 📋 PLANNED

**Goal**: Production-ready observability

### 3.1 Prometheus Integration
- [ ] Wire up metrics collectors in event handler
- [ ] Add `/metrics` endpoint
- [ ] Implement all metric types:
  - Event counters by type
  - Message latency histograms
  - Node connectivity gauges
  - Signal quality histograms (SNR/RSSI)
  - Battery/storage gauges
  - Radio statistics
  - Database metrics
  - Error counters
- [ ] Add FastAPI metrics middleware
- [ ] Document Prometheus queries

### 3.2 Enhanced Logging
- [ ] Add contextual logging throughout
- [ ] Log request/response for API calls
- [ ] Log event processing errors
- [ ] Add correlation IDs for tracing
- [ ] Performance logging for slow queries

### 3.3 Database Monitoring
- [ ] Periodic database size updates
- [ ] Table row count metrics
- [ ] Query performance tracking
- [ ] Cleanup operation metrics

### 3.4 Health Monitoring
- [ ] Connection status tracking
- [ ] Auto-reconnect attempts
- [ ] Event processing lag monitoring
- [ ] Alert on connection failures

---

## Phase 4: Docker Deployment 📋 PLANNED

**Goal**: Production-ready Docker deployment

### 4.1 Dockerfile
- [ ] Multi-stage build for smaller image
- [ ] Python 3.11+ base image
- [ ] Install dependencies
- [ ] Non-root user
- [ ] Health check
- [ ] Expose ports (API: 8000)

### 4.2 Docker Compose (Development)
- [ ] meshcore-sidekick service (mock mode)
- [ ] Volume mounts for development
- [ ] Environment variable configuration
- [ ] Port mappings
- [ ] Optional: Prometheus service
- [ ] Optional: Grafana service

### 4.3 Docker Compose (Production)
- [ ] meshcore-sidekick service (real hardware)
- [ ] Serial device mapping
- [ ] Persistent volume for database
- [ ] Restart policy
- [ ] Logging configuration
- [ ] Health checks

### 4.4 Prometheus Configuration
- [ ] prometheus.yml scrape config
- [ ] Target: meshcore-sidekick:8000/metrics
- [ ] Scrape interval: 15s

### 4.5 Grafana Dashboard
- [ ] Dashboard JSON configuration
- [ ] Panels:
  - Message rate over time
  - Active nodes gauge
  - Round-trip latency histogram
  - Battery voltage gauge
  - Signal quality graphs (SNR/RSSI)
  - Event type distribution
  - Database size gauge

### 4.6 Documentation
- [ ] Docker build instructions
- [ ] Docker run examples
- [ ] docker-compose usage
- [ ] Environment variable reference
- [ ] Volume mounting guide
- [ ] Serial device access setup

---

## Phase 5: Testing & Documentation 📋 PLANNED

**Goal**: Comprehensive testing and documentation

### 5.1 Unit Tests
- [ ] Database model tests
- [ ] Address utility tests
- [ ] Configuration tests
- [ ] Mock MeshCore tests
- [ ] Event handler tests

### 5.2 Integration Tests
- [ ] API endpoint tests
- [ ] Database persistence tests
- [ ] Mock scenario tests
- [ ] Configuration priority tests

### 5.3 API Documentation
- [ ] Complete OpenAPI schema
- [ ] Request/response examples
- [ ] Authentication documentation (future)
- [ ] Error code reference
- [ ] Rate limiting info (future)

### 5.4 User Documentation
- [ ] Installation guide
- [ ] Configuration guide
- [ ] CLI reference
- [ ] Environment variable reference
- [ ] API usage examples
- [ ] Mock scenario guide
- [ ] Troubleshooting guide

### 5.5 Developer Documentation
- [ ] Architecture overview
- [ ] Database schema documentation
- [ ] Adding new scenarios
- [ ] Contributing guide
- [ ] Code style guide

---

## Phase 6: Advanced Features 📋 FUTURE

**Goal**: Additional functionality and integrations

### 6.1 MCP Server Integration
- [ ] Define MCP protocol schemas
- [ ] Implement MCP tool endpoints
- [ ] Read operations:
  - Query battery status
  - Query messages
  - Query node list
  - Query telemetry
- [ ] Write operations:
  - Send message
  - Send advertisement
  - Ping node
  - Send telemetry request
- [ ] MCP server documentation
- [ ] Example MCP client usage

### 6.2 Web UI (Optional)
- [ ] React/Vue frontend
- [ ] Dashboard with real-time updates
- [ ] Node map visualization
- [ ] Message history viewer
- [ ] Network topology graph
- [ ] Configuration interface

### 6.3 Real-time Features
- [ ] WebSocket endpoint for live events
- [ ] Server-Sent Events (SSE) support
- [ ] Real-time node status updates
- [ ] Live message notifications

### 6.4 Advanced Querying
- [ ] Full-text search on messages
- [ ] Geographic queries (nodes within radius)
- [ ] Network topology queries
- [ ] Path analysis tools
- [ ] Message threading/conversations

### 6.5 Alert System
- [ ] Alert rules engine
- [ ] Node offline alerts
- [ ] Low battery alerts
- [ ] Message delivery failures
- [ ] Network congestion alerts
- [ ] Alert delivery (webhook, email)

### 6.6 Data Export
- [ ] CSV export for all tables
- [ ] JSON export
- [ ] GPX export for node locations
- [ ] Message archive export
- [ ] Statistics reports

### 6.7 Authentication & Authorization
- [ ] API key authentication
- [ ] JWT token support
- [ ] Role-based access control
- [ ] Rate limiting per API key
- [ ] Usage tracking

### 6.8 Performance Enhancements
- [ ] PostgreSQL backend option
- [ ] Redis caching layer
- [ ] Message queue for event processing
- [ ] Horizontal scaling support
- [ ] Read replicas

---

## Configuration Reference

### CLI Arguments

```bash
Connection:
  --serial-port TEXT          Serial port device
  --serial-baud INTEGER       Serial baud rate
  --use-mock                  Use mock MeshCore
  --mock-scenario TEXT        Scenario name for playback
  --mock-loop                 Loop scenario indefinitely
  --mock-nodes INTEGER        Number of simulated nodes
  --mock-min-interval FLOAT   Min event interval (seconds)
  --mock-max-interval FLOAT   Max event interval (seconds)
  --mock-center-lat FLOAT     Center latitude
  --mock-center-lon FLOAT     Center longitude

Database:
  --db-path TEXT                   Database file path
  --retention-days INTEGER         Data retention days
  --cleanup-interval-hours INTEGER Cleanup interval hours

API:
  --api-host TEXT     API host
  --api-port INTEGER  API port
  --api-title TEXT    API title
  --api-version TEXT  API version

Metrics:
  --no-metrics        Disable Prometheus metrics

Logging:
  --log-level LEVEL   Log level (DEBUG/INFO/WARNING/ERROR/CRITICAL)
  --log-format TYPE   Log format (json/text)
```

### Environment Variables

```bash
# Connection
MESHCORE_SERIAL_PORT=/dev/ttyUSB0
MESHCORE_SERIAL_BAUD=115200
MESHCORE_USE_MOCK=true
MESHCORE_MOCK_SCENARIO=simple_chat
MESHCORE_MOCK_LOOP=true
MESHCORE_MOCK_NODES=10
MESHCORE_MOCK_MIN_INTERVAL=1.0
MESHCORE_MOCK_MAX_INTERVAL=10.0
MESHCORE_MOCK_CENTER_LAT=45.5231
MESHCORE_MOCK_CENTER_LON=-122.6765

# Database
MESHCORE_DB_PATH=/data/meshcore.db
MESHCORE_RETENTION_DAYS=30
MESHCORE_CLEANUP_INTERVAL_HOURS=1

# API
MESHCORE_API_HOST=0.0.0.0
MESHCORE_API_PORT=8000
MESHCORE_API_TITLE="MeshCore Sidekick API"
MESHCORE_API_VERSION="1.0.0"

# Metrics
MESHCORE_METRICS_ENABLED=true

# Logging
MESHCORE_LOG_LEVEL=INFO
MESHCORE_LOG_FORMAT=json
```

---

## Database Schema

### Tables

1. **nodes** - Node tracking with prefix indexing
2. **messages** - Direct and channel messages
3. **advertisements** - Node advertisements with GPS
4. **paths** - Routing path information
5. **trace_paths** - Trace results with SNR data
6. **telemetry** - Sensor telemetry data
7. **acknowledgments** - Message confirmations with timing
8. **status_responses** - Node status data
9. **statistics** - Device statistics (core/radio/packets)
10. **binary_responses** - Binary protocol responses
11. **control_data** - Control packet data
12. **raw_data** - Raw packet data
13. **device_info** - Companion device information
14. **events_log** - Raw event log for all events

### Key Indexes

- `nodes.public_key` (unique)
- `nodes.public_key_prefix_2` (for fast 2-char prefix queries)
- `nodes.public_key_prefix_8` (for fast 8-char prefix queries)
- `messages.from_public_key`
- `messages.to_public_key`
- `messages.timestamp`
- `advertisements.public_key`
- `events_log.event_type`
- `events_log.created_at` (for cleanup)

---

## Mock Scenarios

### simple_chat
Two nodes (Alice & Bob) exchanging messages
- Duration: 10 seconds
- Events: 2 advertisements, 2 messages, 1 ACK

### trace_path_test
Trace path through multi-hop network
- Duration: 5 seconds
- Events: 3 advertisements, 1 trace result

### telemetry_collection
Periodic telemetry from sensor node
- Duration: 15 seconds
- Events: 1 advertisement, 3 telemetry responses

### network_stress
High-traffic scenario with many nodes
- Duration: 30 seconds
- Events: 10 advertisements, 20 channel messages

### battery_drain
Simulated battery drain over time
- Duration: 200 seconds
- Events: 20 battery status updates

---

## Metrics Reference

### Event Counters
- `meshcore_events_total{event_type}` - Total events by type
- `meshcore_messages_total{direction,message_type}` - Messages by direction/type
- `meshcore_advertisements_total{adv_type}` - Advertisements by type

### Latency
- `meshcore_message_roundtrip_seconds` - Message round-trip time
- `meshcore_ack_latency_seconds` - ACK latency

### Connectivity
- `meshcore_nodes_total` - Total unique nodes
- `meshcore_nodes_active{node_type}` - Active nodes (last hour)
- `meshcore_path_hop_count` - Path hop distribution

### Signal Quality
- `meshcore_snr_db` - SNR histogram
- `meshcore_rssi_dbm` - RSSI histogram

### Device
- `meshcore_battery_voltage` - Battery voltage
- `meshcore_battery_percentage` - Battery percentage
- `meshcore_storage_used_bytes` - Storage used
- `meshcore_storage_total_bytes` - Storage total

### Radio
- `meshcore_radio_noise_floor_dbm` - Noise floor
- `meshcore_radio_airtime_percent` - Airtime utilization
- `meshcore_packets_total{direction,status}` - Packet counts

### Database
- `meshcore_db_table_rows{table}` - Rows per table
- `meshcore_db_size_bytes` - Database size
- `meshcore_db_cleanup_rows_deleted{table}` - Cleanup counts

### Application
- `meshcore_connection_status` - Connection status (1=connected)
- `meshcore_errors_total{component,error_type}` - Error counts

---

## Development Workflow

### Setup
```bash
# Clone repository
git clone https://github.com/ipnet-mesh/meshcore-sidekick.git
cd meshcore-sidekick

# Install dependencies
pip install -r requirements.txt

# Or with Poetry
poetry install
```

### Running
```bash
# Development with mock
python -m meshcore_sidekick --use-mock --log-level DEBUG

# With scenario
python -m meshcore_sidekick --use-mock --mock-scenario simple_chat

# Production with hardware
python -m meshcore_sidekick --serial-port /dev/ttyUSB0
```

### Testing
```bash
# Run tests
pytest

# With coverage
pytest --cov=meshcore_sidekick

# Specific test
pytest tests/test_database.py
```

### Code Quality
```bash
# Format
black src/ tests/

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

---

## Deployment

### Local Development
```bash
python -m meshcore_sidekick --use-mock
```

### Docker (Mock)
```bash
docker-compose up --build
```

### Docker (Production)
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Systemd Service
```ini
[Unit]
Description=MeshCore Sidekick
After=network.target

[Service]
Type=simple
User=meshcore
WorkingDirectory=/opt/meshcore-sidekick
Environment="MESHCORE_SERIAL_PORT=/dev/ttyUSB0"
Environment="MESHCORE_DB_PATH=/var/lib/meshcore/data.db"
ExecStart=/usr/bin/python3 -m meshcore_sidekick
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## Future Considerations

### Scalability
- Separate API server from event collector
- Use message queue (Redis/RabbitMQ) for events
- PostgreSQL for multi-instance deployments
- Read replicas for query performance

### Security
- API authentication (API keys, JWT)
- Rate limiting
- Input validation
- SQL injection prevention
- Encrypted storage option

### Data Privacy
- Optional message content exclusion
- GDPR compliance features
- Data export tools
- User data deletion

### Performance
- Connection pooling optimization
- Query optimization
- Caching frequently accessed data
- Batch inserts for events

---

## Contributing

1. Create feature branch from `main`
2. Implement changes with tests
3. Follow code style (black, ruff)
4. Update documentation
5. Submit pull request

## License

See LICENSE file for details.
