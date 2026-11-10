"""
Secure Examination & Proctoring Platform
proctor_web/dashboard_server.py - Standalone Launcher for Proctor Web & WebSocket Bridge
"""

import logging
import os
import sys
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from server.web_bridge import WebBridge

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [WEB DASHBOARD] %(message)s")
logger = logging.getLogger("DashboardServer")

if __name__ == "__main__":
    bridge = WebBridge(http_port=8080, ws_port=8081)
    bridge.start()
    logger.info("Proctor Web Dashboard running at: http://localhost:8080")
    logger.info("WebSocket Server running at: ws://localhost:8081")
    logger.info("Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        bridge.stop()
        logger.info("Proctor Web Dashboard stopped.")
