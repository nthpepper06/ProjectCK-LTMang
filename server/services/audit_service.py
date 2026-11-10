"""
Secure Examination & Proctoring Platform
server/services/audit_service.py - AI Proctoring Telemetry & Violation Audit Service
Persists suspicious candidate actions and webcam snapshots to database and server storage.
"""

import base64
import logging
import os
import time
from typing import Any, Dict, Optional

from server.database.repositories import ExamRepository, ViolationRepository

logger = logging.getLogger("AUDIT_SERVICE")


class AuditService:
    """Service handling proctoring telemetry logging and violation snapshot preservation."""

    def __init__(
        self,
        viol_repo: Optional[ViolationRepository] = None,
        exam_repo: Optional[ExamRepository] = None,
        evidence_dir: str = "server_storage/evidence",
    ):
        self.viol_repo = viol_repo or ViolationRepository()
        self.exam_repo = exam_repo or ExamRepository()
        self.evidence_dir = evidence_dir
        os.makedirs(self.evidence_dir, exist_ok=True)

    def log_violation(
        self,
        student_id: str,
        exam_code: Optional[str],
        violation_type: str,
        suspicion_score: float = 1.0,
        details: str = "",
        evidence_b64: Optional[str] = None,
        timestamp_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Stores AI proctoring alert, saves snapshot image to disk, and records entry in database.
        """
        if timestamp_ms is None or timestamp_ms == 0:
            timestamp_ms = int(time.time() * 1000)

        # 1. Save evidence image file if attached
        evidence_filename = None
        evidence_filepath = None
        if evidence_b64:
            try:
                evidence_filename = f"{student_id}_{violation_type}_{timestamp_ms}.jpg"
                evidence_filepath = os.path.join(self.evidence_dir, evidence_filename)
                with open(evidence_filepath, "wb") as f:
                    f.write(base64.b64decode(evidence_b64))
            except Exception as e:
                logger.error(f"Failed to write evidence snapshot for {student_id}: {e}")

        # 2. Resolve exam ID
        exam = None
        if exam_code:
            exam = self.exam_repo.get_by_code(exam_code)
        if not exam:
            exam = self.exam_repo.get_active_exam()
        exam_id = exam["id"] if exam else 1

        # 3. Insert into ViolationRepository
        try:
            self.viol_repo.log_violation(
                student_id=student_id,
                exam_id=exam_id,
                violation_type=violation_type,
                suspicion_score=suspicion_score,
                details=details,
                evidence_path=evidence_filename,
                timestamp_ms=timestamp_ms
            )
        except Exception as e:
            logger.warning(f"Failed to record violation into database: {e}")

        logger.warning(
            f"🚨 [VIOLATION ALERT] Student {student_id}: Type={violation_type}, Details={details}, Evidence={evidence_filename}"
        )

        return {
            "status": "LOGGED",
            "timestamp_ms": timestamp_ms
        }
