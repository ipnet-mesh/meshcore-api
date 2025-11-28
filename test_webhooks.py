#!/usr/bin/env python3
"""Simple webhook receiver for testing webhook functionality."""

import asyncio
import json
from datetime import datetime
from aiohttp import web

# Store received webhooks
received_webhooks = {
    "direct": [],
    "channel": [],
    "advertisement": [],
}


async def webhook_direct(request):
    """Handle direct message webhooks."""
    data = await request.json()
    received_webhooks["direct"].append(data)
    print(f"\n[{datetime.now()}] Direct Message Webhook Received:")
    print(json.dumps(data, indent=2))
    return web.json_response({"status": "ok"})


async def webhook_channel(request):
    """Handle channel message webhooks."""
    data = await request.json()
    received_webhooks["channel"].append(data)
    print(f"\n[{datetime.now()}] Channel Message Webhook Received:")
    print(json.dumps(data, indent=2))
    return web.json_response({"status": "ok"})


async def webhook_advertisement(request):
    """Handle advertisement webhooks."""
    data = await request.json()
    received_webhooks["advertisement"].append(data)
    print(f"\n[{datetime.now()}] Advertisement Webhook Received:")
    print(json.dumps(data, indent=2))
    return web.json_response({"status": "ok"})


async def status(request):
    """Return webhook statistics."""
    stats = {
        "direct_count": len(received_webhooks["direct"]),
        "channel_count": len(received_webhooks["channel"]),
        "advertisement_count": len(received_webhooks["advertisement"]),
        "total": sum(len(v) for v in received_webhooks.values()),
    }
    print(f"\n[{datetime.now()}] Webhook Statistics:")
    print(json.dumps(stats, indent=2))
    return web.json_response(stats)


async def main():
    """Run the webhook test server."""
    app = web.Application()
    app.router.add_post("/webhooks/direct", webhook_direct)
    app.router.add_post("/webhooks/channel", webhook_channel)
    app.router.add_post("/webhooks/advertisement", webhook_advertisement)
    app.router.add_get("/status", status)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", 9000)
    await site.start()

    print("=" * 80)
    print("Webhook Test Server Started")
    print("=" * 80)
    print(f"Listening on: http://localhost:9000")
    print("")
    print("Webhook endpoints:")
    print("  - Direct Messages:  POST http://localhost:9000/webhooks/direct")
    print("  - Channel Messages: POST http://localhost:9000/webhooks/channel")
    print("  - Advertisements:   POST http://localhost:9000/webhooks/advertisement")
    print("  - Status:           GET  http://localhost:9000/status")
    print("")
    print("Press Ctrl+C to stop")
    print("=" * 80)
    print("")

    try:
        # Keep server running
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        print("\n\nShutting down webhook server...")
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
