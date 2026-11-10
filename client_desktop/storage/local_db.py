"""
Secure Examination & Proctoring Platform
client_desktop/storage/local_db.py - SQLite Local Auto-Save Manager
"""

import logging
import os
import sqlite3
import time
from typing import Any, Dict, Optional

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [LOCAL STORAGE] %(message)s")
logger = logging.getLogger("LocalStorage")

DEFAULT_DB_PATH = "exam_local_drafts.db"


class LocalDraftStorage:
    """
    Persists student draft answers locally in SQLite every 15 seconds.
    Ensures zero work loss even if unexpected power cuts or network crashes occur.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._init_database()

    def _init_database(self) -> None:
        """Initializes tables for local exam drafts."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS exam_drafts (
                    student_id TEXT NOT NULL,
                    exam_id TEXT NOT NULL,
                    question_id INTEGER NOT NULL,
                    answer_text TEXT,
                    status TEXT DEFAULT 'NOT_DONE',
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (student_id, exam_id, question_id)
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def save_draft(
        self,
        student_id: str,
        exam_id: str,
        question_id: int,
        answer_text: str,
        status: str = "DONE"
    ) -> None:
        """Saves a single question draft."""
        now = time.time()
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO exam_drafts (student_id, exam_id, question_id, answer_text, status, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(student_id, exam_id, question_id) DO UPDATE SET
                    answer_text = excluded.answer_text,
                    status = excluded.status,
                    updated_at = excluded.updated_at
            """, (student_id, exam_id, question_id, answer_text, status, now))
            conn.commit()
        finally:
            conn.close()

    def save_all_drafts(
        self,
        student_id: str,
        exam_id: str,
        answers: Dict[int, str],
        statuses: Dict[int, str]
    ) -> float:
        """
        Atomically saves all answers and their palette statuses.
        Returns timestamp of save operation.
        """
        now = time.time()
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            for q_id, text in answers.items():
                st = statuses.get(q_id, "DONE" if text.strip() else "NOT_DONE")
                cursor.execute("""
                    INSERT INTO exam_drafts (student_id, exam_id, question_id, answer_text, status, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(student_id, exam_id, question_id) DO UPDATE SET
                        answer_text = excluded.answer_text,
                        status = excluded.status,
                        updated_at = excluded.updated_at
                """, (student_id, exam_id, q_id, text, st, now))
            conn.commit()
        finally:
            conn.close()
        return now

    def load_drafts(self, student_id: str, exam_id: str) -> Dict[int, Dict[str, Any]]:
        """
        Retrieves all previously cached drafts for recovery.
        """
        results: Dict[int, Dict[str, Any]] = {}
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT question_id, answer_text, status, updated_at
                FROM exam_drafts
                WHERE student_id = ? AND exam_id = ?
            """, (student_id, exam_id))
            for row in cursor.fetchall():
                q_id, text, st, updated = row
                results[q_id] = {
                    "answer_text": text or "",
                    "status": st,
                    "updated_at": updated
                }
        finally:
            conn.close()
        return results

    def clear_drafts(self, student_id: str, exam_id: str) -> None:
        """Wipes cached drafts after confirmed successful submission."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM exam_drafts WHERE student_id = ? AND exam_id = ?
            """, (student_id, exam_id))
            conn.commit()
        finally:
            conn.close()
        logger.info(f"Cleared local drafts for {student_id} - {exam_id}")
