"""
Secure Examination & Proctoring Platform
server/tcp_server.py - Multi-Threaded TCP Server Entry Point
Uses ThreadPoolExecutor for client connection pooling, delegates protocol routing to SocketHandler,
and coordinates layered backend services (SessionManager, AuthService, ExamService, AuditService).
"""

import logging
import os
import socket
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common.crypto_utils import generate_rsa_keypair
from server.core.session_manager import ClientSession, SessionManager, get_session_manager
from server.database.connection import DatabaseConnectionManager, get_db_manager
from server.database.repositories import (
    ExamRepository,
    StudentRepository,
    SubmissionRepository,
    ViolationRepository,
)
from server.handlers.socket_handler import SocketHandler
from server.services.audit_service import AuditService
from server.services.auth_service import AuthService
from server.services.exam_service import ExamService

logger = logging.getLogger("TCP_SERVER")
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(name)s] %(message)s"
    )


class ExamTCPServer:
    """
    Production-ready Multi-Threaded TCP Server using Layered Architecture:
    TCP Listener -> ThreadPoolExecutor -> SocketHandler -> Services -> Repositories.
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8888,
        max_workers: int = 50,
        evidence_dir: str = "server_storage/evidence",
        db_path: Optional[str] = None,
    ):
        self.host = host
        self.port = port
        self.max_workers = max_workers
        self.evidence_dir = evidence_dir
        os.makedirs(self.evidence_dir, exist_ok=True)
        os.makedirs("server_storage/submissions", exist_ok=True)

        # 1. Initialize Server RSA-2048 Keypair for Official Countersignatures
        logger.info("Initializing Server RSA 2048-bit Keypair...")
        self.server_private_key, self.server_public_key = generate_rsa_keypair(2048)

        # 2. Initialize Database Layer
        self.db_manager = get_db_manager(db_path) if db_path else get_db_manager()
        self.db_manager.init_database()
        self.student_repo = StudentRepository(self.db_manager)
        self.exam_repo = ExamRepository(self.db_manager)
        self.sub_repo = SubmissionRepository(self.db_manager)
        self.viol_repo = ViolationRepository(self.db_manager)

        # 3. Initialize Core Session Management
        self.session_manager = get_session_manager(heartbeat_timeout_seconds=15.0)

        # 4. Initialize Domain Services
        self.auth_service = AuthService(self.student_repo)
        self.exam_service = ExamService(
            exam_repo=self.exam_repo,
            sub_repo=self.sub_repo,
            student_repo=self.student_repo,
            server_private_key_pem=self.server_private_key
        )
        self.audit_service = AuditService(
            viol_repo=self.viol_repo,
            exam_repo=self.exam_repo,
            evidence_dir=self.evidence_dir
        )

        # 5. Initialize Socket Handler (Packet Router)
        self.socket_handler = SocketHandler(
            session_manager=self.session_manager,
            auth_service=self.auth_service,
            exam_service=self.exam_service,
            audit_service=self.audit_service,
            server_public_key_pem=self.server_public_key
        )

        # 6. Thread Pool Executor for Connection Concurrency
        self.thread_pool = ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="ClientWorker"
        )
        self.server_sock: Optional[socket.socket] = None
        self.is_running = False

    @property
    def sessions(self) -> Dict[str, ClientSession]:
        """Provides backwards-compatible read access to active student sessions."""
        return self.session_manager._sessions_by_student_id

    def start(self) -> None:
        """Starts TCP Server listener and dispatches connections into the thread pool."""
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen(100)
        self.is_running = True

        logger.info(f"Exam TCP Server running on {self.host}:{self.port} (ThreadPool: {self.max_workers} workers)")
        self.session_manager.start_watchdog()

        try:
            while self.is_running:
                try:
                    client_sock, client_addr = self.server_sock.accept()
                except OSError:
                    if not self.is_running:
                        break
                    raise

                logger.info(f"Accepted new connection from {client_addr}")
                # Dispatch connection handling to ThreadPoolExecutor
                self.thread_pool.submit(self.socket_handler.handle_connection, client_sock, client_addr)
        except KeyboardInterrupt:
            logger.info("Server interrupted by user.")
        finally:
            self.stop()

    def stop(self) -> None:
        """Stops the server listener, shuts down worker pool, and closes sessions."""
        if not self.is_running and self.server_sock is None:
            return
        self.is_running = False

        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass
            self.server_sock = None

        self.session_manager.stop_watchdog()
        self.session_manager.close_all()
        self.thread_pool.shutdown(wait=False, cancel_futures=True)
        logger.info("Exam TCP Server stopped cleanly.")


def launch_server():
    server = ExamTCPServer(host="0.0.0.0", port=8888)
    server.start()


if __name__ == "__main__":
    launch_server()
