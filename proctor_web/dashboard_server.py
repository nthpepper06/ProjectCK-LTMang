"""
Secure Examination & Proctoring Platform
proctor_web/dashboard_server.py - WebSocket Relay Server for Proctor Web Dashboard
"""

import asyncio
import json
import logging
import websockets

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [WEB DASHBOARD] %(message)s")
logger = logging.getLogger("DashboardServer")

CONNECTED_CLIENTS = set()


async def register(websocket):
    CONNECTED_CLIENTS.add(websocket)
    logger.info(f"Proctor Web Dashboard connected: {websocket.remote_address}")
    try:
        await websocket.wait_closed()
    finally:
        CONNECTED_CLIENTS.remove(websocket)
        logger.info(f"Proctor Web Dashboard disconnected: {websocket.remote_address}")


async def broadcast_alert(alert_data: dict):
    """Broadcasts a violation alert or student status to all connected web dashboards."""
    if CONNECTED_CLIENTS:
        message = json.dumps(alert_data, ensure_ascii=False)
        await asyncio.gather(*[client.send(message) for client in CONNECTED_CLIENTS])


async def main():
    logger.info("Starting Proctor Dashboard WebSocket Server on ws://0.0.0.0:8765...")
    async with websockets.serve(register, "0.0.0.0", 8765):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Dashboard Server stopped.")
