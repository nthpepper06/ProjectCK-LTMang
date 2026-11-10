"""
Secure Examination & Proctoring Platform
client_desktop/ui/screen_login.py - Screen 2: Biometric Onboarding & Face Matching
"""

import os
import sys
import time

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QImage, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from client_desktop.network_client import NetworkClient


class BiometricLoginScreen(QWidget):
    """
    Screen 2: Candidate enters student credentials and aligns face in the camera
    to extract face embedding and authenticate against stored profile.
    """

    login_successful = pyqtSignal(str, str, str)  # (student_id, student_name, session_token)

    def __init__(self, net_client: NetworkClient, parent=None):
        super().__init__(parent)
        self.net_client = net_client
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(50, 40, 50, 40)
        main_layout.setSpacing(40)

        # LEFT PANE: Form input & Instructions
        left_layout = QVBoxLayout()
        left_layout.setSpacing(15)

        lbl_step = QLabel("BƯỚC 2: XÁC THỰC DANH TÍNH & SINH TRẮC HỌC")
        lbl_step.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        lbl_step.setStyleSheet("color: #60A5FA;")
        left_layout.addWidget(lbl_step)

        lbl_guide = QLabel("Nhập thông tin thí sinh và giữ thẳng khuôn mặt trong khung camera để so khớp với dữ liệu thẻ sinh viên.")
        lbl_guide.setFont(QFont("Segoe UI", 10))
        lbl_guide.setStyleSheet("color: #94A3B8;")
        lbl_guide.setWordWrap(True)
        left_layout.addWidget(lbl_guide)

        # Form Card
        form_card = QFrame()
        form_card.setStyleSheet("""
            background-color: #1E293B;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 20px;
        """)
        form_layout = QVBoxLayout(form_card)
        form_layout.setSpacing(12)

        lbl_id = QLabel("Mã số Sinh viên (MSSV):")
        lbl_id.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.txt_id = QLineEdit("SV2026_01")
        self.txt_id.setFont(QFont("Segoe UI", 11))
        self.txt_id.setStyleSheet("background-color: #0F172A; border: 1px solid #334155; border-radius: 6px; padding: 10px; color: white;")
        form_layout.addWidget(lbl_id)
        form_layout.addWidget(self.txt_id)

        lbl_name = QLabel("Họ và Tên Thí sinh:")
        lbl_name.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.txt_name = QLineEdit("Nguyễn Văn A")
        self.txt_name.setFont(QFont("Segoe UI", 11))
        self.txt_name.setStyleSheet("background-color: #0F172A; border: 1px solid #334155; border-radius: 6px; padding: 10px; color: white;")
        form_layout.addWidget(lbl_name)
        form_layout.addWidget(self.txt_name)

        lbl_exam = QLabel("Mã Kỳ thi:")
        lbl_exam.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.txt_exam = QLineEdit("LTM_2026_FINAL")
        self.txt_exam.setReadOnly(True)
        self.txt_exam.setFont(QFont("Segoe UI", 11))
        self.txt_exam.setStyleSheet("background-color: #1E293B; border: 1px solid #334155; border-radius: 6px; padding: 10px; color: #94A3B8;")
        form_layout.addWidget(lbl_exam)
        form_layout.addWidget(self.txt_exam)

        left_layout.addWidget(form_card)

        # Status and Action Button
        self.lbl_status = QLabel("Trạng thái: Sẵn sàng so khớp khuôn mặt.")
        self.lbl_status.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        self.lbl_status.setStyleSheet("color: #F59E0B;")
        left_layout.addWidget(self.lbl_status)

        self.btn_auth = QPushButton("📸 SO KHỚP KHUÔN MẶT & VÀO THI")
        self.btn_auth.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.btn_auth.setStyleSheet("""
            QPushButton {
                background-color: #2563EB; color: white; border-radius: 10px; padding: 14px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
            QPushButton:disabled { background-color: #475569; color: #94A3B8; }
        """)
        self.btn_auth.clicked.connect(self._perform_biometric_login)
        left_layout.addWidget(self.btn_auth)
        left_layout.addStretch()

        main_layout.addLayout(left_layout, 1)

        # RIGHT PANE: Camera Video Frame with Alignment Overlay
        right_layout = QVBoxLayout()
        right_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        cam_box = QFrame()
        cam_box.setStyleSheet("""
            background-color: #0D1117;
            border: 2px solid #3B82F6;
            border-radius: 16px;
            padding: 10px;
        """)
        cam_inner = QVBoxLayout(cam_box)
        cam_inner.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_camera_feed = QLabel("Đang mở luồng camera...")
        self.lbl_camera_feed.setFixedSize(480, 360)
        self.lbl_camera_feed.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_camera_feed.setStyleSheet("background-color: #000; border-radius: 10px;")
        cam_inner.addWidget(self.lbl_camera_feed)

        lbl_guide_overlay = QLabel("🎯 Căn chỉnh khuôn mặt chính diện vào khung hình")
        lbl_guide_overlay.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        lbl_guide_overlay.setStyleSheet("color: #60A5FA; margin-top: 8px;")
        lbl_guide_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cam_inner.addWidget(lbl_guide_overlay)

        right_layout.addWidget(cam_box)
        main_layout.addLayout(right_layout, 1)

    def update_camera_frame(self, q_image: QImage) -> None:
        """Renders live camera frames from AI proctor thread."""
        pixmap = QPixmap.fromImage(q_image)
        scaled = pixmap.scaled(
            self.lbl_camera_feed.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.lbl_camera_feed.setPixmap(scaled)

    def _perform_biometric_login(self) -> None:
        student_id = self.txt_id.text().strip()
        student_name = self.txt_name.text().strip()

        if not student_id or not student_name:
            QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập đầy đủ Mã số sinh viên và Họ tên!")
            return

        self.btn_auth.setEnabled(False)
        self.lbl_status.setText("Đang trích xuất Face Embedding và kết nối Server...")
        self.lbl_status.setStyleSheet("color: #60A5FA;")

        # Update client credentials
        self.net_client.student_id = student_id
        self.net_client.student_name = student_name

        # Connect to Server
        if not self.net_client.is_connected:
            connected = self.net_client.connect()
            if not connected:
                self.lbl_status.setText("❌ Không thể kết nối tới Exam TCP Server!")
                self.lbl_status.setStyleSheet("color: #EF4444;")
                self.btn_auth.setEnabled(True)
                return

        # Biometric Face Verification
        auth_success = self.net_client.authenticate_biometric(0.96)
        if auth_success:
            self.lbl_status.setText("✅ Xác thực sinh trắc học thành công! Cấp phiên thi...")
            self.lbl_status.setStyleSheet("color: #10B981;")
            session_token = f"JWT_EXAM_{student_id}_{int(time.time())}"
            self.login_successful.emit(student_id, student_name, session_token)
        else:
            self.lbl_status.setText("❌ Khuôn mặt không khớp với hồ sơ lưu trữ!")
            self.lbl_status.setStyleSheet("color: #EF4444;")
            self.btn_auth.setEnabled(True)
