"""
Secure Examination & Proctoring Platform
server/handlers/socket_handler.py - Packet Router & Client Request Handler
Processes framed protocol byte-streams, routes commands to domain services, and replies with structured status codes.
"""

import base64
import logging
import socket
from typing import Any, Dict, Optional, Tuple

from common.protocol import (
    CommandType,
    get_current_timestamp_ms,
    recv_packet,
    send_packet,
)
from server.core.session_manager import ClientSession, SessionManager
from server.services.audit_service import AuditService
from server.services.auth_service import AuthService
from server.services.exam_service import ExamService

logger = logging.getLogger("SOCKET_HANDLER")


class SocketHandler:
    """
    Dedicated Request Router servicing candidate TCP socket connections.
    Decodes 23-byte binary headers, unpacks payloads, delegates business logic to Services,
    and returns protocol-compliant responses.
    """

    def __init__(
        self,
        session_manager: SessionManager,
        auth_service: AuthService,
        exam_service: ExamService,
        audit_service: AuditService,
        server_public_key_pem: bytes,
        web_bridge: Optional[Any] = None,
    ):
        self.session_manager = session_manager
        self.auth_service = auth_service
        self.exam_service = exam_service
        self.audit_service = audit_service
        self.server_public_key_pem = server_public_key_pem
        self.web_bridge = web_bridge

    def handle_connection(self, sock: socket.socket, addr: Tuple[str, int]) -> None:
        """
        Main worker loop servicing a candidate's continuous TCP connection.
        Runs inside a thread pool worker until socket closure or disconnect.
        """
        session: ClientSession = self.session_manager.register_session(sock, addr)
        student_id: Optional[str] = None
        student_name: Optional[str] = None

        try:
            while True:
                # 1. Framing & Packet Reception
                header, payload = recv_packet(sock)
                cmd = header["cmd"]

                # 2. Command Dispatching (Router)
                if cmd == CommandType.REQ_CONNECT:
                    student_id = payload.get("student_id", "UNKNOWN")
                    student_name = payload.get("student_name", "Anonymous")
                    pub_key = payload.get("public_key_pem", "")

                    session.student_id = student_id
                    session.student_name = student_name
                    session.public_key_pem = pub_key

                    # Persist / update student public key in DB
                    self.auth_service.student_repo.create_student(
                        student_id=student_id,
                        full_name=student_name,
                        rsa_public_key=pub_key
                    )

                    res = {
                        "status": "OK",
                        "server_time_ms": get_current_timestamp_ms(),
                        "server_public_key_pem": self.server_public_key_pem.decode("utf-8"),
                        "message": "Connection established. Awaiting biometric verification."
                    }
                    send_packet(sock, CommandType.RES_CONNECT_OK, res)

                elif cmd == CommandType.REQ_AUTH_BIOMETRIC:
                    s_id = payload.get("student_id", student_id or "UNKNOWN")
                    confidence = payload.get("match_confidence", 0.95)
                    face_emb = payload.get("face_embedding")

                    ok, token, msg = self.auth_service.authenticate_student(
                        student_id=s_id,
                        student_name=student_name or s_id,
                        public_key_pem=session.public_key_pem,
                        face_embedding_bytes=face_emb,
                        match_confidence=confidence
                    )

                    if ok:
                        self.session_manager.authenticate_session(
                            sock=sock,
                            student_id=s_id,
                            student_name=student_name or s_id,
                            public_key_pem=session.public_key_pem,
                            token=token or ""
                        )
                        student_id = s_id
                        res = {
                            "success": True,
                            "confidence": confidence,
                            "session_token": token,
                            "message": msg
                        }
                        send_packet(sock, CommandType.RES_AUTH_SUCCESS, res)

                        if self.web_bridge:
                            self.web_bridge.broadcast_ws({
                                "type": "SESSION_UPDATE",
                                "sessions": self.web_bridge.get_sessions_list(),
                                "overview": self.web_bridge.get_overview_stats()
                            })
                    else:
                        res = {
                            "success": False,
                            "confidence": confidence,
                            "message": msg
                        }
                        send_packet(sock, CommandType.RES_AUTH_FAILED, res)

                elif cmd == CommandType.REQ_AUTH_LOGIN:
                    u_name = payload.get("username", "").strip()
                    pwd = payload.get("password", "")
                    ok, token, role, full_name, msg = self.auth_service.authenticate_user(u_name, pwd)
                    if ok:
                        session.student_id = u_name
                        session.student_name = full_name
                        session.role = role
                        self.session_manager.authenticate_session(
                            sock=sock,
                            student_id=u_name,
                            student_name=full_name or u_name,
                            public_key_pem=session.public_key_pem,
                            token=token or ""
                        )
                        student_id = u_name
                        student_name = full_name
                        res = {
                            "status": "SUCCESS",
                            "token": token,
                            "role": role,
                            "full_name": full_name,
                            "message": msg
                        }
                        send_packet(sock, CommandType.RES_AUTH_SUCCESS, res)

                        if self.web_bridge:
                            self.web_bridge.broadcast_ws({
                                "type": "SESSION_UPDATE",
                                "sessions": self.web_bridge.get_sessions_list(),
                                "overview": self.web_bridge.get_overview_stats()
                            })
                    else:
                        res = {
                            "status": "FAILED",
                            "message": msg
                        }
                        send_packet(sock, CommandType.RES_AUTH_FAILED, res)

                elif cmd == CommandType.REQ_AUTH_REGISTER:
                    u_name = payload.get("username", "").strip()
                    pwd = payload.get("password", "")
                    f_name = payload.get("full_name", "").strip()
                    r_name = payload.get("role", "STUDENT").strip()
                    email = payload.get("email")
                    face_b64 = payload.get("face_image_b64")
                    face_bytes = None
                    if face_b64:
                        try:
                            face_bytes = base64.b64decode(face_b64)
                        except Exception:
                            pass
                    ok, user_id, msg = self.auth_service.register_user(
                        username=u_name,
                        password=pwd,
                        full_name=f_name,
                        role_name=r_name,
                        email=email,
                        face_embedding=face_bytes
                    )
                    if ok:
                        send_packet(sock, CommandType.RES_CONNECT_OK, {
                            "status": "SUCCESS",
                            "user_id": user_id,
                            "message": msg
                        })
                    else:
                        send_packet(sock, CommandType.RES_AUTH_FAILED, {
                            "status": "FAILED",
                            "message": msg
                        })

                elif cmd == CommandType.PING:
                    self.session_manager.update_heartbeat(sock)
                    res = {
                        "server_timestamp_ms": get_current_timestamp_ms(),
                        "echo": payload.get("seq", 0)
                    }
                    send_packet(sock, CommandType.PONG, res)

                elif cmd == CommandType.REQ_EXAM_PAPER:
                    paper = self.exam_service.fetch_exam_paper(
                        student_id=student_id or "ANONYMOUS",
                        exam_code=payload.get("exam_id")
                    )
                    if paper:
                        session.status = "IN_EXAM"
                        send_packet(sock, CommandType.RES_EXAM_PAPER, paper)
                        if self.web_bridge:
                            self.web_bridge.broadcast_ws({
                                "type": "SESSION_UPDATE",
                                "sessions": self.web_bridge.get_sessions_list(),
                                "overview": self.web_bridge.get_overview_stats()
                            })
                    else:
                        send_packet(sock, CommandType.RES_EXAM_PAPER, {"error": "Exam paper not found."})

                elif cmd == CommandType.REPORT_VIOLATION:
                    v_type = payload.get("violation_type", "UNKNOWN")
                    v_detail = payload.get("details", "")
                    evidence_b64 = payload.get("evidence_image_b64")
                    v_time = payload.get("timestamp_ms", get_current_timestamp_ms())
                    score = payload.get("suspicion_score", 1.0)

                    ack_res = self.audit_service.log_violation(
                        student_id=student_id or "ANONYMOUS",
                        exam_code=payload.get("exam_id"),
                        violation_type=v_type,
                        suspicion_score=score,
                        details=v_detail,
                        evidence_b64=evidence_b64,
                        timestamp_ms=v_time
                    )
                    send_packet(sock, CommandType.VIOLATION_ACK, ack_res)

                elif cmd == CommandType.SUBMIT_EXAM_PAPER:
                    s_id = payload.get("student_id", student_id or "ANONYMOUS")
                    exam_id = payload.get("exam_id", "LTM_2026_FINAL")
                    answers = payload.get("answers", {})
                    client_sig = payload.get("signature", "")
                    p_hash = payload.get("paper_hash", "")

                    ok, receipt, server_sig, c_sig, msg = self.exam_service.submit_exam(
                        student_id=s_id,
                        exam_code=exam_id,
                        answers=answers,
                        client_signature=client_sig,
                        paper_hash=p_hash
                    )

                    if ok:
                        session.status = "SUBMITTED"
                        send_packet(sock, CommandType.SUBMIT_ACK, {
                            "success": True,
                            "receipt": receipt,
                            "server_signature": server_sig,
                            "student_signature": c_sig,
                            "message": msg
                        })
                        if self.web_bridge:
                            self.web_bridge.broadcast_ws({
                                "type": "NEW_SUBMISSION",
                                "data": {
                                    "student_id": s_id,
                                    "student_name": session.student_name or s_id,
                                    "sha256_hash": p_hash,
                                    "client_sig_preview": f"{c_sig[:24]}...{c_sig[-12:]}" if len(c_sig) > 36 else c_sig,
                                    "server_sig_preview": f"{server_sig[:24]}...{server_sig[-12:]}" if len(server_sig) > 36 else server_sig,
                                    "submitted_at_ms": get_current_timestamp_ms(),
                                    "status": "VERIFIED_RSA"
                                },
                                "overview": self.web_bridge.get_overview_stats(),
                                "sessions": self.web_bridge.get_sessions_list(),
                                "submissions": self.web_bridge.get_submissions_list()
                            })
                    else:
                        send_packet(sock, CommandType.SUBMIT_ACK, {
                            "success": False,
                            "error": msg
                        })

                elif cmd == CommandType.DISCONNECT:
                    logger.info(f"Student {student_id} explicitly requested disconnect.")
                    break

        except (ConnectionResetError, EOFError, BrokenPipeError, TimeoutError):
            logger.info(f"Client disconnected abruptly from {addr} (Student: {student_id}).")
        except Exception as e:
            logger.error(f"Error servicing connection from {addr} (Student: {student_id}): {e}", exc_info=True)
        finally:
            self.session_manager.remove_session(sock)
            if self.web_bridge:
                self.web_bridge.broadcast_ws({
                    "type": "SESSION_UPDATE",
                    "sessions": self.web_bridge.get_sessions_list(),
                    "overview": self.web_bridge.get_overview_stats()
                })
