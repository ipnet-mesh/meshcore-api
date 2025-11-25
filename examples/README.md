# Tag Import Examples

This directory contains example JSON files for bulk importing node tags using the `meshcore_api tag` command.

## Files

### ipnet.json

IPNet mesh network node metadata for 18 nodes across the Ipswich area (IP2, IP3, IP4, IP8).

**Usage:**
```bash
# Preview what would be imported
meshcore_api tag examples/ipnet.json --dry-run

# Import the tags
meshcore_api tag examples/ipnet.json

# Import with verbose output
meshcore_api tag examples/ipnet.json --verbose
```

**Tag Fields:**
- `friendly_name` (string) - Human-readable node name
- `node_id` (string) - DNS hostname/identifier
- `member_id` (string) - Network member who manages the node
- `area` (string) - Geographic area (e.g., "IP2", "IP3")
- `location` (coordinate) - GPS coordinates (latitude/longitude)
- `location_description` (string) - Human-readable location
- `hardware` (string) - Device hardware model
- `antenna` (string) - Antenna type and specifications
- `elevation` (number) - Elevation in meters
- `show_on_map` (boolean) - Whether to display on map
- `is_public` (boolean) - Public accessibility flag
- `is_online` (boolean) - Online status
- `is_testing` (boolean) - Testing/development flag
- `mesh_role` (string) - Role in mesh network (repeater/integration)

**Coverage:**
- 18 nodes total
- 251 tags
- Areas: IP2 (5 nodes), IP3 (9 nodes), IP4 (3 nodes), IP8 (2 nodes)
