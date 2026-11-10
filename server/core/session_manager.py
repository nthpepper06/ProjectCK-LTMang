"""
Secure Examination & Proctoring Platform
server/core/session_manager.py - Thread-Safe Client Session Manager & Watchdog
Tracks active socket connections, candidates, heartbeat telemetry, and kicks dead sessions.
"""

import logging
import socket
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("SESSION_MANAGER")
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(name)s] %(message)s"
    )


class ClientSession:
    """Represents an active candidate TCP connection state."""

    def __init__(self, sock: socket.socket, addr: Tuple[str, int]):
        self.sock = sock
        self.addr = addr
        self.student_id: Optional[str] = None
        self.student_name: Optional[str] = None
        self.public_key_pem: Optional[str] = None
        self.session_token: Optional[str] = None
        self.is_authenticated: bool = False
        self.status: str = "CONNECTED"  # CONNECTED, IN_EXAM, SUBMITTED, DISCONNECTED
        self.last_heartbeat: float = time.time()
        self.connected_at: float = time.time()
        self.violations_count: int = 0
        self.lock = threading.Lock()

    def update_heartbeat(self) -> None:
        """Refreshes heartbeat timestamp."""
        with self.lock:
            self.last_heartbeat = time.time()

    def mark_authenticated(self, student_id: str, student_name: str, public_key_pem: Optional[str], token: str) -> None:
        with self.lock:
            self.student_id = student_id
            self.student_name = student_name
            self.public_key_pem = public_key_pem
            self.session_token = token
            self.is_authenticated = True
            self.status = "IN_EXAM"

    def close(self) -> None:
        """Closes underlying socket cleanly."""
        with self.lock:
            self.status = "DISCONNECTED"
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass


class SessionManager:
    """
    Thread-Safe Singleton managing all active candidate TCP sessions.
    Maintains active socket lookup tables and runs a background Watchdog thread
    to disconnect unresponsive clients whose heartbeat exceeds timeout.
    """

    _instance: Optional["SessionManager"] = None
    _init_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._init_lock:
                if not cls._instance:
                    cls._instance = super(SessionManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, heartbeat_timeout_seconds: float = 15.0):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self.heartbeat_timeout = heartbeat_timeout_seconds
        self._lock = threading.Lock()
        self._sessions_by_sock: Dict[socket.socket, ClientSession] = {}
        self._sessions_by_student_id: Dict[str, ClientSession] = {}

        self.is_running = False
        self.watchdog_thread: Optional[threading.Thread] = None
        self._initialized = True

    def start_watchdog(self) -> None:
        """Starts background thread monitoring client heartbeats."""
        if self.is_running:
            return
        self.is_running = True
        self.watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            daemon=True,
            name="HeartbeatWatchdog"
        )
        self.watchdog_thread.start()
        logger.info(f"Heartbeat Watchdog started (Timeout: {self.heartbeat_timeout}s).")

    def stop_watchdog(self) -> None:
        """Stops background watchdog."""
        self.is_running = False
        if self.watchdog_thread and self.watchdog_thread.is_alive():
            self.watchdog_thread.join(timeout=1.0)
        logger.info("Heartbeat Watchdog stopped.")

    def register_session(self, sock: socket.socket, addr: Tuple[str, int]) -> ClientSession:
        """Registers a newly accepted socket connection."""
        session = ClientSession(sock, addr)
        with self._lock:
            self._sessions_by_sock[sock] = session
        logger.info(f"Registered connection from {addr}. Total active: {len(self._sessions_by_sock)}")
        return session

    def authenticate_session(
        self,
        sock: socket.socket,
        student_id: str,
        student_name: str,
        public_key_pem: Optional[str],
        token: str
    ) -> Optional[ClientSession]:
        """Marks a connection as authenticated and binds to student_id."""
        with self._lock:
            session = self._sessions_by_sock.get(sock)
            if not session:
                return None
            session.mark_authenticated(student_id, student_name, public_key_pem, token)
            self._sessions_by_student_id[student_id] = session
        logger.info(f"Authenticated session for candidate {student_id} ({student_name}).")
        return session

    def update_heartbeat(self, sock: socket.socket) -> bool:
        """Refreshes heartbeat for connection."""
        with self._lock:
            session = self._sessions_by_sock.get(sock)
            if session:
                session.update_heartbeat()
                return True
        return False

    def get_session(self, sock: socket.socket) -> Optional[ClientSession]:
        """Returns session associated with socket."""
        with self._lock:
            return self._sessions_by_sock.get(sock)

    def get_session_by_student_id(self, student_id: str) -> Optional[ClientSession]:
        """Returns session associated with student_id."""
        with self._lock:
            return self._sessions_by_student_id.get(student_id)

    def remove_session(self, sock: socket.socket) -> Optional[ClientSession]:
        """Closes and removes session from active registers."""
        with self._lock:
            session = self._sessions_by_sock.pop(sock, None)
            if session:
                if session.student_id and session.student_id in self._sessions_by_student_id:
                    if self._sessions_by_student_id[session.student_id] == session:
                        del self._sessions_by_student_id[session.student_id]
        if session:
            session.close()
            logger.info(f"Removed session {session.addr} (Student: {session.student_id}). Remaining: {len(self._sessions_by_sock)}")
        return session

    def close_all(self) -> None:
        """Closes all open client sessions upon server shutdown."""
        with self._lock:
            sessions = list(self._sessions_by_sock.values())
            self._sessions_by_sock.clear()
            self._sessions_by_student_id.clear()

        for s in sessions:
            s.close()
        logger.info(f"Closed {len(sessions)} client sessions cleanly.")

    def get_active_count(self) -> int:
        """Returns number of active client connections."""
        with self._lock:
            return len(self._sessions_by_sock)

    def _watchdog_loop(self) -> None:
        """Background thread kicking unresponsive clients exceeding heartbeat timeout."""
        while self.is_running:
            time.sleep(2.5)
            now = time.time()
            dead_sockets: List[socket.socket] = []

            with self._lock:
                for sock, session in self._sessions_by_sock.items():
                    if now - session.last_heartbeat > self.heartbeat_timeout:
                        dead_sockets.append(sock)

            for s in dead_sockets:
                logger.warning(f"⏰ Kicking client due to heartbeat timeout (> {self.heartbeat_timeout}s).")
                self.remove_session(s)


# Module-level convenience singleton
_session_manager: Optional[SessionManager] = None


def get_session_manager(heartbeat_timeout_seconds: float = 15.0) -> SessionManager:
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager(heartbeat_timeout_seconds)
    return _session_manager
