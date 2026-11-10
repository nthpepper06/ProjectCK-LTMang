"""
Secure Examination & Proctoring Platform
server/tcp_server.py - Multi-Thread TCP Examination Server
"""

import json
import logging
import os
import socket
import sys
import threading
import time
from typing import Any, Dict, Optional

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common.crypto_utils import (
    compute_sha256,
    generate_rsa_keypair,
    sign_data,
    verify_signature,
)
from common.protocol import (
    CommandType,
    get_current_timestamp_ms,
    pack_packet,
    recv_packet,
    send_packet,
)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(threadName)s] %(message)s"
)
logger = logging.getLogger("ExamTCPServer")


class StudentSession:
    """Represents an active candidate connection and cryptographic state."""

    def __init__(self, student_id: str, student_name: str, public_key_pem: str, sock: socket.socket, addr: tuple):
        self.student_id = student_id
        self.student_name = student_name
        self.public_key_pem = public_key_pem.encode("utf-8") if isinstance(public_key_pem, str) else public_key_pem
        self.sock = sock
        self.addr = addr
        self.connected_at = time.time()
        self.last_heartbeat = time.time()
        self.is_authenticated = False
        self.status = "CONNECTED"  # CONNECTED, IN_EXAM, SUBMITTED, DISCONNECTED
        self.violations_count = 0


