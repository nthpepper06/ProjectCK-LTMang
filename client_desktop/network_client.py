"""
Secure Examination & Proctoring Platform
client_desktop/network_client.py - TCP Exam Network Client with Digital Signature Support
"""

import base64
import json
import logging
import os
import socket
import sys
import threading
import time
from typing import Any, Callable, Dict, Optional

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
    recv_packet,
    send_packet,
)

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [NETWORK CLIENT] %(message)s")
logger = logging.getLogger("NetworkClient")


class NetworkClient:
    """
    Handles TCP communication with ExamTCPServer:
    - Candidate authentication and RSA 2048 key exchange
    - Periodic heartbeat PING
    - Telemetry and AI violation reporting
    - Anti-repudiation paper submission with RSA digital signatures
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8888, student_id: str = "SV2026_01", student_name: str = "Nguyen Van A"):
        self.host = host
        self.port = port
        self.student_id = student_id
        self.student_name = student_name

        logger.info(f"Generating candidate RSA 2048-bit keypair for {student_id}...")
        self.private_key_pem, self.public_key_pem = generate_rsa_keypair(2048)

        self.server_public_key_pem: Optional[str] = None
        self.sock: Optional[socket.socket] = None
        self.is_connected = False
        self.is_authenticated = False

        self.heartbeat_thread: Optional[threading.Thread] = None
        self.recv_thread: Optional[threading.Thread] = None
        self.on_server_message: Optional[Callable[[dict, Any], None]] = None

        # Lock to ensure atomic send operations
        self.send_lock = threading.Lock()

    def connect(self) -> bool:
        """Establishes TCP connection and performs cryptographic handshake."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            self.is_connected = True
            logger.info(f"Connected to Exam TCP Server at {self.host}:{self.port}")

            # Send REQ_CONNECT with candidate credentials and Public Key
            connect_payload = {
                "student_id": self.student_id,
                "student_name": self.student_name,
                "public_key_pem": self.public_key_pem.decode("utf-8")
            }
            with self.send_lock:
                send_packet(self.sock, CommandType.REQ_CONNECT, connect_payload)

            header, res = recv_packet(self.sock)
            if header["cmd"] == CommandType.RES_CONNECT_OK:
                self.server_public_key_pem = res.get("server_public_key_pem")
                logger.info(f"Handshake successful. Server time: {res.get('server_time_ms')}")

                # Start heartbeat thread
                self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True, name="HeartbeatWorker")
                self.heartbeat_thread.start()
                return True
            else:
                logger.error(f"Handshake rejected: {res}")
                return False

        except Exception as e:
            logger.error(f"Failed to connect to server: {e}")
            self.disconnect()
            return False

    def authenticate_biometric(self, face_embedding_confidence: float = 0.95) -> bool:
        """Sends biometric face match score to the server for exam room admission."""
        if not self.is_connected or not self.sock:
            return False

        auth_payload = {
            "student_id": self.student_id,
            "match_confidence": face_embedding_confidence,
            "timestamp_ms": get_current_timestamp_ms()
        }
        with self.send_lock:
            send_packet(self.sock, CommandType.REQ_AUTH_BIOMETRIC, auth_payload)

        header, res = recv_packet(self.sock)
        self.is_authenticated = (header["cmd"] == CommandType.RES_AUTH_SUCCESS)
        logger.info(f"Biometric Admission Result: {res.get('message')}")
        return self.is_authenticated

    def request_exam_paper(self) -> Optional[dict]:
        """Fetches the official exam questions paper from the server."""
        if not self.is_connected or not self.sock:
            return None

        with self.send_lock:
            send_packet(self.sock, CommandType.REQ_EXAM_PAPER, {"student_id": self.student_id})

        header, paper = recv_packet(self.sock)
        if header["cmd"] == CommandType.RES_EXAM_PAPER:
            logger.info(f"Exam paper received: {paper.get('title')} ({len(paper.get('questions', []))} questions)")
            return paper
        return None

    def report_violation(self, violation_type: str, details: str, evidence_image_bytes: Optional[bytes] = None) -> None:
        """Transmits AI-detected cheating behavior and webcam snapshot to the server."""
        if not self.is_connected or not self.sock:
            return

        evidence_b64 = None
        if evidence_image_bytes:
            evidence_b64 = base64.b64encode(evidence_image_bytes).decode("ascii")

        payload = {
            "student_id": self.student_id,
            "violation_type": violation_type,
            "details": details,
            "evidence_image_b64": evidence_b64,
            "timestamp_ms": get_current_timestamp_ms()
        }
        try:
            with self.send_lock:
                send_packet(self.sock, CommandType.REPORT_VIOLATION, payload)
                # Receive ACK to maintain request-reply synchronization
                recv_packet(self.sock)
        except Exception as e:
            logger.error(f"Failed to report violation: {e}")

    def submit_exam_paper(self, exam_id: str, answers: Dict[str, Any]) -> Dict[str, Any]:
        """
        Signs student answers with candidate's RSA Private Key (SHA-256 + PSS)
        and submits to the Server for non-repudiation verification.
        """
        if not self.is_connected or not self.sock:
            return {"success": False, "error": "Not connected to server"}

        # 1. Deterministic canonical serialization of answers
        answers_canonical_bytes = json.dumps(answers, sort_keys=True).encode("utf-8")
        paper_hash = compute_sha256(answers_canonical_bytes)

        # 2. Generate RSA digital signature
        logger.info("Computing SHA-256 hash and signing submission with RSA Private Key...")
        signature_b64 = sign_data(self.private_key_pem, answers_canonical_bytes)

        submission_payload = {
            "student_id": self.student_id,
            "exam_id": exam_id,
            "answers": answers,
            "paper_hash": paper_hash,
            "signature": signature_b64,
            "submitted_at_ms": get_current_timestamp_ms()
        }

        with self.send_lock:
            send_packet(self.sock, CommandType.SUBMIT_EXAM_PAPER, submission_payload)

        header, res = recv_packet(self.sock)
        if header["cmd"] == CommandType.SUBMIT_ACK:
            if res.get("success"):
                logger.info("✅ Submission ACCEPTED & VERIFIED by Exam Server!")
                # Validate server countersignature if provided
                if self.server_public_key_pem and "server_signature" in res:
                    receipt = res["receipt"]
                    receipt_bytes = json.dumps(receipt, sort_keys=True).encode("utf-8")
                    valid_server = verify_signature(
                        self.server_public_key_pem.encode("utf-8"),
                        receipt_bytes,
                        res["server_signature"]
                    )
                    logger.info(f"Server counter-signature verification: {'VALID' if valid_server else 'INVALID'}")
            else:
                logger.error(f"❌ Submission REJECTED by Server: {res.get('error')}")
            return res

        return {"success": False, "error": "Unexpected server response"}

    def _heartbeat_loop(self) -> None:
        """Sends periodic PING to ensure connection vitality."""
        seq = 1
        while self.is_connected and self.sock:
            time.sleep(5)
            try:
                with self.send_lock:
                    send_packet(self.sock, CommandType.PING, {"seq": seq})
                    recv_packet(self.sock)  # Consume PONG
                seq += 1
            except Exception:
                logger.warning("Heartbeat send failed.")
                break

    def disconnect(self) -> None:
        """Gracefully disconnects from the exam server."""
        self.is_connected = False
        if self.sock:
            try:
                with self.send_lock:
                    send_packet(self.sock, CommandType.DISCONNECT, {"student_id": self.student_id})
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        logger.info("Disconnected from Exam TCP Server.")
