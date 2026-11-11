"""
Secure Examination & Proctoring Platform
server/database/connection.py - Thread-Safe Database Connection Manager
Provides WAL Mode, Busy Timeout, Thread-Local Connection Isolation & Atomic Transaction Locks.
"""

import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Generator, Optional

logger = logging.getLogger("DB_CONNECTION")

DEFAULT_DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../server_storage/exam_system.db")
)
SCHEMA_SQL_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "schema.sql")
)


class DatabaseConnectionManager:
    """
    Thread-Safe Database Connection Manager for high-concurrency TCP Server.
    Uses Thread-Local storage to isolate connections across worker threads,
    enables WAL mode for concurrent reads, and serializes write transactions safely.
    """

    _instance: Optional["DatabaseConnectionManager"] = None
    _init_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._init_lock:
                if not cls._instance:
                    cls._instance = super(DatabaseConnectionManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        self._local = threading.local()
        self._write_lock = threading.Lock()
        self._initialized = True

        # Initialize schema upon startup
        self.init_database()

    def get_connection(self) -> sqlite3.Connection:
        """
        Returns a thread-local SQLite connection.
        Each thread has its own connection handle, avoiding cross-thread race conditions.
        """
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(
                self.db_path,
                timeout=10.0,
                check_same_thread=False
            )
            # Enable WAL mode (Write-Ahead Logging) for concurrent reads without blocking
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA busy_timeout = 5000;")
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    def _apply_migrations(self, conn: sqlite3.Connection) -> None:
        """Applies backward-compatible column and table migrations."""
        cur = conn.cursor()
        # 1. Ensure exams.created_by column exists
        try:
            cur.execute("PRAGMA table_info(exams)")
            cols = [r[1] for r in cur.fetchall()]
            if cols and "created_by" not in cols:
                conn.execute("ALTER TABLE exams ADD COLUMN created_by INTEGER REFERENCES users(id) ON DELETE SET NULL;")
        except Exception as e:
            logger.warning(f"Migration exams.created_by error: {e}")

        # 2. Check if 'students' was created as a physical table in earlier iterations; drop if so to let view be created
        try:
            cur.execute("SELECT type FROM sqlite_master WHERE name = 'students'")
            row = cur.fetchone()
            if row and row[0] == "table":
                conn.execute("DROP TABLE IF EXISTS students;")
        except Exception as e:
            logger.warning(f"Migration students table drop error: {e}")

    def init_database(self) -> None:
        """Applies schema.sql definitions to initialize database tables and indexes."""
        if os.path.exists(SCHEMA_SQL_PATH):
            with open(SCHEMA_SQL_PATH, "r", encoding="utf-8") as f:
                schema_script = f.read()
            with self._write_lock:
                conn = self.get_connection()
                try:
                    conn.execute("PRAGMA foreign_keys = OFF;")
                    self._apply_migrations(conn)
                    conn.executescript(schema_script)
                    conn.commit()
                finally:
                    conn.execute("PRAGMA foreign_keys = ON;")

    @contextmanager
    def write_transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager for write transactions (INSERT, UPDATE, DELETE).
        Uses a mutex lock to serialize write operations across threads, preventing lock contention.
        """
        with self._write_lock:
            conn = self.get_connection()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    @contextmanager
    def read_cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        """
        Context manager for read-only queries (SELECT).
        Runs concurrently without acquiring the write lock (benefit of WAL mode).
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()

    def close_current_thread_connection(self) -> None:
        """Closes the connection belonging to the calling thread."""
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            self._local.conn = None


# Module-level convenience singleton
_db_manager: Optional[DatabaseConnectionManager] = None


def get_db_manager(db_path: str = DEFAULT_DB_PATH) -> DatabaseConnectionManager:
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseConnectionManager(db_path)
    return _db_manager