class ExamTCPServer:
    """
    Multi-threaded TCP Server managing student connections, real-time proctoring telemetry,
    and anti-repudiation digital signature verification upon exam submission.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8888, evidence_dir: str = "server_storage/evidence"):
        self.host = host
        self.port = port
        self.evidence_dir = evidence_dir
        os.makedirs(self.evidence_dir, exist_ok=True)
        os.makedirs("server_storage/submissions", exist_ok=True)

        # Generate or load Server RSA Keypair for official countersignatures
        logger.info("Initializing Server RSA 2048-bit Keypair...")
        self.server_private_key, self.server_public_key = generate_rsa_keypair(2048)

        self.server_sock: Optional[socket.socket] = None
        self.is_running = False

        # Thread-safe session tracking
        self.sessions_lock = threading.Lock()
        self.sessions: Dict[str, StudentSession] = {}  # student_id -> StudentSession
        self.sock_to_student: Dict[socket.socket, str] = {}

        # Default sample exam paper
        self.exam_paper = {
            "exam_id": "LTM_2026_FINAL",
            "title": "Kỳ thi Cuối kỳ Lập trình Mạng & An toàn Hệ thống",
            "duration_minutes": 60,
            "questions": [
                {
                    "id": 1,
                    "question": "Giao thức TCP và UDP khác nhau cơ bản ở điểm nào trong việc kiểm soát luồng và độ tin cậy?",
                    "type": "essay"
                },
                {
                    "id": 2,
                    "question": "Tại sao UDP Multicast được ưu tiên sử dụng để phát thông điệp đồng loạt trong mạng cục bộ thay vì gửi nhiều gói tin Unicast TCP?",
                    "type": "essay"
                },
                {
                    "id": 3,
                    "question": "Chữ ký số (Digital Signature) kết hợp giữa thuật toán hàm băm SHA-256 và RSA giải quyết được những bài toán an ninh thông tin nào?",
                    "type": "essay"
                }
            ]
        }

    def start(self) -> None:
        """Starts listening for incoming client connections."""
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen(100)
        self.is_running = True

        logger.info(f"Exam TCP Server running on {self.host}:{self.port}")

        # Start background heartbeat watchdog thread
        watchdog = threading.Thread(target=self._heartbeat_watchdog, daemon=True, name="HeartbeatWatchdog")
        watchdog.start()

        try:
            while self.is_running:
                try:
                    client_sock, client_addr = self.server_sock.accept()
                except OSError:
                    if not self.is_running:
                        break
                    raise
                logger.info(f"Accepted new connection from {client_addr}")
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_sock, client_addr),
                    daemon=True,
                    name=f"Client-{client_addr[0]}:{client_addr[1]}"
                )
                client_thread.start()
        except KeyboardInterrupt:
            logger.info("Server interrupted by user.")
        finally:
            self.stop()

    def stop(self) -> None:
        """Stops the server and closes all active sockets."""
        self.is_running = False
        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass
        with self.sessions_lock:
            for s in self.sessions.values():
                try:
                    s.sock.close()
                except Exception:
                    pass
            self.sessions.clear()
            self.sock_to_student.clear()
        logger.info("Exam TCP Server stopped cleanly.")

    def _handle_client(self, sock: socket.socket, addr: tuple) -> None:
        """Dedicated worker thread loop servicing one candidate connection."""
        student_id: Optional[str] = None
        try:
            while self.is_running:
                header, payload = recv_packet(sock)
                cmd = header["cmd"]

                # 1. Connection & Initial Handshake
                if cmd == CommandType.REQ_CONNECT:
                    student_id = self._handle_req_connect(sock, addr, payload)

                # 2. Biometric Authentication
                elif cmd == CommandType.REQ_AUTH_BIOMETRIC:
                    self._handle_req_auth(sock, student_id, payload)

                # 3. Heartbeat PING
                elif cmd == CommandType.PING:
                    self._handle_ping(sock, student_id, payload)

                # 4. Request Exam Paper
                elif cmd == CommandType.REQ_EXAM_PAPER:
                    self._handle_req_paper(sock, student_id)

                # 5. Proctoring Violation Report
                elif cmd == CommandType.REPORT_VIOLATION:
                    self._handle_report_violation(sock, student_id, payload)

                # 6. Exam Paper Submission with RSA Signature
                elif cmd == CommandType.SUBMIT_EXAM_PAPER:
                    self._handle_submit_exam(sock, student_id, payload)

                # 7. Disconnect
                elif cmd == CommandType.DISCONNECT:
                    logger.info(f"Student {student_id} explicitly requested disconnect.")
                    break

                else:
                    logger.warning(f"Unrecognized command: 0x{cmd:04X} from {addr}")

        except (ConnectionResetError, ConnectionAbortedError):
            logger.warning(f"Client disconnected abruptly: {addr} (Student: {student_id})")
        except Exception as e:
            logger.error(f"Error handling client {addr} (Student: {student_id}): {e}", exc_info=True)
        finally:
            self._cleanup_session(sock, student_id)

    def _handle_req_connect(self, sock: socket.socket, addr: tuple, payload: Dict[str, Any]) -> str:
        s_id = payload.get("student_id", "UNKNOWN")
        s_name = payload.get("student_name", "Anonymous")
        public_key_pem = payload.get("public_key_pem", "")

        logger.info(f"Student Registration: ID={s_id}, Name={s_name} from {addr}")

        session = StudentSession(s_id, s_name, public_key_pem, sock, addr)
        with self.sessions_lock:
            self.sessions[s_id] = session
            self.sock_to_student[sock] = s_id

        # Respond with Server's Public Key for mutual authentication
        res = {
            "status": "OK",
            "server_time_ms": get_current_timestamp_ms(),
            "server_public_key_pem": self.server_public_key.decode("utf-8"),
            "message": "Connection established. Awaiting biometric verification."
        }
        send_packet(sock, CommandType.RES_CONNECT_OK, res)
        return s_id

    def _handle_req_auth(self, sock: socket.socket, student_id: Optional[str], payload: Dict[str, Any]) -> None:
        """Biometric face authentication handler."""
        # Simulated Face Embedding Match (In production, compared with DB registered embedding)
        face_match_score = payload.get("match_confidence", 0.95)
        is_success = face_match_score >= 0.70

        if student_id and student_id in self.sessions:
            self.sessions[student_id].is_authenticated = is_success
            if is_success:
                self.sessions[student_id].status = "IN_EXAM"

        res = {
            "success": is_success,
            "confidence": face_match_score,
            "message": "Biometric face verification successful." if is_success else "Biometric mismatch."
        }
        cmd = CommandType.RES_AUTH_SUCCESS if is_success else CommandType.RES_AUTH_FAILED
        send_packet(sock, cmd, res)
        logger.info(f"Biometric auth for {student_id}: {'PASSED' if is_success else 'FAILED'}")

    def _handle_ping(self, sock: socket.socket, student_id: Optional[str], payload: Dict[str, Any]) -> None:
        """Responds to heartbeat PING with PONG and server timestamp for clock synchronization."""
        if student_id and student_id in self.sessions:
            self.sessions[student_id].last_heartbeat = time.time()

        res = {
            "server_timestamp_ms": get_current_timestamp_ms(),
            "echo": payload.get("seq", 0)
        }
        send_packet(sock, CommandType.PONG, res)

    def _handle_req_paper(self, sock: socket.socket, student_id: Optional[str]) -> None:
        """Sends the exam questions paper to the authenticated student."""
        send_packet(sock, CommandType.RES_EXAM_PAPER, self.exam_paper)
        logger.info(f"Dispatched exam paper to student {student_id}")

    def _handle_report_violation(self, sock: socket.socket, student_id: Optional[str], payload: Dict[str, Any]) -> None:
        """Records AI proctoring violations and saves snapshot evidence."""
        v_type = payload.get("violation_type", "UNKNOWN")
        v_detail = payload.get("details", "")
        v_time = payload.get("timestamp_ms", get_current_timestamp_ms())
        evidence_b64 = payload.get("evidence_image_b64")

        evidence_filename = None
        if evidence_b64:
            import base64
            evidence_filename = f"{student_id}_{v_type}_{v_time}.jpg"
            file_path = os.path.join(self.evidence_dir, evidence_filename)
            try:
                with open(file_path, "wb") as f:
                    f.write(base64.b64decode(evidence_b64))
            except Exception as e:
                logger.error(f"Failed to write evidence snapshot: {e}")

        if student_id and student_id in self.sessions:
            self.sessions[student_id].violations_count += 1

        logger.warning(
            f"🚨 [VIOLATION ALERT] Student {student_id}: Type={v_type}, Details={v_detail}, Evidence={evidence_filename}"
        )

        send_packet(sock, CommandType.VIOLATION_ACK, {"status": "LOGGED", "timestamp_ms": v_time})

    def _handle_submit_exam(self, sock: socket.socket, student_id: Optional[str], payload: Dict[str, Any]) -> None:
        """
        Validates digital signature on submitted paper and returns a signed receipt (Non-repudiation).
        """
        s_id = payload.get("student_id", student_id)
        exam_id = payload.get("exam_id")
        answers = payload.get("answers", {})
        client_signature = payload.get("signature")
        paper_hash = payload.get("paper_hash")

        # 1. Serialize answers deterministically to compute SHA-256
        answers_canonical_bytes = json.dumps(answers, sort_keys=True).encode("utf-8")
        server_computed_hash = compute_sha256(answers_canonical_bytes)

        if server_computed_hash != paper_hash:
            logger.error(f"Hash mismatch for submission of {s_id}: client={paper_hash}, server={server_computed_hash}")
            send_packet(sock, CommandType.SUBMIT_ACK, {
                "success": False,
                "error": "INTEGRITY_CHECK_FAILED: Hash mismatch."
            })
            return

        # 2. Retrieve student public key and verify signature
        session = self.sessions.get(s_id)
        if not session or not session.public_key_pem:
            logger.error(f"No public key available for student {s_id}")
            send_packet(sock, CommandType.SUBMIT_ACK, {
                "success": False,
                "error": "AUTHENTICATION_FAILED: Public key not registered."
            })
            return

        is_valid_sig = verify_signature(session.public_key_pem, answers_canonical_bytes, client_signature)
        if not is_valid_sig:
            logger.error(f"Invalid digital signature from student {s_id}!")
            send_packet(sock, CommandType.SUBMIT_ACK, {
                "success": False,
                "error": "SIGNATURE_VERIFICATION_FAILED: Digital signature invalid."
            })
            return

        # 3. Issue official timestamped Server Receipt with Server RSA signature
        submission_time = get_current_timestamp_ms()
        receipt = {
            "receipt_id": f"REC_{s_id}_{submission_time}",
            "student_id": s_id,
            "exam_id": exam_id,
            "paper_hash": server_computed_hash,
            "submitted_at_ms": submission_time,
            "status": "CONFIRMED_AND_STORED"
        }
        receipt_bytes = json.dumps(receipt, sort_keys=True).encode("utf-8")
        server_signature = sign_data(self.server_private_key, receipt_bytes)

        # Save submission record to disk
        sub_file = f"server_storage/submissions/{s_id}_{exam_id}.json"
        with open(sub_file, "w", encoding="utf-8") as f:
            json.dump({
                "submission": payload,
                "server_receipt": receipt,
                "server_signature": server_signature
            }, f, indent=2, ensure_ascii=False)

        if session:
            session.status = "SUBMITTED"

        logger.info(f"✅ Exam submission for {s_id} successfully verified and countersigned! Receipt={receipt['receipt_id']}")

        send_packet(sock, CommandType.SUBMIT_ACK, {
            "success": True,
            "receipt": receipt,
            "server_signature": server_signature,
            "message": "Bài nộp đã được kiểm tra chữ ký số thành công và lưu trữ bảo mật."
        })

    def _heartbeat_watchdog(self) -> None:
        """Periodically detects dead or silent student connections."""
        while self.is_running:
            time.sleep(5)
            now = time.time()
            with self.sessions_lock:
                for s_id, s in list(self.sessions.items()):
                    if now - s.last_heartbeat > 20 and s.status != "SUBMITTED":
                        logger.warning(f"Student {s_id} missed heartbeats (Last seen {now - s.last_heartbeat:.1f}s ago).")

    def _cleanup_session(self, sock: socket.socket, student_id: Optional[str]) -> None:
        try:
            sock.close()
        except Exception:
            pass
        with self.sessions_lock:
            if student_id and student_id in self.sessions:
                self.sessions[student_id].status = "DISCONNECTED"
            if sock in self.sock_to_student:
                del self.sock_to_student[sock]


if __name__ == "__main__":
    server = ExamTCPServer(host="0.0.0.0", port=8888)
    server.start()
