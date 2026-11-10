"""
Secure Examination & Proctoring Platform
server/database/repositories.py - Data Access Layer (Repository Pattern)
Encapsulates CRUD operations for Students, Exams, Questions, Submissions, and Violations.
"""

import json
from typing import Any, Dict, List, Optional

from server.database.connection import DatabaseConnectionManager, get_db_manager


class StudentRepository:
    """Data Access Repository for Students and Biometric Profile Data."""

    def __init__(self, db_manager: Optional[DatabaseConnectionManager] = None):
        self.db = db_manager or get_db_manager()

    def create_student(
        self,
        student_id: str,
        full_name: str,
        rsa_public_key: Optional[str] = None,
        face_embedding: Optional[bytes] = None,
    ) -> int:
        """Registers a new student profile with optional biometric embedding."""
        query = """
            INSERT INTO students (student_id, full_name, rsa_public_key, face_embedding)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(student_id) DO UPDATE SET
                full_name = excluded.full_name,
                rsa_public_key = COALESCE(excluded.rsa_public_key, students.rsa_public_key),
                face_embedding = COALESCE(excluded.face_embedding, students.face_embedding)
        """
        with self.db.write_transaction() as conn:
            conn.execute(query, (student_id, full_name, rsa_public_key, face_embedding))
            cur = conn.execute("SELECT id FROM students WHERE student_id = ?", (student_id,))
            row = cur.fetchone()
            return row["id"] if row else 0

    def get_by_student_id(self, student_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves student record by student_id (MSSV)."""
        query = "SELECT * FROM students WHERE student_id = ?"
        with self.db.read_cursor() as cursor:
            cursor.execute(query, (student_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_public_key(self, student_id: str, rsa_public_key: str) -> bool:
        """Updates the active RSA-2048 Public Key for a candidate during connection handshake."""
        query = "UPDATE students SET rsa_public_key = ? WHERE student_id = ?"
        with self.db.write_transaction() as conn:
            cursor = conn.execute(query, (rsa_public_key, student_id))
            return cursor.rowcount > 0

    def get_public_key(self, student_id: str) -> Optional[str]:
        """Returns the registered RSA Public Key PEM string."""
        query = "SELECT rsa_public_key FROM students WHERE student_id = ?"
        with self.db.read_cursor() as cursor:
            cursor.execute(query, (student_id,))
            row = cursor.fetchone()
            return row["rsa_public_key"] if row and row["rsa_public_key"] else None

    def list_all(self) -> List[Dict[str, Any]]:
        """Returns all registered students."""
        query = "SELECT id, student_id, full_name, created_at FROM students ORDER BY id ASC"
        with self.db.read_cursor() as cursor:
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]


class ExamRepository:
    """Data Access Repository for Exams and Exam Questions."""

    def __init__(self, db_manager: Optional[DatabaseConnectionManager] = None):
        self.db = db_manager or get_db_manager()

    def create_exam(
        self,
        exam_code: str,
        title: str,
        duration_minutes: int = 60,
        is_active: bool = True
    ) -> int:
        """Creates or updates an exam room."""
        query = """
            INSERT INTO exams (exam_code, title, duration_minutes, is_active)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(exam_code) DO UPDATE SET
                title = excluded.title,
                duration_minutes = excluded.duration_minutes,
                is_active = excluded.is_active
        """
        with self.db.write_transaction() as conn:
            conn.execute(query, (exam_code, title, duration_minutes, 1 if is_active else 0))
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
        """
        Constructs full client-facing exam paper with all questions ordered by index.
        """
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
    """Data Access Repository for Exam Submissions and Digital Audit Records."""

    def __init__(self, db_manager: Optional[DatabaseConnectionManager] = None):
        self.db = db_manager or get_db_manager()

    def create_submission(
        self,
        exam_id: int,
        student_id: str,
        answers: Dict[str, Any],
        sha256_hash: str,
        digital_signature: str,
        server_receipt_signature: str,
        submitted_at_ms: int,
        status: str = "VERIFIED",
    ) -> int:
        """
        Stores candidate final submission with non-repudiation cryptographic signatures.
        """
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
                    student_id,
                    answers_json,
                    sha256_hash,
                    digital_signature,
                    server_receipt_signature,
                    submitted_at_ms,
                    status
                )
            )
            return cursor.lastrowid

    def get_by_student_and_exam(self, student_id: str, exam_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves official submission record."""
        query = "SELECT * FROM submissions WHERE student_id = ? AND exam_id = ?"
        with self.db.read_cursor() as cursor:
            cursor.execute(query, (student_id, exam_id))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            res["answers"] = json.loads(res["answers_payload"])
            return res

    def has_submitted(self, student_id: str, exam_id: int) -> bool:
        """Checks if student has already submitted for this exam."""
        query = "SELECT 1 FROM submissions WHERE student_id = ? AND exam_id = ? LIMIT 1"
        with self.db.read_cursor() as cursor:
            cursor.execute(query, (student_id, exam_id))
            return cursor.fetchone() is not None


class ViolationRepository:
    """Data Access Repository for Proctoring Telemetry and Anti-Cheat Violation Logs."""

    def __init__(self, db_manager: Optional[DatabaseConnectionManager] = None):
        self.db = db_manager or get_db_manager()

    def log_violation(
        self,
        student_id: str,
        exam_id: int,
        violation_type: str,
        suspicion_score: float = 1.0,
        details: Optional[str] = None,
        evidence_path: Optional[str] = None,
        timestamp_ms: int = 0,
    ) -> int:
        """Appends an AI proctoring incident to violation_logs."""
        query = """
            INSERT INTO violation_logs (
                student_id, exam_id, violation_type, suspicion_score, details, evidence_path, timestamp_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        with self.db.write_transaction() as conn:
            cursor = conn.execute(
                query,
                (
                    student_id,
                    exam_id,
                    violation_type,
                    suspicion_score,
                    details,
                    evidence_path,
                    timestamp_ms
                )
            )
            return cursor.lastrowid

    def count_violations(self, student_id: str, exam_id: int) -> int:
        """Returns total count of incidents logged for candidate during exam."""
        query = "SELECT COUNT(*) AS total FROM violation_logs WHERE student_id = ? AND exam_id = ?"
        with self.db.read_cursor() as cursor:
            cursor.execute(query, (student_id, exam_id))
            row = cursor.fetchone()
            return row["total"] if row else 0

    def get_student_violations(self, student_id: str, exam_id: int) -> List[Dict[str, Any]]:
        """Returns chronological history of violations for audit report."""
        query = """
            SELECT violation_type, suspicion_score, details, evidence_path, timestamp_ms, created_at
            FROM violation_logs
            WHERE student_id = ? AND exam_id = ?
            ORDER BY timestamp_ms ASC
        """
        with self.db.read_cursor() as cursor:
            cursor.execute(query, (student_id, exam_id))
            return [dict(r) for r in cursor.fetchall()]
