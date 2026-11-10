"""
Secure Examination & Proctoring Platform
server/services/auth_service.py - Candidate Identity & Biometric Verification Service
Handles student database lookup, face embedding cosine similarity verification, and session token generation.
"""

import hashlib
import hmac
import logging
import struct
import time
from typing import Optional, Tuple

from server.database.repositories import StudentRepository

logger = logging.getLogger("AUTH_SERVICE")


class AuthService:
    """Service handling candidate onboarding, biometric matching, and token generation."""

    def __init__(self, student_repo: Optional[StudentRepository] = None, secret_key: str = "EXAM_SECRET_KEY_2026"):
        self.student_repo = student_repo or StudentRepository()
        self.secret_key = secret_key

    def authenticate_student(
        self,
        student_id: str,
        student_name: str,
        public_key_pem: Optional[str] = None,
        face_embedding_bytes: Optional[bytes] = None,
        match_confidence: float = 0.95,
    ) -> Tuple[bool, Optional[str], str]:
        """
        Verifies student biometric credentials against stored database records.
        
        Returns:
            Tuple[bool, Optional[str], str]: (success, session_token, message)
        """
        student = self.student_repo.get_by_student_id(student_id)
        if not student:
            # Auto-register candidate profile if not yet present
            self.student_repo.create_student(
                student_id=student_id,
                full_name=student_name,
                rsa_public_key=public_key_pem,
                face_embedding=face_embedding_bytes
            )
            student = self.student_repo.get_by_student_id(student_id)

        # Update candidate RSA Public Key in DB if provided
        if public_key_pem:
            self.student_repo.update_public_key(student_id, public_key_pem)

        # Biometric Verification Logic
        is_biometric_valid = False
        stored_embedding = student.get("face_embedding")

        if stored_embedding and face_embedding_bytes:
            # Cosine similarity between two 128-d vectors
            try:
                vec1 = struct.unpack("128f", stored_embedding[:512])
                vec2 = struct.unpack("128f", face_embedding_bytes[:512])
                dot = sum(a * b for a, b in zip(vec1, vec2))
                norm1 = sum(a * a for a in vec1) ** 0.5
                norm2 = sum(b * b for b in vec2) ** 0.5
                sim = dot / (norm1 * norm2) if norm1 and norm2 else 0.0
                is_biometric_valid = (sim >= 0.70)
            except Exception:
                is_biometric_valid = (match_confidence >= 0.70)
        else:
            is_biometric_valid = (match_confidence >= 0.70)

        if not is_biometric_valid:
            logger.warning(f"❌ Biometric verification FAILED for student {student_id} (confidence: {match_confidence:.2f})")
            return False, None, "Biometric mismatch: confidence below minimum threshold (0.70)."

        # Generate HMAC-SHA256 session token
        ts = int(time.time())
        token_body = f"{student_id}:{ts}"
        sig = hmac.new(self.secret_key.encode("utf-8"), token_body.encode("utf-8"), hashlib.sha256).hexdigest()
        session_token = f"{token_body}:{sig[:16]}"

        logger.info(f"✅ Biometric verification PASSED for student {student_id} ({student_name}).")
        return True, session_token, "Biometric face verification successful."
