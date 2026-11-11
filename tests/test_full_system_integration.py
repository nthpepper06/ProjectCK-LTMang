"""
Secure Examination & Proctoring Platform
tests/test_full_system_integration.py - Full End-to-End Enterprise System Integration Test
Validates:
1. TCP Server (Port 8889) + SessionManager + Layered Services
2. NetworkClient Handshake & RSA-2048 Public Key Exchange
3. Biometric Face Authentication
4. Exam Paper Fetching (Multiple Choice + Essay)
5. Multi-modal AI Violation Logging & Evidence Storage
6. Cryptographic RSA-2048 PSS Non-repudiation & Dual Countersignatures
7. Database Persistence & Receipt Verification
"""

import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from client_desktop.network_client import NetworkClient
from common.crypto_utils import generate_rsa_keypair, verify_signature
from server.core.session_manager import SessionManager
from server.database.connection import DatabaseConnectionManager
from server.database.repositories import ExamRepository, StudentRepository, SubmissionRepository, ViolationRepository
from server.services.audit_service import AuditService
from server.services.auth_service import AuthService
from server.services.exam_service import ExamService
from server.handlers.socket_handler import SocketHandler


class TestFullSystemIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.test_db_path = os.path.join(cls.temp_dir, "test_system.db")
        cls.test_evidence_dir = os.path.join(cls.temp_dir, "evidence")
        os.makedirs(cls.test_evidence_dir, exist_ok=True)

        # Setup Database
        cls.db_mgr = DatabaseConnectionManager(cls.test_db_path)
        cls.db_mgr.init_database()

        # Seed test student and exam
        cls.student_repo = StudentRepository(cls.db_mgr)
        cls.exam_repo = ExamRepository(cls.db_mgr)
        cls.sub_repo = SubmissionRepository(cls.db_mgr)
        cls.viol_repo = ViolationRepository(cls.db_mgr)

        import struct
        cls.test_embedding = struct.pack("128f", *[0.1] * 128)
        cls.student_repo.create_student("SV_INTEG_01", "Trần Văn Test", cls.test_embedding)

        cls.exam_id = cls.exam_repo.create_exam("INTEG_2026", "Kỳ thi Tích hợp Hệ thống", 45, True)
        cls.exam_repo.add_question(
            cls.exam_id, 1, "UDP là giao thức gì?", "multiple_choice",
            ["A. Connectionless", "B. Connection-oriented"], "A"
        )
        cls.exam_repo.add_question(
            cls.exam_id, 2, "Trình bày cơ chế bắt tay 3 bước TCP.", "essay"
        )

        # Generate Server RSA Keys
        cls.server_priv, cls.server_pub = generate_rsa_keypair()

        # Init Services
        cls.session_mgr = SessionManager()
        cls.auth_svc = AuthService(cls.student_repo, secret_key="EXAM_SECRET_KEY_2026")
        cls.exam_svc = ExamService(cls.exam_repo, cls.sub_repo, cls.student_repo, cls.server_priv)
        cls.audit_svc = AuditService(cls.viol_repo, cls.exam_repo, cls.test_evidence_dir)

        # Start Mini TCP Server on Port 8889
        cls.server_host = "127.0.0.1"
        cls.server_port = 8889
        cls.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cls.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        cls.server_sock.bind((cls.server_host, cls.server_port))
        cls.server_sock.listen(5)

        cls.is_running = True
        cls.server_thread = threading.Thread(target=cls._run_server, daemon=True)
        cls.server_thread.start()
        time.sleep(0.15)

    @classmethod
    def _run_server(cls):
        while cls.is_running:
            try:
                cls.server_sock.settimeout(0.5)
                client_sock, addr = cls.server_sock.accept()
                handler = SocketHandler(
                    session_manager=cls.session_mgr,
                    auth_service=cls.auth_svc,
                    exam_service=cls.exam_svc,
                    audit_service=cls.audit_svc,
                    server_public_key_pem=cls.server_pub,
                )
                t = threading.Thread(target=handler.handle_connection, args=(client_sock, addr), daemon=True)
                t.start()
            except socket.timeout:
                continue
            except Exception:
                break

    @classmethod
    def tearDownClass(cls):
        cls.is_running = False
        try:
            cls.server_sock.close()
        except Exception:
            pass
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_full_pipeline(self):
        """End-to-End Test: Connect -> Auth -> Fetch Paper -> Violation -> Sign & Submit -> Receipt."""
        client = NetworkClient(
            host=self.server_host,
            port=self.server_port,
            student_id="SV_INTEG_01",
            student_name="Trần Văn Test"
        )

        # 1. Connect and Handshake
        connected = client.connect()
        self.assertTrue(connected, "NetworkClient must successfully connect and exchange keys.")
        self.assertTrue(client.is_connected)
        self.assertIsNotNone(client.server_public_key_pem)

        # 2. Biometric Authentication
        auth_ok = client.authenticate_biometric(0.95)
        self.assertTrue(auth_ok, "Biometric authentication must succeed.")
        self.assertTrue(client.is_authenticated)

        # 3. Request Exam Paper
        paper = client.request_exam_paper()
        self.assertIsNotNone(paper)
        self.assertEqual(len(paper.get("questions", [])), 2)
        q1 = paper["questions"][0]
        q2 = paper["questions"][1]
        self.assertEqual(q1["type"], "multiple_choice")
        self.assertEqual(q2["type"], "essay")
        self.assertIn("A. Connectionless", q1["options"])

        # 4. Report Violation with Evidence
        fake_jpeg = b"\xFF\xD8\xFF\xE0\x00\x10JFIF" + b"\x00" * 32 + b"\xFF\xD9"
        client.report_violation(
            violation_type="MULTIPLE_FACES",
            details="Phát hiện 2 người trong khung hình thi",
            evidence_image_bytes=fake_jpeg
        )

        # Verify Violation logged in DB
        viols = self.viol_repo.get_student_violations("SV_INTEG_01", self.exam_id)
        self.assertEqual(len(viols), 1)
        self.assertEqual(viols[0]["violation_type"], "MULTIPLE_FACES")

        # 5. Sign and Submit Exam Paper
        answers = {
            "1": "A",
            "2": "Bắt tay 3 bước TCP gồm SYN -> SYN-ACK -> ACK để đồng bộ Sequence Number."
        }
        res = client.submit_exam_paper(exam_id="INTEG_2026", answers=answers)
        self.assertTrue(res.get("success"), f"Submission failed: {res.get('error')}")

        receipt = res.get("receipt", {})
        server_sig = res.get("server_signature", "")
        self.assertEqual(receipt.get("student_id"), "SV_INTEG_01")
        self.assertEqual(receipt.get("status"), "VERIFIED")

        # 6. Verify Server Countersignature
        receipt_bytes = json.dumps(receipt, sort_keys=True).encode("utf-8")
        is_valid_server_sig = verify_signature(self.server_pub, receipt_bytes, server_sig)
        self.assertTrue(is_valid_server_sig, "Server countersignature on receipt must be valid RSA-2048.")

        # 7. Verify Database Record
        stored_sub = self.sub_repo.get_by_student_and_exam("SV_INTEG_01", self.exam_id)
        self.assertIsNotNone(stored_sub)
        self.assertEqual(stored_sub["student_id"], "SV_INTEG_01")

        client.disconnect()


if __name__ == "__main__":
    unittest.main()
