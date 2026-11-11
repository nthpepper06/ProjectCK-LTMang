"""
Secure Examination & Proctoring Platform
server/database/repositories.py - Data Access Layer (Repository Pattern)
Encapsulates CRUD operations for Roles, Users (RBAC), Exams, Questions, Submissions, and Violations.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import bcrypt
    HAS_BCRYPT = True
except ImportError:
    HAS_BCRYPT = False

import hashlib
import hmac

from server.database.connection import DatabaseConnectionManager, get_db_manager

logger = logging.getLogger("REPOSITORIES")


def hash_password(plain_password: str) -> str:
    """Hashes a plaintext password using bcrypt with PBKDF2-HMAC fallback."""
    if HAS_BCRYPT:
        try:
            return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        except Exception as e:
            logger.warning(f"Bcrypt hash error ({e}), falling back to PBKDF2")
    salt = os.urandom(16).hex()
    dk = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return f"pbkdf2:{salt}:{dk.hex()}"


def check_password(plain_password: str, password_hash: str) -> bool:
    """Verifies a plaintext password against a stored bcrypt or PBKDF2 hash."""
    if not password_hash or not plain_password:
        return False
    try:
        if password_hash.startswith("pbkdf2:"):
            parts = password_hash.split(":")
            if len(parts) == 3:
                _, salt, dk_hex = parts
                check_dk = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 100000)
                return hmac.compare_digest(check_dk.hex(), dk_hex)
            return False
        if HAS_BCRYPT:
            return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
        return False
    except Exception as e:
        logger.warning(f"Password check failed with exception: {e}")
        return False


class RoleRepository:
    """Data Access Repository for RBAC Roles."""

    def __init__(self, db_manager: Optional[DatabaseConnectionManager] = None):
        self.db = db_manager or get_db_manager()

    def get_or_create_role(self, name: str, description: Optional[str] = None) -> int:
        """Returns existing role ID or creates role if absent."""
        name_clean = name.strip().upper()
        with self.db.write_transaction() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO roles (name, description) VALUES (?, ?)",
                (name_clean, description or f"Vai trò {name_clean}")
            )
            cur = conn.execute("SELECT id FROM roles WHERE name = ?", (name_clean,))
            row = cur.fetchone()
            return row["id"] if row else 0

    def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Retrieves role by name (case-insensitive)."""
        query = "SELECT * FROM roles WHERE UPPER(name) = UPPER(?)"
        with self.db.read_cursor() as cursor:
            cursor.execute(query, (name.strip(),))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_by_id(self, role_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves role by ID."""
        query = "SELECT * FROM roles WHERE id = ?"
        with self.db.read_cursor() as cursor:
            cursor.execute(query, (role_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_roles(self) -> List[Dict[str, Any]]:
        """Lists all system roles."""
        query = "SELECT * FROM roles ORDER BY id ASC"
        with self.db.read_cursor() as cursor:
            cursor.execute(query)
            return [dict(r) for r in cursor.fetchall()]


class UserRepository:
    """Data Access Repository for Users and Enterprise Multi-Role Authentication."""

    def __init__(self, db_manager: Optional[DatabaseConnectionManager] = None):
        self.db = db_manager or get_db_manager()
        self.role_repo = RoleRepository(self.db)

    def create_user(
        self,
        username: str,
        password_hash: str,
        full_name: str,
        role_name: str = "STUDENT",
        email: Optional[str] = None,
        rsa_public_key: Optional[str] = None,
        face_embedding: Optional[bytes] = None,
        status: str = "ACTIVE",
    ) -> int:
        """Creates or updates a user profile with role assignment."""
        role_id = self.role_repo.get_or_create_role(role_name)
        query = """
            INSERT INTO users (username, password_hash, full_name, role_id, email, rsa_public_key, face_embedding, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                password_hash = excluded.password_hash,
                full_name = excluded.full_name,
                role_id = excluded.role_id,
                email = COALESCE(excluded.email, users.email),
                rsa_public_key = COALESCE(excluded.rsa_public_key, users.rsa_public_key),
                face_embedding = COALESCE(excluded.face_embedding, users.face_embedding),
                status = excluded.status
        """
        with self.db.write_transaction() as conn:
            conn.execute(
                query,
                (username.strip(), password_hash, full_name.strip(), role_id, email, rsa_public_key, face_embedding, status)
            )
            cur = conn.execute("SELECT id FROM users WHERE username = ?", (username.strip(),))
            row = cur.fetchone()
            return row["id"] if row else 0

    def get_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Retrieves user profile along with role details by username."""
        query = """
            SELECT u.*, r.name AS role_name, r.description AS role_description
            FROM users u
            JOIN roles r ON u.role_id = r.id
            WHERE u.username = ?
        """
        with self.db.read_cursor() as cursor:
            cursor.execute(query, (username.strip(),))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves user profile along with role details by user_id."""
        query = """
            SELECT u.*, r.name AS role_name, r.description AS role_description
            FROM users u
            JOIN roles r ON u.role_id = r.id
            WHERE u.id = ?
        """
        with self.db.read_cursor() as cursor:
            cursor.execute(query, (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def verify_credentials(self, username: str, plain_password: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Verifies username and password against stored bcrypt/PBKDF2 hash."""
        user = self.get_by_username(username)
        if not user:
            return False, None
        if user.get("status") != "ACTIVE":
            return False, None
        is_valid = check_password(plain_password, user["password_hash"])
        return is_valid, user if is_valid else None

    def update_face_embedding(self, user_id_or_username: Union[int, str], embedding_bytes: bytes) -> bool:
        """Updates biometric face embedding for a user."""
        if isinstance(user_id_or_username, int):
            query = "UPDATE users SET face_embedding = ? WHERE id = ?"
        else:
            query = "UPDATE users SET face_embedding = ? WHERE username = ?"
        with self.db.write_transaction() as conn:
            cursor = conn.execute(query, (embedding_bytes, user_id_or_username))
            return cursor.rowcount > 0

    def update_public_key(self, user_id_or_username: Union[int, str], rsa_public_key: str) -> bool:
        """Updates RSA Public Key PEM for a user."""
        if isinstance(user_id_or_username, int):
            query = "UPDATE users SET rsa_public_key = ? WHERE id = ?"
        else:
            query = "UPDATE users SET rsa_public_key = ? WHERE username = ?"
        with self.db.write_transaction() as conn:
            cursor = conn.execute(query, (rsa_public_key, user_id_or_username))
            return cursor.rowcount > 0

    def list_users(self, role_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists users filtered optionally by role."""
        if role_name:
            query = """
                SELECT u.id, u.username, u.full_name, u.email, u.status, u.created_at, r.name AS role_name
                FROM users u
                JOIN roles r ON u.role_id = r.id
                WHERE UPPER(r.name) = UPPER(?)
                ORDER BY u.id ASC
            """
            params = (role_name.strip(),)
        else:
            query = """
                SELECT u.id, u.username, u.full_name, u.email, u.status, u.created_at, r.name AS role_name
                FROM users u
                JOIN roles r ON u.role_id = r.id
                ORDER BY u.id ASC
            """
            params = ()
        with self.db.read_cursor() as cursor:
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]


class StudentRepository:
    """
    Backward-compatible Repository for Students and Biometric Profiles.
    Delegates underlying storage to UserRepository with role 'STUDENT'.
    """

    def __init__(self, db_manager: Optional[DatabaseConnectionManager] = None):
        self.db = db_manager or get_db_manager()
        self.user_repo = UserRepository(self.db)

    def create_student(
        self,
        student_id: str,
        full_name: str,
        rsa_public_key: Optional[str] = None,
        face_embedding: Optional[bytes] = None,
    ) -> int:
        """Registers or updates a student profile."""
        default_hash = hash_password("Student@2026")
        return self.user_repo.create_user(
            username=student_id,
            password_hash=default_hash,
            full_name=full_name,
            role_name="STUDENT",
            rsa_public_key=rsa_public_key,
            face_embedding=face_embedding
        )

    def get_by_student_id(self, student_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves student profile by student_id (username)."""
        user = self.user_repo.get_by_username(student_id)
        if user:
            user["student_id"] = user["username"]
        return user

    def get_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Retrieves user profile by username (delegates to UserRepository)."""
        return self.get_by_student_id(username)

    def verify_credentials(self, username: str, plain_password: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Verifies credentials (delegates to UserRepository)."""
        return self.user_repo.verify_credentials(username, plain_password)

    def update_public_key(self, student_id: str, rsa_public_key: str) -> bool:
        """Updates active RSA Public Key for candidate."""
        return self.user_repo.update_public_key(student_id, rsa_public_key)

    def get_public_key(self, student_id: str) -> Optional[str]:
        """Retrieves RSA Public Key PEM."""
        user = self.user_repo.get_by_username(student_id)
        return user["rsa_public_key"] if user and user.get("rsa_public_key") else None

    def list_all(self) -> List[Dict[str, Any]]:
        """Lists all registered student accounts."""
        users = self.user_repo.list_users(role_name="STUDENT")
        for u in users:
            u["student_id"] = u["username"]
        return users


class ExamRepository:
    """Data Access Repository for Exams and Exam Questions."""

    def __init__(self, db_manager: Optional[DatabaseConnectionManager] = None):
        self.db = db_manager or get_db_manager()

    def create_exam(
        self,
        exam_code: str,
        title: str,
        duration_minutes: int = 60,
        is_active: bool = True,
        created_by: Optional[int] = None,
    ) -> int:
        """Creates or updates an exam room."""
        query = """
            INSERT INTO exams (exam_code, title, duration_minutes, is_active, created_by)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(exam_code) DO UPDATE SET
                title = excluded.title,
                duration_minutes = excluded.duration_minutes,
                is_active = excluded.is_active,
                created_by = COALESCE(excluded.created_by, exams.created_by)
        """
        with self.db.write_transaction() as conn:
            conn.execute(query, (exam_code, title, duration_minutes, 1 if is_active else 0, created_by))
            cur = conn.execute("SELECT id FROM exams WHERE exam_code = ?", (exam_code,))
            row = cur.fetchone()
            return row["id"] if row else 0

    def add_question(
        self,
        exam_id: int,
        question_index: int,
        content: str,
        question_type: str = "essay",
        options: Optional[List[str]] = None,
        correct_answer_hash: Optional[str] = None,
    ) -> int:
        """Adds or updates a question in an exam (idempotent)."""
        options_json = json.dumps(options) if options else None
        check_q = "SELECT id FROM questions WHERE exam_id = ? AND question_index = ?"
        with self.db.write_transaction() as conn:
            cur = conn.execute(check_q, (exam_id, question_index))
            existing = cur.fetchone()
            if existing:
                conn.execute(
                    """UPDATE questions SET content = ?, question_type = ?, options_json = ?, correct_answer_hash = ?
                       WHERE id = ?""",
                    (content, question_type, options_json, correct_answer_hash, existing["id"])
                )
                return existing["id"]
            else:
                insert_q = """
                    INSERT INTO questions (exam_id, question_index, content, question_type, options_json, correct_answer_hash)
                    VALUES (?, ?, ?, ?, ?, ?)
                """
                cursor = conn.execute(
                    insert_q,
                    (exam_id, question_index, content, question_type, options_json, correct_answer_hash)
                )
                return cursor.lastrowid

    def get_by_code(self, exam_code: str) -> Optional[Dict[str, Any]]:
        """Finds exam record by exam_code."""
        query = "SELECT * FROM exams WHERE exam_code = ?"
        with self.db.read_cursor() as cursor:
            cursor.execute(query, (exam_code,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_active_exam(self) -> Optional[Dict[str, Any]]:
        """Returns the currently active exam session."""
        query = "SELECT * FROM exams WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
        with self.db.read_cursor() as cursor:
            cursor.execute(query)
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_exam_paper(self, exam_code: str) -> Optional[Dict[str, Any]]:
        """Constructs full client-facing exam paper with all questions ordered by index."""
        exam = self.get_by_code(exam_code)
        if not exam:
            return None

        q_query = """
            SELECT question_index AS id, content AS question, question_type AS type, options_json
            FROM questions
            WHERE exam_id = ?
            ORDER BY question_index ASC
        """
        with self.db.read_cursor() as cursor:
            cursor.execute(q_query, (exam["id"],))
            rows = cursor.fetchall()

            questions = []
            for r in rows:
                item = {
                    "id": r["id"],
                    "question": r["question"],
                    "type": r["type"]
                }
                if r["options_json"]:
                    item["options"] = json.loads(r["options_json"])
                questions.append(item)

        return {
            "exam_id": exam["exam_code"],
            "title": exam["title"],
            "duration_minutes": exam["duration_minutes"],
            "questions": questions
        }


class SubmissionRepository:
    """Data Access Repository for Submissions and Anti-Repudiation Dual Signatures."""

    def __init__(self, db_manager: Optional[DatabaseConnectionManager] = None):
        self.db = db_manager or get_db_manager()

    def _resolve_user_id(self, student_id: Union[int, str]) -> int:
        """Resolves student_id (username string or user_id int) to user primary key."""
        if isinstance(student_id, int):
            return student_id
        with self.db.read_cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE username = ?", (str(student_id),))
            row = cursor.fetchone()
            if row:
                return row["id"]
        try:
            return int(student_id)
        except ValueError:
            return 0

    def create_submission(
        self,
        exam_id: int,
        student_id: Union[int, str],
        answers: Dict[str, Any],
        sha256_hash: str,
        digital_signature: str,
        server_receipt_signature: str,
        submitted_at_ms: int,
        status: str = "VERIFIED",
    ) -> int:
        """Stores candidate final submission with non-repudiation cryptographic signatures."""
        uid = self._resolve_user_id(student_id)
        answers_json = json.dumps(answers, sort_keys=True)
        query = """
            INSERT INTO submissions (
                exam_id, student_id, answers_payload, sha256_hash,
                digital_signature, server_receipt_signature, submitted_at_ms, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self.db.write_transaction() as conn:
            cursor = conn.execute(
                query,
                (
                    exam_id,
                    uid,
                    answers_json,
                    sha256_hash,
                    digital_signature,
                    server_receipt_signature,
                    submitted_at_ms,
                    status
                )
            )
            return cursor.lastrowid

    def get_by_student_and_exam(self, student_id: Union[int, str], exam_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves official submission record."""
        uid = self._resolve_user_id(student_id)
        query = """
            SELECT s.*, u.username AS student_username, u.full_name AS student_name
            FROM submissions s
            JOIN users u ON s.student_id = u.id
            WHERE s.student_id = ? AND s.exam_id = ?
        """
        with self.db.read_cursor() as cursor:
            cursor.execute(query, (uid, exam_id))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            res["student_id"] = res["student_username"]
            res["answers"] = json.loads(res["answers_payload"])
            return res

    def has_submitted(self, student_id: Union[int, str], exam_id: int) -> bool:
        """Checks if student has already submitted for this exam."""
        uid = self._resolve_user_id(student_id)
        query = "SELECT 1 FROM submissions WHERE student_id = ? AND exam_id = ? LIMIT 1"
        with self.db.read_cursor() as cursor:
            cursor.execute(query, (uid, exam_id))
            return cursor.fetchone() is not None


class ViolationRepository:
    """Data Access Repository for Proctoring Telemetry and Anti-Cheat Violation Logs."""

    def __init__(self, db_manager: Optional[DatabaseConnectionManager] = None):
        self.db = db_manager or get_db_manager()

    def _resolve_user_id(self, student_id: Union[int, str]) -> int:
        if isinstance(student_id, int):
            return student_id
        with self.db.read_cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE username = ?", (str(student_id),))
            row = cursor.fetchone()
            if row:
                return row["id"]
        try:
            return int(student_id)
        except ValueError:
            return 0

    def log_violation(
        self,
        student_id: Union[int, str],
        exam_id: int,
        violation_type: str,
        suspicion_score: float = 1.0,
        details: Optional[str] = None,
        evidence_path: Optional[str] = None,
        timestamp_ms: int = 0,
    ) -> int:
        """Appends an AI proctoring incident to violation_logs."""
        uid = self._resolve_user_id(student_id)
        query = """
            INSERT INTO violation_logs (
                student_id, exam_id, violation_type, suspicion_score, details, evidence_path, timestamp_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        with self.db.write_transaction() as conn:
            cursor = conn.execute(
                query,
                (
                    uid,
                    exam_id,
                    violation_type,
                    suspicion_score,
                    details,
                    evidence_path,
                    timestamp_ms
                )
            )
            return cursor.lastrowid

    def count_violations(self, student_id: Union[int, str], exam_id: int) -> int:
        """Returns total count of incidents logged for candidate during exam."""
        uid = self._resolve_user_id(student_id)
        query = "SELECT COUNT(*) AS total FROM violation_logs WHERE student_id = ? AND exam_id = ?"
        with self.db.read_cursor() as cursor:
            cursor.execute(query, (uid, exam_id))
            row = cursor.fetchone()
            return row["total"] if row else 0

    def get_student_violations(self, student_id: Union[int, str], exam_id: int) -> List[Dict[str, Any]]:
        """Returns chronological history of violations for audit report."""
        uid = self._resolve_user_id(student_id)
        query = """
            SELECT violation_type, suspicion_score, details, evidence_path, timestamp_ms, created_at
            FROM violation_logs
            WHERE student_id = ? AND exam_id = ?
            ORDER BY timestamp_ms ASC
        """
        with self.db.read_cursor() as cursor:
            cursor.execute(query, (uid, exam_id))
            return [dict(r) for r in cursor.fetchall()]
