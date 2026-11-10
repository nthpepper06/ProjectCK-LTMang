"""
Secure Examination & Proctoring Platform
server/web_bridge.py - Real-Time Web & WebSocket Bridge for Proctor Web Dashboard
Serves Proctor Web UI, REST endpoints, and pushes live candidate telemetry, AI violations, and submissions over WebSockets.
"""

import asyncio
import json
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional, Set
from urllib.parse import parse_qs, urlparse

import websockets
from websockets.asyncio.server import ServerConnection

from common.protocol import CommandType, get_current_timestamp_ms
from server.core.session_manager import SessionManager, get_session_manager
from server.database.repositories import ExamRepository, SubmissionRepository, ViolationRepository
from server.multicast_sender import MulticastSender
from server.services.audit_service import AuditService
from server.services.exam_service import ExamService

logger = logging.getLogger("WEB_BRIDGE")
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(name)s] %(message)s"
    )


class ProctorHTTPHandler(BaseHTTPRequestHandler):
    """Custom HTTP handler serving Proctor Web Dashboard, evidence snapshots, and REST APIs."""

    bridge: "WebBridge" = None  # Injected by WebBridge

    def log_message(self, format, *args):
        # Suppress noisy standard HTTP logs, log only errors
        if args and str(args[1])[0] in ("4", "5"):
            logger.warning(f"HTTP {args[0]} {args[1]}")

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # 1. Static Root: Proctor Web Dashboard UI
        if path in ("/", "/index.html"):
            index_path = os.path.join(self.bridge.web_dir, "index.html")
            if os.path.exists(index_path):
                with open(index_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            else:
                self.send_error(404, "Proctor Web Dashboard file not found.")
                return

        # 2. Evidence Snapshot Images
        if path.startswith("/evidence/"):
            filename = os.path.basename(path)
            file_path = os.path.join(self.bridge.evidence_dir, filename)
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    img_data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(img_data)))
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                self.wfile.write(img_data)
                return
            else:
                self.send_error(404, "Evidence image snapshot not found.")
                return

        # 3. REST API: /api/overview
        if path == "/api/overview":
            data = self.bridge.get_overview_stats()
            self._send_json(data)
            return

        # 4. REST API: /api/sessions
        if path == "/api/sessions":
            data = self.bridge.get_sessions_list()
            self._send_json(data)
            return

        # 5. REST API: /api/violations
        if path == "/api/violations":
            data = self.bridge.get_violations_list()
            self._send_json(data)
            return

        # 6. REST API: /api/submissions
        if path == "/api/submissions":
            data = self.bridge.get_submissions_list()
            self._send_json(data)
            return

        self.send_error(404, "Endpoint not found.")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/multicast":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}

            action = payload.get("action", "").upper()
            res = self.bridge.handle_multicast_action(action, payload)
            self._send_json(res)
            return

        self.send_error(404, "Endpoint not found.")

    def _send_json(self, data: Any):
        payload_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload_bytes)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload_bytes)


