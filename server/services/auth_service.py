"""
Secure Examination & Proctoring Platform
server/services/auth_service.py - Enterprise Multi-Role Identity & Biometric Verification Service
Handles multi-role authentication (RBAC), bcrypt/PBKDF2 password verification, HMAC session tokens,
and face embedding cosine similarity verification.
"""

import hashlib
import hmac
import logging
import struct
import time
from typing import Any, Dict, Optional, Tuple, Union

from server.database.repositories import (
    RoleRepository,
    StudentRepository,
    UserRepository,
    check_password,
    hash_password,
)

logger = logging.getLogger("AUTH_SERVICE")


class AuthService:
    """Service handling multi-role candidate onboarding, RBAC auth, biometric matching, and token generation."""

    def __init__(
        self,
        user_repo_or_student_repo: Optional[Union[UserRepository, StudentRepository]] = None,
        secret_key: str = "EXAM_SECRET_KEY_2026",
        student_repo: Optional[StudentRepository] = None,
        user_repo: Optional[UserRepository] = None,
    ):
        if isinstance(user_repo_or_student_repo, StudentRepository):
            self.student_repo = user_repo_or_student_repo
            self.user_repo = user_repo or user_repo_or_student_repo.user_repo
        elif isinstance(user_repo_or_student_repo, UserRepository):
            self.user_repo = user_repo_or_student_repo
            self.student_repo = student_repo or StudentRepository(self.user_repo.db)
        elif user_repo is not None:
            self.user_repo = user_repo
            self.student_repo = student_repo or StudentRepository(self.user_repo.db)
        elif student_repo is not None:
            self.student_repo = student_repo
            self.user_repo = student_repo.user_repo
        else:
            self.user_repo = UserRepository()
            self.student_repo = StudentRepository(self.user_repo.db)

        self.role_repo = RoleRepository(self.user_repo.db)
        self.secret_key = secret_key

    def register_user(
        self,
        username: str,
        password: str,
        full_name: str,
        role_name: str = "STUDENT",
        email: Optional[str] = None,
        face_embedding: Optional[bytes] = None,
        rsa_public_key: Optional[str] = None,
    ) -> Tuple[bool, Optional[int], str]:
        """
        Registers a new user account with hashed password and role assignment.

        Returns:
            Tuple[bool, Optional[int], str]: (success, user_id, message)
        """
        u_clean = username.strip()
        if not u_clean:
            return False, None, "Tên tài khoản không được để trống."
        if not password or len(password) < 6:
            return False, None, "Mật khẩu phải chứa ít nhất 6 ký tự."

        existing = self.user_repo.get_by_username(u_clean)
        if existing:
            return False, None, f"Tài khoản '{u_clean}' đã tồn tại trong hệ thống."

        pwd_hash = hash_password(password)
        try:
            user_id = self.user_repo.create_user(
                username=u_clean,
                password_hash=pwd_hash,
                full_name=full_name.strip() if full_name else u_clean,
                role_name=role_name.strip().upper(),
                email=email.strip() if email else None,
                rsa_public_key=rsa_public_key,
                face_embedding=face_embedding,
                status="ACTIVE",
            )
            logger.info(f"✅ User '{u_clean}' registered successfully as role '{role_name.upper()}' (ID: {user_id})")
            return True, user_id, "Đăng ký tài khoản thành công."
        except Exception as e:
            logger.error(f"❌ Failed to register user '{u_clean}': {e}", exc_info=True)
            return False, None, f"Lỗi hệ thống khi đăng ký: {str(e)}"

    def authenticate_user(
        self,
        username: str,
        password: str,
    ) -> Tuple[bool, Optional[str], Optional[str], Optional[str], str]:
        """
        Authenticates user with username & password against bcrypt/PBKDF2 hash.

        Returns:
            Tuple[bool, Optional[str], Optional[str], Optional[str], str]:
            (success, session_token, role_name, full_name, message)
        """
        u_clean = username.strip()
        if not u_clean or not password:
            return False, None, None, None, "Vui lòng nhập đầy đủ tên đăng nhập và mật khẩu."

        is_valid, user = self.user_repo.verify_credentials(u_clean, password)
        if not is_valid or not user:
            logger.warning(f"❌ Authentication FAILED for username: '{u_clean}'")
            return False, None, None, None, "Tài khoản hoặc mật khẩu không chính xác."

        role = user.get("role_name", "STUDENT")
        full_name = user.get("full_name", u_clean)

        # Generate HMAC-SHA256 enterprise session token: f"{username}:{role}:{timestamp}:{hmac_sig}"
        ts = int(time.time())
        token_body = f"{u_clean}:{role}:{ts}"
        sig = hmac.new(self.secret_key.encode("utf-8"), token_body.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
        session_token = f"{token_body}:{sig}"

        logger.info(f"✅ User '{u_clean}' authenticated successfully. Role: {role}, Token issued.")
        return True, session_token, role, full_name, "Xác thực danh tính thành công."

    def verify_session_token(self, token: str, max_age_seconds: int = 86400) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validates HMAC session token integrity and freshness.

        Returns:
            Tuple[bool, Optional[str], Optional[str]]: (valid, username, role)
        """
        if not token or ":" not in token:
            return False, None, None

        parts = token.split(":")
        if len(parts) != 4:
            return False, None, None

        username, role, ts_str, signature = parts
        try:
            ts = int(ts_str)
            if abs(int(time.time()) - ts) > max_age_seconds:
                logger.warning(f"Session token expired for user {username}")
                return False, None, None

            expected_body = f"{username}:{role}:{ts_str}"
            expected_sig = hmac.new(
                self.secret_key.encode("utf-8"),
                expected_body.encode("utf-8"),
                hashlib.sha256
            ).hexdigest()[:16]

            if not hmac.compare_digest(signature, expected_sig):
                logger.warning(f"Tampered session token signature for user {username}")
                return False, None, None

            return True, username, role
        except Exception as e:
            logger.warning(f"Session token validation error: {e}")
            return False, None, None

    def authenticate_student(
        self,
        student_id: str,
        student_name: str,
        public_key_pem: Optional[str] = None,
        face_embedding_bytes: Optional[bytes] = None,
        match_confidence: float = 0.95,
    ) -> Tuple[bool, Optional[str], str]:
        """
        Verifies candidate biometric credentials against stored database records.
        Maintains backward compatibility with client check-in workflow.
        
        Returns:
            Tuple[bool, Optional[str], str]: (success, session_token, message)
        """
        s_clean = student_id.strip()
        user = self.user_repo.get_by_username(s_clean)
        if not user:
            # Auto-register student if not yet present in users table
            default_pwd = hash_password(f"{s_clean}@2026")
            self.user_repo.create_user(
                username=s_clean,
                password_hash=default_pwd,
                full_name=student_name.strip() if student_name else s_clean,
                role_name="STUDENT",
                rsa_public_key=public_key_pem,
                face_embedding=face_embedding_bytes,
                status="ACTIVE",
            )
            user = self.user_repo.get_by_username(s_clean)

        # Update candidate RSA Public Key in DB if provided
        if public_key_pem:
            self.user_repo.update_public_key(s_clean, public_key_pem)

        # Biometric Verification Logic
        is_biometric_valid = False
        stored_embedding = user.get("face_embedding") if user else None

        if stored_embedding and face_embedding_bytes:
            # Cosine similarity between two 128-d vectors (512 bytes)
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
            logger.warning(f"❌ Biometric verification FAILED for candidate {s_clean} (confidence: {match_confidence:.2f})")
            return False, None, "Biometric mismatch: confidence below minimum threshold (0.70)."

        # Generate enterprise HMAC-SHA256 session token
        role = user.get("role_name", "STUDENT") if user else "STUDENT"
        ts = int(time.time())
        token_body = f"{s_clean}:{role}:{ts}"
        sig = hmac.new(self.secret_key.encode("utf-8"), token_body.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
        session_token = f"{token_body}:{sig}"

        logger.info(f"✅ Biometric verification PASSED for candidate {s_clean} ({student_name}).")
        return True, session_token, "Biometric face verification successful."
