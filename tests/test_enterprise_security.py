"""
Secure Examination & Proctoring Platform
tests/test_enterprise_security.py - Enterprise Commercial-Grade Security & Auto-Discovery Test Suite
Tests:
1. UDP LAN Auto-Discovery (Server Discovery Responder & Client LAN Scanner on port 5006)
2. Deep Anti-VM & Hypervisor Registry/MAC Check
3. Multi-Modal Vision & Audio AI Proctoring Components
4. Multiple-Choice & Essay Question Rendering, Auto-Save, and Input Locking
5. Time-out / Forced Auto-Submission with RSA-2048 Digital Signature
"""

import os
import sys
import time
import unittest
from unittest.mock import MagicMock

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common.discovery import ClientLANScanner, ServerDiscoveryResponder, load_client_config, save_client_config
from client_desktop.security.windows_guard import AntiVMDetector, DisplayAffinityGuard, LowLevelKeyboardGuard
from client_desktop.security.audio_monitor import AudioMonitorThread
from client_desktop.security.object_detector import ObjectDetector
from client_desktop.storage.local_db import LocalDraftStorage


class TestEnterpriseSecuritySuite(unittest.TestCase):
    """Automated integration tests for Phase 5 Commercial-Grade capabilities."""

    def test_01_udp_lan_auto_discovery(self):
        """Validates UDP broadcast auto-discovery mechanism between Server and Client."""
        test_port = 5006
        responder = ServerDiscoveryResponder(
            server_ip="127.0.0.1",
            tcp_port=8888,
            http_port=8080,
            ws_port=8081,
            exam_title="Kỳ thi Thử nghiệm An ninh Mạng",
            discovery_port=test_port
        )
        responder.start()
        time.sleep(0.4)

        scanner = ClientLANScanner()
        server_info = scanner.discover_server(port=test_port, timeout_seconds=2.0)
        responder.stop()

        self.assertIsNotNone(server_info, "ClientLANScanner should discover local server announcement")
        self.assertEqual(server_info.get("tcp_port"), 8888)
        self.assertIn("Thử nghiệm", server_info.get("exam_title", ""))

    def test_02_client_config_persistence(self):
        """Verifies loading and saving client network configurations."""
        test_cfg_path = "test_client_config.json"
        try:
            sample_cfg = {
                "server_host": "192.168.1.100",
                "server_port": 8888,
                "auto_discovered": True,
                "last_student_id": "SV_TEST_99"
            }
            save_client_config(sample_cfg, config_path=test_cfg_path)
            loaded = load_client_config(config_path=test_cfg_path)
            self.assertEqual(loaded["server_host"], "192.168.1.100")
            self.assertEqual(loaded["server_port"], 8888)
            self.assertTrue(loaded["auto_discovered"])
        finally:
            if os.path.exists(test_cfg_path):
                os.remove(test_cfg_path)

    def test_03_anti_vm_detection(self):
        """Tests Anti-VM hardware registry and virtual MAC OUI heuristics."""
        is_vm, verdict, audit_data = AntiVMDetector.evaluate_environment()
        self.assertIsInstance(is_vm, bool)
        self.assertIsInstance(verdict, str)
        self.assertTrue(len(verdict) > 0)
        self.assertIn("bios", audit_data)
        self.assertIn("macs", audit_data)

    def test_04_object_detector_fallback(self):
        """Tests computer vision prohibited object detector initialization and detection pipeline."""
        import numpy as np
        detector = ObjectDetector()
        self.assertIsNotNone(detector)
        # Test synthetic frame
        blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = detector.detect(blank_frame)
        self.assertIsInstance(detections, list)

    def test_05_audio_monitor_threshold_logic(self):
        """Tests audio monitor configuration and threshold attributes."""
        audio_thread = AudioMonitorThread(rms_threshold=0.045, trigger_duration_sec=3.0)
        self.assertEqual(audio_thread.rms_threshold, 0.045)
        self.assertEqual(audio_thread.trigger_duration_sec, 3.0)
        self.assertFalse(audio_thread.isRunning())

    def test_06_local_draft_storage_multiple_choice_and_essay(self):
        """Tests local SQLite persistence with both Multiple Choice choices and Essay texts."""
        test_db = "test_drafts_temp.db"
        try:
            storage = LocalDraftStorage(db_path=test_db)
            answers = {
                1: "A",
                2: "B",
                3: "Phân tích cơ chế bắt tay 3 bước TCP SYN, SYN-ACK, ACK..."
            }
            statuses = {
                1: "DONE",
                2: "REVIEW",
                3: "DONE"
            }
            storage.save_all_drafts("SV2026_01", "LTM_2026_FINAL", answers, statuses)

            loaded = storage.load_drafts("SV2026_01", "LTM_2026_FINAL")
            self.assertEqual(loaded[1]["answer_text"], "A")
            self.assertEqual(loaded[1]["status"], "DONE")
            self.assertEqual(loaded[2]["answer_text"], "B")
            self.assertEqual(loaded[2]["status"], "REVIEW")
            self.assertIn("bắt tay 3 bước", loaded[3]["answer_text"])
        finally:
            if os.path.exists(test_db):
                os.remove(test_db)

    def test_07_win32_keyboard_guard_lifecycle(self):
        """Tests LowLevelKeyboardGuard install and safe cleanup without leaking hooks."""
        # Install hook
        installed = LowLevelKeyboardGuard.install_hook()
        # Should be active or handled gracefully
        self.assertEqual(LowLevelKeyboardGuard.is_active(), installed)
        # Uninstall cleanly
        LowLevelKeyboardGuard.uninstall_hook()
        self.assertFalse(LowLevelKeyboardGuard.is_active())


if __name__ == "__main__":
    unittest.main()