class WebBridge:
    """
    Unified HTTP Server & WebSocket Real-time Telemetry Broadcaster.
    Runs in the same process as tcp_server.py to access live SessionManager,
    Repositories, and trigger UDP Multicast commands from Web Dashboard.
    """

    def __init__(
        self,
        http_host: str = "0.0.0.0",
        http_port: int = 8080,
        ws_port: int = 8081,
        session_manager: Optional[SessionManager] = None,
        exam_service: Optional[ExamService] = None,
        audit_service: Optional[AuditService] = None,
        multicast_sender: Optional[MulticastSender] = None,
        web_dir: str = "proctor_web",
        evidence_dir: str = "server_storage/evidence",
    ):
        self.http_host = http_host
        self.http_port = http_port
        self.ws_port = ws_port
        self.session_manager = session_manager or get_session_manager()
        self.exam_service = exam_service
        self.audit_service = audit_service
        self.multicast_sender = multicast_sender or MulticastSender()
        self.web_dir = os.path.abspath(web_dir)
        self.evidence_dir = os.path.abspath(evidence_dir)

        os.makedirs(self.web_dir, exist_ok=True)
        os.makedirs(self.evidence_dir, exist_ok=True)

        # Repositories for queries
        self.exam_repo = ExamRepository()
        self.sub_repo = SubmissionRepository()
        self.viol_repo = ViolationRepository()

        # WebSocket state
        self._ws_clients: Set[ServerConnection] = set()
        self._ws_lock = threading.Lock()
        self.ws_loop: Optional[asyncio.AbstractEventLoop] = None
        self.ws_thread: Optional[threading.Thread] = None
        self.http_server: Optional[ThreadingHTTPServer] = None
        self.http_thread: Optional[threading.Thread] = None
        self.is_running = False

        # Hook services to push live notifications
        self._setup_service_hooks()

    def _setup_service_hooks(self) -> None:
        """Hooks into audit and exam services to broadcast live events."""
        if self.audit_service:
            original_log = self.audit_service.log_violation

            def hooked_log_violation(*args, **kwargs):
                res = original_log(*args, **kwargs)
                # Build real-time violation event payload
                student_id = kwargs.get("student_id") or (args[0] if len(args) > 0 else "ANONYMOUS")
                v_type = kwargs.get("violation_type") or (args[2] if len(args) > 2 else "UNKNOWN")
                score = kwargs.get("suspicion_score") or (args[3] if len(args) > 3 else 1.0)
                details = kwargs.get("details") or (args[4] if len(args) > 4 else "")
                evidence_b64 = kwargs.get("evidence_b64") or (args[5] if len(args) > 5 else None)
                ts = kwargs.get("timestamp_ms") or (args[6] if len(args) > 6 else int(time.time() * 1000))

                evidence_file = res.get("evidence_saved")
                if not evidence_file and evidence_b64:
                    evidence_file = f"{student_id}_{v_type}_{ts}.jpg"
                event = {
                    "type": "NEW_VIOLATION",
                    "data": {
                        "student_id": student_id,
                        "violation_type": v_type,
                        "suspicion_score": score,
                        "details": details,
                        "evidence_url": f"/evidence/{evidence_file}" if evidence_file else None,
                        "timestamp_ms": ts,
                        "time_str": time.strftime("%H:%M:%S", time.localtime((ts or 0) / 1000))
                    },
                    "overview": self.get_overview_stats()
                }
                self.broadcast_ws(event)
                return res

            self.audit_service.log_violation = hooked_log_violation

    def start(self) -> None:
        """Starts both HTTP Web Server and WebSocket Server in background threads."""
        if self.is_running:
            return
        self.is_running = True

        # 1. Start HTTP Server
        ProctorHTTPHandler.bridge = self
        self.http_server = ThreadingHTTPServer((self.http_host, self.http_port), ProctorHTTPHandler)
        self.http_thread = threading.Thread(
            target=self.http_server.serve_forever,
            daemon=True,
            name="ProctorHTTPServer"
        )
        self.http_thread.start()
        logger.info(f"Proctor Web Dashboard running at: http://localhost:{self.http_port}")

        # 2. Start WebSocket Server
        self.ws_thread = threading.Thread(
            target=self._run_ws_server,
            daemon=True,
            name="ProctorWSServer"
        )
        self.ws_thread.start()
        logger.info(f"Proctor Real-Time WebSocket Server listening at: ws://localhost:{self.ws_port}")

    def stop(self) -> None:
        """Stops both HTTP and WebSocket servers cleanly."""
        self.is_running = False
        if self.http_server:
            try:
                self.http_server.shutdown()
                self.http_server.server_close()
            except Exception:
                pass
            self.http_server = None

        if self.ws_loop and self.ws_loop.is_running():
            if hasattr(self, "_ws_stop_event") and self._ws_stop_event:
                self.ws_loop.call_soon_threadsafe(self._ws_stop_event.set)
            else:
                self.ws_loop.call_soon_threadsafe(self.ws_loop.stop)

        logger.info("Proctor Web & WebSocket Bridge stopped.")

    def _run_ws_server(self) -> None:
        """Worker thread running asyncio event loop for websockets."""
        self.ws_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.ws_loop)

        async def _main():
            self._ws_stop_event = asyncio.Event()
            async with websockets.serve(self._ws_handler, self.http_host, self.ws_port) as ws_server:
                await self._ws_stop_event.wait()
                ws_server.close()
                await ws_server.wait_closed()

        try:
            self.ws_loop.run_until_complete(_main())
        except Exception as e:
            if self.is_running:
                logger.error(f"WebSocket loop error: {e}")
        finally:
            try:
                self.ws_loop.close()
            except Exception:
                pass

    async def _ws_handler(self, websocket: ServerConnection) -> None:
        """Handles incoming WebSocket connection from Proctor Web Dashboard."""
        with self._ws_lock:
            self._ws_clients.add(websocket)
        logger.info(f"Web Dashboard connected via WebSocket ({len(self._ws_clients)} dashboard clients).")

        # Send initial full state snapshot
        initial_payload = {
            "type": "INITIAL_STATE",
            "overview": self.get_overview_stats(),
            "sessions": self.get_sessions_list(),
            "violations": self.get_violations_list(limit=25),
            "submissions": self.get_submissions_list()
        }
        await websocket.send(json.dumps(initial_payload, ensure_ascii=False))

        try:
            async for raw_msg in websocket:
                try:
                    data = json.loads(raw_msg)
                    msg_type = data.get("type")
                    if msg_type == "MULTICAST_ACTION":
                        action = data.get("action", "").upper()
                        res = self.handle_multicast_action(action, data)
                        await websocket.send(json.dumps({"type": "ACTION_RESULT", "data": res}))
                    elif msg_type == "REFRESH_REQUEST":
                        refresh_data = {
                            "type": "REFRESH_UPDATE",
                            "overview": self.get_overview_stats(),
                            "sessions": self.get_sessions_list(),
                            "violations": self.get_violations_list(limit=25),
                            "submissions": self.get_submissions_list()
                        }
                        await websocket.send(json.dumps(refresh_data, ensure_ascii=False))
                except Exception as e:
                    logger.error(f"Error processing WS message: {e}")
        finally:
            with self._ws_lock:
                self._ws_clients.discard(websocket)
            logger.info("Web Dashboard disconnected from WebSocket.")

    def broadcast_ws(self, event_data: Dict[str, Any]) -> None:
        """
        Thread-safe broadcast of an event dictionary to all connected dashboard WebSockets.
        Can be called from any thread (TCP server worker, Watchdog, etc.).
        """
        if not self.ws_loop or not self.ws_loop.is_running():
            return

        with self._ws_lock:
            clients = list(self._ws_clients)

        if not clients:
            return

        payload_str = json.dumps(event_data, ensure_ascii=False)

        async def _async_send():
            for ws in clients:
                try:
                    await ws.send(payload_str)
                except Exception:
                    pass

        asyncio.run_coroutine_threadsafe(_async_send(), self.ws_loop)

    def get_overview_stats(self) -> Dict[str, Any]:
        """Calculates current KPI stats for top dashboard cards."""
        sessions = self.get_sessions_list()
        active_count = len(sessions)
        in_exam_count = sum(1 for s in sessions if s.get("status") == "IN_EXAM")

        exam = self.exam_repo.get_active_exam()
        exam_id = exam["id"] if exam else 1

        with self.sub_repo.db.read_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS total FROM submissions")
            sub_count = cursor.fetchone()["total"]

        with self.viol_repo.db.read_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS total FROM violation_logs")
            viol_count = cursor.fetchone()["total"]

        return {
            "active_students": active_count,
            "in_exam": in_exam_count,
            "submitted": sub_count,
            "total_violations": viol_count,
            "server_time_ms": get_current_timestamp_ms()
        }

    def get_sessions_list(self) -> list:
        """Returns list of currently active candidate sessions."""
        res = []
        now = time.time()
        with self.session_manager._lock:
            for s in self.session_manager._sessions_by_sock.values():
                res.append({
                    "student_id": s.student_id or "Chưa đăng nhập",
                    "student_name": s.student_name or "Anonymous",
                    "addr": f"{s.addr[0]}:{s.addr[1]}",
                    "status": s.status,
                    "violations_count": s.violations_count,
                    "connected_seconds": int(now - s.connected_at),
                    "last_heartbeat_ago": int(now - s.last_heartbeat)
                })
        return res

    def get_violations_list(self, limit: int = 30) -> list:
        """Returns recent AI proctoring violations with evidence links."""
        query = """
            SELECT v.id, v.student_id, s.full_name, v.violation_type, v.suspicion_score,
                   v.details, v.evidence_path, v.timestamp_ms
            FROM violation_logs v
            LEFT JOIN students s ON v.student_id = s.student_id
            ORDER BY v.timestamp_ms DESC
            LIMIT ?
        """
        with self.viol_repo.db.read_cursor() as cursor:
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()

        res = []
        for r in rows:
            ts = r["timestamp_ms"]
            res.append({
                "id": r["id"],
                "student_id": r["student_id"],
                "full_name": r["full_name"] or r["student_id"],
                "violation_type": r["violation_type"],
                "suspicion_score": r["suspicion_score"],
                "details": r["details"] or "",
                "evidence_url": f"/evidence/{r['evidence_path']}" if r["evidence_path"] else None,
                "timestamp_ms": ts,
                "time_str": time.strftime("%H:%M:%S", time.localtime(ts / 1000))
            })
        return res

    def get_submissions_list(self, limit: int = 50) -> list:
        """Returns list of verified submissions with RSA digital signatures."""
        query = """
            SELECT sub.id, sub.student_id, st.full_name, sub.sha256_hash,
                   sub.digital_signature, sub.server_receipt_signature, sub.submitted_at_ms, sub.status
            FROM submissions sub
            LEFT JOIN students st ON sub.student_id = st.student_id
            ORDER BY sub.submitted_at_ms DESC
            LIMIT ?
        """
        with self.sub_repo.db.read_cursor() as cursor:
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()

        res = []
        for r in rows:
            ts = r["submitted_at_ms"]
            c_sig = r["digital_signature"]
            s_sig = r["server_receipt_signature"]
            res.append({
                "id": r["id"],
                "student_id": r["student_id"],
                "full_name": r["full_name"] or r["student_id"],
                "sha256_hash": r["sha256_hash"],
                "client_sig_preview": f"{c_sig[:24]}...{c_sig[-12:]}" if len(c_sig) > 36 else c_sig,
                "server_sig_preview": f"{s_sig[:24]}...{s_sig[-12:]}" if len(s_sig) > 36 else s_sig,
                "submitted_at_ms": ts,
                "time_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts / 1000)),
                "status": r["status"]
            })
        return res

    def handle_multicast_action(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Executes UDP Multicast exam commands across the local network."""
        logger.info(f"📢 Web Dashboard requested UDP Multicast action: {action}")
        try:
            if action == "START":
                duration = payload.get("duration_minutes", 60)
                self.multicast_sender.start_exam(duration_minutes=duration)
                msg = f"Đã phát lệnh BẮT ĐẦU THI ({duration} phút) tới toàn bộ phòng thi!"
            elif action == "PAUSE":
                reason = payload.get("reason", "Giám thị tạm dừng kiểm tra")
                self.multicast_sender.pause_exam(reason=reason)
                msg = "Đã phát lệnh TẠM DỪNG KHẨN CẤP tới toàn bộ phòng thi!"
            elif action == "RESUME":
                added = payload.get("added_minutes", 0)
                self.multicast_sender.resume_exam(added_minutes=added)
                msg = "Đã phát lệnh TIẾP TỤC BÀI THI tới toàn bộ phòng thi!"
            elif action == "FORCE_SUBMIT":
                self.multicast_sender.finish_exam(message="HẾT GIỜ! Giám thị yêu cầu thu bài đồng loạt.")
                msg = "Đã phát lệnh THU BÀI ĐỒNG LOẠT tới toàn bộ phòng thi!"
            elif action == "ANNOUNCEMENT":
                text = payload.get("message", "")
                self.multicast_sender.send_announcement(text)
                msg = f"Đã gửi thông báo: {text}"
            else:
                return {"success": False, "error": f"Lệnh không hợp lệ: {action}"}

            # Broadcast command update to all connected dashboards
            broadcast_event = {
                "type": "MULTICAST_DISPATCHED",
                "action": action,
                "message": msg,
                "timestamp_ms": get_current_timestamp_ms()
            }
            self.broadcast_ws(broadcast_event)
            return {"success": True, "message": msg, "action": action}
        except Exception as e:
            logger.error(f"Failed to execute multicast action: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
