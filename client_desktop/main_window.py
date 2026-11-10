"""
Secure Examination & Proctoring Platform
client_desktop/main_window.py - Production-Ready Kiosk Window Managing 4-Stage Lifecycle
"""

import os
import sys
import time
from typing import Optional

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PyQt6.QtCore import QEvent, Qt, QTimer
from PyQt6.QtGui import QFont, QKeyEvent
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from client_desktop.ai_proctor_thread import AIProctorThread
from client_desktop.multicast_listener import MulticastListenerThread
from client_desktop.network_client import NetworkClient
from client_desktop.security.clipboard_hook import ClipboardSanitizer
from client_desktop.security.monitor_blocker import MultiMonitorBlocker
from client_desktop.security.process_watchdog import ProcessWatchdogThread
from client_desktop.ui.screen_exam import ExamScreen
from client_desktop.ui.screen_login import BiometricLoginScreen
from client_desktop.ui.screen_preflight import PreflightScreen
from client_desktop.ui.screen_receipt import SubmissionReceiptScreen
from common.protocol import CommandType


class ExamMainWindow(QWidget):
    """
    Main Kiosk Host Window orchestrating the 4-stage examination lifecycle:
    1. Pre-flight Hardware & Network Check
    2. Biometric Onboarding & Face Matching
    3. UX-Optimized Exam View with Question Palette & Local Auto-Save
    4. Cryptographic Submission Receipt & Dynamic QR Code Audit
    """

    def __init__(self, server_host: str = "127.0.0.1", server_port: int = 8888):
        super().__init__()
        self.server_host = server_host
        self.server_port = server_port
        self.student_id = "SV2026_01"
        self.student_name = "Nguyen Van A"
        self.is_fullscreen_mode = True

        # 1. Initialize Network Client
        self.net_client = NetworkClient(
            host=self.server_host,
            port=self.server_port,
            student_id=self.student_id,
            student_name=self.student_name
        )

        # 2. Setup Kiosk Mode Window Flags
        self.setWindowTitle("Secure Online Examination Platform - Production Kiosk Mode")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        # 3. Security Subsystems (OS-Level)
        self.monitor_blocker = MultiMonitorBlocker()

        self.clipboard_sanitizer = ClipboardSanitizer(sanitize_interval_ms=2000, parent=self)
        self.clipboard_sanitizer.start()

        self.process_watchdog = ProcessWatchdogThread(check_interval_seconds=3.0)
        self.process_watchdog.prohibited_process_detected.connect(self._on_prohibited_process)
        self.process_watchdog.start()

        # 4. AI Proctoring Thread (Single Source of Camera Capture)
        self.proctor_thread = AIProctorThread(camera_index=0)
        self.proctor_thread.frame_ready.connect(self._on_camera_frame)
        self.proctor_thread.violation_detected.connect(self._on_ai_violation)
        self.proctor_thread.telemetry_updated.connect(self._on_ai_telemetry)
        self.proctor_thread.start()

        # 5. UDP Multicast Listener Thread
        self.multicast_listener = MulticastListenerThread(
            on_command_received=self._on_multicast_command
        )
        self.multicast_listener.start()

        # 6. Build 4-Stage QStackedWidget UI
        self._init_ui()
        self._apply_dark_theme()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Top Control / Title Bar with Emergency Exit and Fullscreen Toggle
        control_bar = QFrame()
        control_bar.setFixedHeight(38)
        control_bar.setStyleSheet("""
            background-color: #0B0F19;
            border-bottom: 1px solid #1E293B;
            padding: 0px 10px;
        """)
        c_layout = QHBoxLayout(control_bar)
        c_layout.setContentsMargins(10, 0, 10, 0)

        lbl_app_tag = QLabel("🛡️ SMART AI PROCTORING & SECURE EXAMINATION PLATFORM")
        lbl_app_tag.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lbl_app_tag.setStyleSheet("color: #60A5FA;")
        c_layout.addWidget(lbl_app_tag)
        c_layout.addStretch()

        # Toggle Fullscreen / Windowed Mode (F11)
        self.btn_toggle_screen = QPushButton("⛶ Cửa sổ / Toàn màn hình (F11)")
        self.btn_toggle_screen.setFont(QFont("Segoe UI", 9))
        self.btn_toggle_screen.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_screen.setStyleSheet("""
            QPushButton {
                background-color: #1E293B; color: #CBD5E1; border: 1px solid #334155; border-radius: 4px; padding: 4px 10px;
            }
            QPushButton:hover { background-color: #334155; color: white; }
        """)
        self.btn_toggle_screen.clicked.connect(self._toggle_fullscreen_mode)
        c_layout.addWidget(self.btn_toggle_screen)
        c_layout.addSpacing(10)

        # Emergency Exit / Close Button
        btn_exit = QPushButton("✕ Thoát Kiosk")
        btn_exit.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        btn_exit.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_exit.setStyleSheet("""
            QPushButton {
                background-color: #7F1D1D; color: #FECACA; border: 1px solid #991B1B; border-radius: 4px; padding: 4px 12px;
            }
            QPushButton:hover { background-color: #DC2626; color: white; }
        """)
        btn_exit.clicked.connect(self._prompt_exit_dialog)
        c_layout.addWidget(btn_exit)

        main_layout.addWidget(control_bar)

        self.stacked_widget = QStackedWidget(self)

        # SCREEN 1: Pre-flight System Check (Shares proctor_thread)
        self.screen_preflight = PreflightScreen(
            server_host=self.server_host,
            server_port=self.server_port,
            proctor_thread=self.proctor_thread
        )
        self.screen_preflight.preflight_passed.connect(self._goto_screen_login)
        self.stacked_widget.addWidget(self.screen_preflight)

        # SCREEN 2: Biometric Onboarding & Login
        self.screen_login = BiometricLoginScreen(net_client=self.net_client)
        self.screen_login.login_successful.connect(self._goto_screen_exam)
        self.stacked_widget.addWidget(self.screen_login)

        # SCREEN 3: Main Exam Screen (Instantiated upon login)
        self.screen_exam: Optional[ExamScreen] = None

        # SCREEN 4: Submission Receipt & QR Code Audit
        self.screen_receipt = SubmissionReceiptScreen()
        self.screen_receipt.exit_requested.connect(self.close)
        self.stacked_widget.addWidget(self.screen_receipt)

        main_layout.addWidget(self.stacked_widget)
        self.stacked_widget.setCurrentIndex(0)

    def _goto_screen_login(self) -> None:
        self.stacked_widget.setCurrentWidget(self.screen_login)

    def _goto_screen_exam(self, student_id: str, student_name: str, session_token: str) -> None:
        self.student_id = student_id
        self.student_name = student_name

        self.screen_exam = ExamScreen(
            net_client=self.net_client,
            student_id=student_id,
            student_name=student_name
        )
        self.screen_exam.exam_submitted.connect(self._goto_screen_receipt)
        
        self.stacked_widget.addWidget(self.screen_exam)
        self.stacked_widget.setCurrentWidget(self.screen_exam)

    def _goto_screen_receipt(self, receipt: dict, server_sig: str, client_sig: str) -> None:
        self.screen_receipt.set_receipt_data(receipt, server_sig, client_sig)
        self.stacked_widget.setCurrentWidget(self.screen_receipt)

    def _on_camera_frame(self, q_image) -> None:
        """Dynamically delivers real-time camera frames to whichever screen is currently active."""
        cur_widget = self.stacked_widget.currentWidget()
        if hasattr(cur_widget, "update_camera_frame"):
            cur_widget.update_camera_frame(q_image)

    def _on_ai_telemetry(self, yaw: float, pitch: float, roll: float, face_count: int) -> None:
        if self.screen_exam and self.stacked_widget.currentWidget() == self.screen_exam:
            self.screen_exam.update_telemetry(yaw, pitch, roll, face_count)

    def _on_ai_violation(self, v_type: str, details: str, evidence_jpeg: bytes) -> None:
        if self.screen_exam and self.stacked_widget.currentWidget() == self.screen_exam:
            self.screen_exam.log_violation(f"⚠️ [{v_type}] {details}")
        self.net_client.report_violation(v_type, details, evidence_jpeg)

    def _on_prohibited_process(self, proc_name: str, pid: int, desc: str) -> None:
        msg = f"Phát hiện phần mềm bị cấm: {proc_name} (PID: {pid}) - {desc}"
        if self.screen_exam and self.stacked_widget.currentWidget() == self.screen_exam:
            self.screen_exam.log_violation(f"🚨 [PROHIBITED_PROCESS] {msg}")
        self.net_client.report_violation("PROHIBITED_PROCESS", msg)

    def _on_multicast_command(self, cmd: CommandType, payload: dict) -> None:
        if self.screen_exam and self.stacked_widget.currentWidget() == self.screen_exam:
            if cmd == CommandType.CMD_EXAM_START:
                self.screen_exam.is_exam_active = True
                self.screen_exam.is_paused = False
                self.screen_exam.log_violation("📢 Giám thị: BẮT ĐẦU THI!")
            elif cmd == CommandType.CMD_EXAM_PAUSE:
                self.screen_exam.is_paused = True
                self.screen_exam.log_violation("⏸️ Giám thị: TẠM DỪNG THI!")
            elif cmd == CommandType.CMD_EXAM_RESUME:
                self.screen_exam.is_paused = False
                self.screen_exam.log_violation("▶️ Giám thị: TIẾP TỤC THI!")
            elif cmd == CommandType.CMD_EXAM_FINISH:
                self.screen_exam.log_violation("⏰ Giám thị: HẾT GIỜ LÀM BÀI! Tự động nộp bài...")
                self.screen_exam._execute_submit_exam()
            elif cmd == CommandType.CMD_ANNOUNCEMENT:
                self.screen_exam.log_violation(f"📢 Giám thị: {payload.get('message', '')}")

    def _toggle_fullscreen_mode(self) -> None:
        """Toggles between strict fullscreen Kiosk and convenient windowed mode."""
        if self.is_fullscreen_mode:
            self.is_fullscreen_mode = False
            self.showNormal()
            self.resize(1240, 820)
        else:
            self.is_fullscreen_mode = True
            self.showFullScreen()

    def _prompt_exit_dialog(self) -> None:
        """Safe exit confirmation dialog."""
        reply = QMessageBox.question(
            self,
            "Xác nhận thoát Kiosk",
            "Bạn có chắc chắn muốn đóng ứng dụng khảo thí?\n(Dành cho Giám thị / Thử nghiệm hệ thống)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.close()

    # --- KIOSK MODE: ANTI-ALT-TAB & FOCUS LOSS DETECTION ---
    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.ActivationChange:
            if not self.isActiveWindow():
                if self.screen_exam and self.stacked_widget.currentWidget() == self.screen_exam and not self.screen_exam.is_submitted:
                    self.screen_exam.log_violation("🚨 CẢNH BÁO: Mất tiêu điểm cửa sổ thi (Focus Lost / Alt-Tab)!")
                    self.net_client.report_violation("FOCUS_LOST", "Thí sinh chuyển đổi ứng dụng hoặc mở tab khác.")
        super().changeEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_F11:
            self._toggle_fullscreen_mode()
            return
        elif event.key() == Qt.Key.Key_Escape:
            self._prompt_exit_dialog()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        self.clipboard_sanitizer.stop()
        self.monitor_blocker.remove_blackouts()
        self.process_watchdog.stop()
        self.proctor_thread.stop()
        self.multicast_listener.stop()
        self.net_client.disconnect()
        event.accept()

    def _apply_dark_theme(self) -> None:
        self.setStyleSheet("""
            QWidget {
                background-color: #0F172A;
                color: #F8FAFC;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
        """)


def launch_client():
    app = QApplication(sys.argv)
    window = ExamMainWindow(server_host="127.0.0.1", server_port=8888)
    window.showFullScreen()
    sys.exit(app.exec())


if __name__ == "__main__":
    launch_client()
