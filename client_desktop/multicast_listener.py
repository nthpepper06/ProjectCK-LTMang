"""
Secure Examination & Proctoring Platform
client_desktop/multicast_listener.py - UDP Multicast Exam Listener Thread
"""

import logging
import os
import socket
import struct
import sys
import threading
from typing import Callable, Optional

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common.protocol import CommandType, unpack_header

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [MULTICAST LISTENER] %(message)s")
logger = logging.getLogger("MulticastListener")

DEFAULT_MULTICAST_GROUP = "224.1.1.1"
DEFAULT_MULTICAST_PORT = 5005


class MulticastListenerThread(threading.Thread):
    """
    Background worker thread that joins a UDP Multicast group on the LAN
    and notifies the Desktop Client whenever the Proctor broadcasts an event.
    """

    def __init__(
        self,
        group_ip: str = DEFAULT_MULTICAST_GROUP,
        port: int = DEFAULT_MULTICAST_PORT,
        on_command_received: Optional[Callable[[CommandType, dict], None]] = None
    ):
        super().__init__(daemon=True, name="MulticastListener")
        self.group_ip = group_ip
        self.port = port
        self.on_command_received = on_command_received
        self.is_running = False
        self.sock: Optional[socket.socket] = None

    def run(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Bind to the multicast port across all local network interfaces
        try:
            self.sock.bind(("", self.port))
        except Exception:
            self.sock.bind(("0.0.0.0", self.port))

        # Join the multicast group
        mreq = struct.pack("4sl", socket.inet_aton(self.group_ip), socket.INADDR_ANY)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        self.is_running = True
        logger.info(f"Joined UDP Multicast group {self.group_ip}:{self.port}. Waiting for proctor commands...")

        import json

        while self.is_running:
            try:
                data, addr = self.sock.recvfrom(65535)
                if len(data) < 23:
                    continue

                header = unpack_header(data[:23])
                cmd = CommandType(header["cmd"]) if header["cmd"] in CommandType._value2member_map_ else header["cmd"]
                payload_bytes = data[23:23 + header["payload_length"]]

                try:
                    payload = json.loads(payload_bytes.decode("utf-8"))
                except Exception:
                    payload = {"raw": payload_bytes}

                logger.info(f"🔔 Received Multicast broadcast from {addr}: {header['cmd_name']}")

                if self.on_command_received:
                    self.on_command_received(cmd, payload)

            except OSError:
                break
            except Exception as e:
                logger.error(f"Error reading multicast datagram: {e}")

    def stop(self) -> None:
        self.is_running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        logger.info("Multicast listener stopped.")
