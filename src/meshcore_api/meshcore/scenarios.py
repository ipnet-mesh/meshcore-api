"""Predefined scenarios for mock MeshCore playback."""

import random
import uuid
from datetime import datetime
from typing import Any, Dict


def process_dynamic_values(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process dynamic placeholder values in event data.

    Supported placeholders:
    - {{now}}: Current timestamp (ISO format)
    - {{random_snr}}: Random SNR value (-20 to 30 dB)
    - {{random_rssi}}: Random RSSI value (-110 to -50 dBm)
    - {{uuid}}: Random UUID
    - {{counter}}: Incrementing counter

    Args:
        data: Event data dictionary

    Returns:
        Processed dictionary with placeholders replaced
    """
    result = {}
    counter = getattr(process_dynamic_values, "_counter", 0)

    for key, value in data.items():
        if isinstance(value, str):
            if value == "{{now}}":
                result[key] = datetime.utcnow().isoformat() + "Z"
            elif value == "{{random_snr}}":
                result[key] = random.uniform(-20, 30)
            elif value == "{{random_rssi}}":
                result[key] = random.uniform(-110, -50)
            elif value == "{{uuid}}":
                result[key] = str(uuid.uuid4())
            elif value == "{{counter}}":
                result[key] = counter
                counter += 1
            else:
                result[key] = value
        elif isinstance(value, dict):
            result[key] = process_dynamic_values(value)
        elif isinstance(value, list):
            result[key] = [
                process_dynamic_values(item) if isinstance(item, dict) else item for item in value
            ]
        else:
            result[key] = value

    process_dynamic_values._counter = counter
    return result


SCENARIOS = {
    "simple_chat": {
        "description": "Two nodes exchanging messages",
        "events": [
            {
                "delay": 0.0,
                "type": "ADVERTISEMENT",
                "data": {
                    "public_key": "01ab2186c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1",
                    "name": "Alice",
                    "adv_type": "chat",
                    "latitude": 45.5231,
                    "longitude": -122.6765,
                    "flags": 0,
                },
            },
            {
                "delay": 2.0,
                "type": "ADVERTISEMENT",
                "data": {
                    "public_key": "b3f4e5d6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4",
                    "name": "Bob",
                    "adv_type": "chat",
                    "latitude": 45.5345,
                    "longitude": -122.6543,
                    "flags": 0,
                },
            },
            {
                "delay": 5.0,
                "type": "CONTACT_MSG_RECV",
                "data": {
                    "pubkey_prefix": "01ab2186c4d5",
                    "path_len": 3,
                    "txt_type": 0,
                    "text": "Hello Bob!",
                    "SNR": 15.5,
                    "sender_timestamp": "{{now}}",
                },
            },
            {
                "delay": 8.0,
                "type": "SEND_CONFIRMED",
                "data": {
                    "destination_public_key": "01ab2186c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1",
                    "round_trip_ms": 2500,
                },
            },
            {
                "delay": 10.0,
                "type": "CONTACT_MSG_RECV",
                "data": {
                    "pubkey_prefix": "b3f4e5d6a7b8",
                    "path_len": 2,
                    "txt_type": 0,
                    "text": "Hi Alice! How are you?",
                    "SNR": 14.8,
                    "sender_timestamp": "{{now}}",
                },
            },
        ],
    },
    "trace_path_test": {
        "description": "Trace path through multi-hop network",
        "events": [
            {
                "delay": 0.0,
                "type": "ADVERTISEMENT",
                "data": {
                    "public_key": "01abc123456789abcdef0123456789abcdef0123456789abcdef0123456789ab",
                    "name": "NodeA",
                    "adv_type": "chat",
                    "latitude": 45.5231,
                    "longitude": -122.6765,
                },
            },
            {
                "delay": 1.0,
                "type": "ADVERTISEMENT",
                "data": {
                    "public_key": "b3def456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                    "name": "NodeB",
                    "adv_type": "repeater",
                    "latitude": 45.5345,
                    "longitude": -122.6543,
                },
            },
            {
                "delay": 2.0,
                "type": "ADVERTISEMENT",
                "data": {
                    "public_key": "fa9876543210fedcba9876543210fedcba9876543210fedcba9876543210fedc",
                    "name": "NodeC",
                    "adv_type": "chat",
                    "latitude": 45.5456,
                    "longitude": -122.6321,
                },
            },
            {
                "delay": 5.0,
                "type": "TRACE_DATA",
                "data": {
                    "initiator_tag": 305419896,
                    "path_len": 2,
                    "path_hashes": ["b3", "fa"],
                    "snr_values": [48.0, 45.2],
                    "hop_count": 2,
                },
            },
        ],
    },
    "telemetry_collection": {
        "description": "Periodic telemetry from sensor nodes",
        "events": [
            {
                "delay": 0.0,
                "type": "ADVERTISEMENT",
                "data": {
                    "public_key": "sensor01aabbccddeeff00112233445566778899aabbccddeeff00112233445566",
                    "name": "TempSensor",
                    "adv_type": "chat",
                    "latitude": 45.5231,
                    "longitude": -122.6765,
                },
            },
            {
                "delay": 5.0,
                "type": "TELEMETRY_RESPONSE",
                "data": {
                    "node_public_key": "sensor01aabb",
                    "parsed_data": {"temperature": 22.5, "humidity": 65, "battery": 3.8},
                },
            },
            {
                "delay": 10.0,
                "type": "TELEMETRY_RESPONSE",
                "data": {
                    "node_public_key": "sensor01aabb",
                    "parsed_data": {"temperature": 23.1, "humidity": 63, "battery": 3.75},
                },
            },
            {
                "delay": 15.0,
                "type": "TELEMETRY_RESPONSE",
                "data": {
                    "node_public_key": "sensor01aabb",
                    "parsed_data": {"temperature": 23.8, "humidity": 61, "battery": 3.72},
                },
            },
        ],
    },
    "network_stress": {
        "description": "High-traffic scenario with many nodes",
        "events": [
            # 10 nodes advertising
            *[
                {
                    "delay": i * 0.5,
                    "type": "ADVERTISEMENT",
                    "data": {
                        "public_key": f"node{i:02d}{'ab' * 30}",
                        "name": f"Node{i:02d}",
                        "adv_type": "chat",
                        "latitude": 45.52 + (i * 0.01),
                        "longitude": -122.67 + (i * 0.01),
                    },
                }
                for i in range(10)
            ],
            # Flood of channel messages
            *[
                {
                    "delay": 10.0 + i * 1.0,
                    "type": "CHANNEL_MSG_RECV",
                    "data": {
                        "channel_idx": i % 3,
                        "path_len": 0,
                        "txt_type": 0,
                        "text": f"Channel message {i}",
                        "SNR": "{{random_snr}}",
                        "sender_timestamp": "{{now}}",
                    },
                }
                for i in range(20)
            ],
        ],
    },
    "battery_drain": {
        "description": "Simulated battery drain over time",
        "events": [
            *[
                {
                    "delay": i * 10.0,
                    "type": "BATTERY",
                    "data": {
                        "battery_voltage": max(3.0, 4.2 - (i * 0.05)),
                        "battery_percentage": max(0, 100 - (i * 5)),
                    },
                }
                for i in range(20)
            ]
        ],
    },
}
