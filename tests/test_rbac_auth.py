"""
Secure Examination & Proctoring Platform
tests/test_rbac_auth.py - Automated Unit & Integration Tests for Multi-Role RBAC & Auth Engine
Covers Role setup, User registration, Password hashing validation, Multi-role login, and Security rejections.
"""

import os
import tempfile
import unittest

from server.database.connection import DatabaseConnectionManager
from server.database.repositories import (
    RoleRepository,
    UserRepository,
    check_password,
    hash_password,
)
from server.services.auth_service import AuthService


class TestRBACAuthEngine(unittest.TestCase):
    """Test suite validating RBAC data architecture and enterprise authentication engine."""

    @classmethod
    def setUpClass(cls):
        # Create an isolated temporary database for test suite
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.test_db_path = os.path.join(cls.temp_dir.name, "test_rbac_auth.db")
        cls.db_mgr = DatabaseConnectionManager(cls.test_db_path)
        cls.db_mgr.init_database()

        cls.role_repo = RoleRepository(cls.db_mgr)
        cls.user_repo = UserRepository(cls.db_mgr)
        cls.auth_service = AuthService(user_repo=cls.user_repo, secret_key="TEST_SECRET_KEY_2026")

        # Seed roles
        cls.role_repo.get_or_create_role("ADMIN", "Quản trị viên hệ thống")
        cls.role_repo.get_or_create_role("PROCTOR", "Giám thị phòng thi")
        cls.role_repo.get_or_create_role("STUDENT", "Thí sinh thi trực tuyến")

        # Seed initial accounts
        cls.user_repo.create_user(
            username="admin_gv",
            password_hash=hash_password("Admin@2026"),
            full_name="Quản Trị Viên Giảng Viên",
            role_name="ADMIN"
        )
        cls.user_repo.create_user(
            username="giamthi_01",
            password_hash=hash_password("Proctor@2026"),
            full_name="Cán Bộ Coi Thi 01",
            role_name="PROCTOR"
        )
        cls.user_repo.create_user(
            username="SV2026_01",
            password_hash=hash_password("Student@2026"),
            full_name="Nguyễn Văn A",
            role_name="STUDENT"
        )

    @classmethod
    def tearDownClass(cls):
        cls.db_mgr.close_current_thread_connection()
        try:
            cls.temp_dir.cleanup()
        except Exception:
            pass

    def test_01_db_init_and_roles(self):
        """1. Test DB initialization and presence of core RBAC roles (ADMIN, PROCTOR, STUDENT)."""
        roles = self.role_repo.list_roles()
        role_names = [r["name"] for r in roles]
        self.assertIn("ADMIN", role_names, "Role ADMIN must exist in database")
        self.assertIn("PROCTOR", role_names, "Role PROCTOR must exist in database")
        self.assertIn("STUDENT", role_names, "Role STUDENT must exist in database")

        admin_role = self.role_repo.get_by_name("ADMIN")
        self.assertIsNotNone(admin_role)
        self.assertEqual(admin_role["name"], "ADMIN")

    def test_02_user_registration_and_password_hashing(self):
        """2. Test user registration and verify password is safe hashed (NOT plaintext)."""
        username = "new_teacher_01"
        plain_pwd = "ComplexPassword@2026"

        ok, user_id, msg = self.auth_service.register_user(
            username=username,
            password=plain_pwd,
            full_name="Thầy Giáo Ba",
            role_name="ADMIN",
            email="thayba@ptit.edu.vn"
        )
        self.assertTrue(ok, f"Registration failed: {msg}")
        self.assertIsNotNone(user_id)

        # Retrieve direct record from database
        user = self.user_repo.get_by_username(username)
        self.assertIsNotNone(user)
        stored_hash = user["password_hash"]

        # Plaintext must NEVER be stored
        self.assertNotEqual(stored_hash, plain_pwd, "Password MUST NOT be stored in plaintext")
        self.assertTrue(
            stored_hash.startswith("$2b$") or stored_hash.startswith("$pbkdf2$"),
            f"Stored password hash format invalid: {stored_hash[:10]}"
        )

        # Verification check
        self.assertTrue(check_password(plain_pwd, stored_hash), "Password verification failed with correct password")
        self.assertFalse(check_password("WrongPassword123", stored_hash), "Password verification must fail on wrong password")

    def test_03_role_based_login_and_token_generation(self):
        """3. Test successful authentication for all 3 roles (ADMIN, PROCTOR, STUDENT) and valid session token."""
        credentials = [
            ("admin_gv", "Admin@2026", "ADMIN", "Quản Trị Viên Giảng Viên"),
            ("giamthi_01", "Proctor@2026", "PROCTOR", "Cán Bộ Coi Thi 01"),
            ("SV2026_01", "Student@2026", "STUDENT", "Nguyễn Văn A"),
        ]

        for uname, pwd, expected_role, expected_name in credentials:
            ok, token, role, full_name, msg = self.auth_service.authenticate_user(uname, pwd)
            self.assertTrue(ok, f"Login failed for {uname}: {msg}")
            self.assertEqual(role, expected_role, f"Role mismatch for {uname}")
            self.assertEqual(full_name, expected_name, f"Name mismatch for {uname}")
            self.assertIsNotNone(token, "Session token must not be None")

            # Verify token structure: username:role:timestamp:hmac_sig
            parts = token.split(":")
            self.assertEqual(len(parts), 4, f"Token must contain 4 parts, got: {token}")
            self.assertEqual(parts[0], uname)
            self.assertEqual(parts[1], expected_role)

            # Verify token cryptographically
            is_valid, token_user, token_role = self.auth_service.verify_session_token(token)
            self.assertTrue(is_valid, "Cryptographic token verification failed")
            self.assertEqual(token_user, uname)
            self.assertEqual(token_role, expected_role)

    def test_04_rejection_on_invalid_credentials(self):
        """4. Test rejection when wrong password, unknown username, or duplicate username is supplied."""
        # 4a. Wrong password
        ok, token, role, full_name, msg = self.auth_service.authenticate_user("admin_gv", "IncorrectPassword")
        self.assertFalse(ok)
        self.assertIsNone(token)
        self.assertIn("không chính xác", msg)

        # 4b. Unknown username
        ok, token, role, full_name, msg = self.auth_service.authenticate_user("ghost_candidate", "AnyPass@2026")
        self.assertFalse(ok)
        self.assertIsNone(token)

        # 4c. Empty credentials
        ok, _, _, _, _ = self.auth_service.authenticate_user("", "pass")
        self.assertFalse(ok)
        ok, _, _, _, _ = self.auth_service.authenticate_user("admin_gv", "")
        self.assertFalse(ok)

        # 4d. Duplicate registration rejection
        ok, user_id, msg = self.auth_service.register_user(
            username="admin_gv",
            password="NewPassword@2026",
            full_name="Duplicate Admin",
            role_name="ADMIN"
        )
        self.assertFalse(ok, "Duplicate username registration must be rejected")
        self.assertIsNone(user_id)
        self.assertIn("đã tồn tại", msg)

    def test_05_tampered_token_rejection(self):
        """5. Security test: Ensure tampered session tokens are rejected by verify_session_token."""
        ok, valid_token, _, _, _ = self.auth_service.authenticate_user("admin_gv", "Admin@2026")
        self.assertTrue(ok)

        # Tamper username in token
        tampered_token = valid_token.replace("admin_gv", "hacker_user")
        is_valid, _, _ = self.auth_service.verify_session_token(tampered_token)
        self.assertFalse(is_valid, "Tampered token must be rejected")

        # Tamper signature in token
        parts = valid_token.split(":")
        corrupted_sig_token = f"{parts[0]}:{parts[1]}:{parts[2]}:ffffffffffffffff"
        is_valid, _, _ = self.auth_service.verify_session_token(corrupted_sig_token)
        self.assertFalse(is_valid, "Token with corrupted signature must be rejected")


if __name__ == "__main__":
    unittest.main()
