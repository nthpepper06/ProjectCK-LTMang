"""
Secure Examination & Proctoring Platform
common/discovery.py - Zero-Config UDP LAN Auto-Discovery Protocol
Enables automatic discovery of active Exam Servers across local subnet (Port 5006).
"""

import json
import logging
import os
import socket
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("DISCOVERY")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [DISCOVERY] %(message)s")

DEFAULT_DISCOVERY_PORT = 5006
CMD_DISCOVER = "DISCOVER_EXAM_SERVER"
CMD_ANNOUNCE = "SERVER_ANNOUNCEMENT"
DEFAULT_CONFIG_PATH = "client_config.json"


def get_local_ip_addresses() -> List[str]:
    """Retrieves list of active non-loopback IPv4 addresses on this host."""
    ips = []
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127."):
                ips.append(ip)
    except Exception:
        pass

    if not ips:
        try:
            # Fallback connect probe
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ips.append(s.getsockname()[0])
            s.close()
        except Exception:
            ips.append("127.0.0.1")
    return ips


class ServerDiscoveryResponder:
    """
    Background UDP service running on Exam Server that listens on port 5006.
    Replies to candidate client discovery broadcasts with server connection metadata.
    """

    def __init__(
        self,
        server_ip: Optional[str] = None,
        tcp_port: int = 8888,
        http_port: int = 8080,
        ws_port: int = 8081,
        exam_title: str = "Kỳ thi Cuối kỳ Lập trình Mạng & An toàn Hệ thống",
        discovery_port: int = DEFAULT_DISCOVERY_PORT
    ):
        self.server_ip = server_ip
        self.tcp_port = tcp_port
        self.http_port = http_port
        self.ws_port = ws_port
        self.exam_title = exam_title
        self.discovery_port = discovery_port

        self.sock: Optional[socket.socket] = None
        self.thread: Optional[threading.Thread] = None
        self.is_running = False

    def start(self) -> None:
        """Starts UDP discovery responder thread."""
        if self.is_running:
            return
        self.is_running = True

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.bind(("", self.discovery_port))
        self.sock.settimeout(1.0)

        self.thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="DiscoveryResponderThread"
        )
        self.thread.start()
        logger.info(f"UDP LAN Auto-Discovery Responder listening on port {self.discovery_port}")

    def stop(self) -> None:
        """Stops UDP listener cleanly."""
        self.is_running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        logger.info("UDP LAN Discovery Responder stopped.")

    def _worker_loop(self) -> None:
        while self.is_running:
            try:
                data, client_addr = self.sock.recvfrom(4096)
                if not data:
                    continue

                try:
                    msg = json.loads(data.decode("utf-8"))
                except Exception:
                    msg = {"cmd": data.decode("utf-8", errors="ignore").strip()}

                if msg.get("cmd") == CMD_DISCOVER:
                    logger.info(f"Received server discovery probe from {client_addr}")
                    # Resolve actual LAN IP
                    resolved_ip = self.server_ip
                    if not resolved_ip or resolved_ip in ("0.0.0.0", "127.0.0.1"):
                        ips = get_local_ip_addresses()
                        resolved_ip = ips[0] if ips else "127.0.0.1"

                    response = {
                        "cmd": CMD_ANNOUNCE,
                        "server_ip": resolved_ip,
                        "tcp_port": self.tcp_port,
                        "http_port": self.http_port,
                        "ws_port": self.ws_port,
                        "exam_title": self.exam_title,
                        "timestamp_ms": int(time.time() * 1000)
                    }
                    resp_bytes = json.dumps(response, ensure_ascii=False).encode("utf-8")
                    self.sock.sendto(resp_bytes, client_addr)
                    logger.info(f"Replied with server announcement to {client_addr} (IP: {resolved_ip}:{self.tcp_port})")

            except socket.timeout:
                continue
            except OSError:
                if not self.is_running:
                    break
            except Exception as e:
                if self.is_running:
                    logger.error(f"Error in discovery responder: {e}")


class ClientLANScanner:
    """Utility scanner for Kiosk Desktop Client to auto-locate server on LAN."""

    @staticmethod
    def discover_server(
        timeout_seconds: float = 3.0,
        port: int = DEFAULT_DISCOVERY_PORT
    ) -> Optional[Dict[str, Any]]:
        """
        Broadcasts discovery probe across LAN and listens for server response.
        Returns server announcement dict or None if no server found.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(0.5)

        probe_msg = json.dumps({"cmd": CMD_DISCOVER}).encode("utf-8")
        broadcast_targets = ["<broadcast>", "255.255.255.255", "127.0.0.1"]

        start_time = time.time()
        logger.info(f"Scanning local LAN for Exam Server (Broadcast port {port}, timeout: {timeout_seconds}s)...")

        # Initial broadcast burst
        for target in broadcast_targets:
            try:
                sock.sendto(probe_msg, (target, port))
            except Exception:
                pass

        announcement = None
        try:
            while time.time() - start_time < timeout_seconds:
                try:
                    data, addr = sock.recvfrom(4096)
                    resp = json.loads(data.decode("utf-8"))
                    if resp.get("cmd") == CMD_ANNOUNCE:
                        announcement = resp
                        # Overwrite server_ip with sender IP if localhost/empty
                        if announcement.get("server_ip") in ("0.0.0.0", "127.0.0.1") and addr[0] != "127.0.0.1":
                            announcement["server_ip"] = addr[0]
                        logger.info(f"✅ Discovered Exam Server: {announcement.get('server_ip')}:{announcement.get('tcp_port')}")
                        break
                except socket.timeout:
                    # Re-send probe every 1 second
                    if time.time() - start_time < timeout_seconds:
                        for target in broadcast_targets:
                            try:
                                sock.sendto(probe_msg, (target, port))
                            except Exception:
                                pass
                except Exception as e:
                    logger.debug(f"Ignore invalid packet: {e}")
        finally:
            sock.close()

        return announcement


def load_client_config(config_path: str = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """Loads cached client configuration (server IP, port, student ID)."""
    default_cfg = {
        "server_host": "127.0.0.1",
        "server_port": 8888,
        "auto_discovered": False,
        "last_student_id": "SV2026_01"
    }
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                saved = json.load(f)
                default_cfg.update(saved)
        except Exception as e:
            logger.warning(f"Failed to read {config_path}: {e}")
    return default_cfg


def save_client_config(config: Dict[str, Any], config_path: str = DEFAULT_CONFIG_PATH) -> None:
    """Saves client configuration to local JSON file."""
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved client configuration to {config_path}")
    except Exception as e:
        logger.error(f"Failed to save {config_path}: {e}")
