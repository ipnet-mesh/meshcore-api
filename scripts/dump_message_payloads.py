"""Utility to dump meshcore_py message- and trace-related event payloads."""

import asyncio
import json
import signal

from meshcore_api.config import Config
from meshcore_api.meshcore.real import RealMeshCore

TARGET_EVENTS = {"CONTACT_MSG_RECV", "CHANNEL_MSG_RECV", "MSG_SENT", "TRACE_DATA"}


async def main() -> None:
    """Connect to MeshCore and print selected event payloads."""
    config = Config.from_args_and_env()
    meshcore = RealMeshCore(config.serial_port, config.serial_baud)

    if not await meshcore.connect():
        print("Failed to connect to MeshCore. Check serial port and try again.")
        return

    stop_event = asyncio.Event()

    async def handle_event(event) -> None:
        """Print selected event payloads as JSON."""
        if event.type in TARGET_EVENTS:
            print(json.dumps({"type": event.type, "payload": event.payload}, indent=2))
            print("-" * 40, flush=True)

    await meshcore.subscribe_to_events(handle_event)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    print("Listening for CONTACT/CHANNEL/TRACE events (Ctrl+C to stop)...")
    try:
        await stop_event.wait()
    finally:
        await meshcore.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
