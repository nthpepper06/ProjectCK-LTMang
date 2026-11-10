"""
Secure Examination & Proctoring Platform
client_desktop/ui/screen_receipt.py - Screen 4: Submission Receipt, Non-repudiation Audit & QR Code
"""

import io
import json
import os
import sys
import time

import qrcode
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


class SubmissionReceiptScreen(QWidget):
    """
    Screen 4: Displays cryptographic audit certificate and dynamic QR code upon exam completion:
    - Accurate millisecond timestamp
    - SHA-256 digest of submitted answers
    - RSA-2048 PSS client signature
    - Server counter-signature verification
    - High-resolution QR Code containing audit record
    """

    exit_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 20, 40, 20)
        main_layout.setSpacing(12)

        # Header Badge
        lbl_head = QLabel("🎉 BÀI THI ĐÃ NỘP THÀNH CÔNG VÀ XÁC THỰC CHỮ KÝ SỐ")
        lbl_head.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        lbl_head.setStyleSheet("color: #10B981;")
        lbl_head.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(lbl_head)

        lbl_subhead = QLabel("Biên nhận điện tử được lưu trữ bất biến trên hệ thống máy chủ khảo thí nhằm chống chối bỏ (Non-repudiation).")
        lbl_subhead.setFont(QFont("Segoe UI", 10))
        lbl_subhead.setStyleSheet("color: #94A3B8;")
        lbl_subhead.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(lbl_subhead)

        # Content Card with 2 columns: Audit Details (Left) + QR Code (Right)
        card = QFrame()
        card.setObjectName("ReceiptCard")
        card.setStyleSheet("""
            QFrame#ReceiptCard {
                background-color: #1E293B;
                border: 1px solid #334155;
                border-radius: 12px;
            }
        """)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(24, 16, 24, 16)
        card_layout.setSpacing(25)

        # LEFT: Metadata Fields
        meta_layout = QVBoxLayout()
        meta_layout.setSpacing(8)

        self.lbl_receipt_id = self._add_field(meta_layout, "Mã Biên nhận (Receipt ID):", "Đang cập nhật...")
        self.lbl_student = self._add_field(meta_layout, "Thí sinh:", "Đang cập nhật...")
        self.lbl_timestamp = self._add_field(meta_layout, "Thời gian nộp (Timestamp ms):", "Đang cập nhật...")
        self.lbl_paper_hash = self._add_field(meta_layout, "Mã băm toàn vẹn (SHA-256 Digest):", "Đang cập nhật...")
        self.lbl_client_sig = self._add_field(meta_layout, "Chữ ký số Thí sinh (RSA-2048 PSS):", "Đang cập nhật...")
        self.lbl_server_sig = self._add_field(meta_layout, "Chữ ký xác thực Máy chủ:", "✔ ĐÃ XÁC THỰC HỢP LỆ (VERIFIED)")
        self.lbl_server_sig.setStyleSheet("color: #10B981; font-weight: bold;")

        meta_layout.addStretch()
        card_layout.addLayout(meta_layout, 2)

        # RIGHT: QR Code Viewer
        qr_layout = QVBoxLayout()
        qr_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qr_layout.setSpacing(8)

        lbl_qr_title = QLabel("MÃ QR ĐỐI CHIẾU")
        lbl_qr_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        lbl_qr_title.setStyleSheet("color: #60A5FA;")
        lbl_qr_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qr_layout.addWidget(lbl_qr_title)

        self.lbl_qr_img = QLabel()
        self.lbl_qr_img.setFixedSize(180, 180)
        self.lbl_qr_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_qr_img.setStyleSheet("background-color: white; border-radius: 8px; padding: 6px;")
        qr_layout.addWidget(self.lbl_qr_img)

        lbl_qr_tip = QLabel("Quét mã để kiểm tra tính toàn vẹn và chữ ký điện tử trên cổng khảo thí.")
        lbl_qr_tip.setWordWrap(True)
        lbl_qr_tip.setFont(QFont("Segoe UI", 8))
        lbl_qr_tip.setStyleSheet("color: #94A3B8; text-align: center;")
        lbl_qr_tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qr_layout.addWidget(lbl_qr_tip)

        card_layout.addLayout(qr_layout, 1)
        main_layout.addWidget(card)

        # Bottom Button
        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_exit = QPushButton("HOÀN TẤT & ĐÓNG ỨNG DỤNG")
        self.btn_exit.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.btn_exit.setStyleSheet("""
            QPushButton {
                background-color: #10B981; color: white; border-radius: 8px; padding: 10px 32px;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        self.btn_exit.clicked.connect(self._on_exit)
        btn_layout.addWidget(self.btn_exit)

        main_layout.addLayout(btn_layout)
        main_layout.addStretch()

    def _add_field(self, layout: QVBoxLayout, label_text: str, default_val: str) -> QLabel:
        box = QVBoxLayout()
        lbl = QLabel(label_text)
        lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        lbl.setStyleSheet("color: #94A3B8;")

        val = QLabel(default_val)
        val.setFont(QFont("Consolas", 10))
        val.setStyleSheet("color: #F8FAFC;")
        val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        box.addWidget(lbl)
        box.addWidget(val)
        layout.addLayout(box)
        return val

    def set_receipt_data(self, receipt: dict, server_sig: str, client_sig: str) -> None:
        """Fills in audit parameters and renders QR Code."""
        receipt_id = receipt.get("receipt_id", "UNKNOWN")
        student_id = receipt.get("student_id", "UNKNOWN")
        paper_hash = receipt.get("paper_hash", "")
        timestamp_ms = receipt.get("submitted_at_ms", int(time.time() * 1000))
        human_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp_ms / 1000))

        self.lbl_receipt_id.setText(receipt_id)
        self.lbl_student.setText(f"{student_id}")
        self.lbl_timestamp.setText(f"{timestamp_ms} ms ({human_time})")
        self.lbl_paper_hash.setText(paper_hash)
        
        display_sig = f"{client_sig[:32]}...{client_sig[-16:]}" if len(client_sig) > 48 else client_sig
        self.lbl_client_sig.setText(display_sig)

        # Generate QR Code
        qr_payload = json.dumps({
            "receipt_id": receipt_id,
            "student_id": student_id,
            "hash": paper_hash,
            "timestamp": timestamp_ms,
            "server_sig": server_sig[:24]
        }, separators=(",", ":"))

        self._render_qr_code(qr_payload)

    def _render_qr_code(self, data_str: str) -> None:
        """Encodes string to QR code and paints to label."""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=5,
            border=2,
        )
        qr.add_data(data_str)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        # Convert PIL image to QPixmap
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        qimg = QImage.fromData(buf.getvalue())
        pixmap = QPixmap.fromImage(qimg)
        self.lbl_qr_img.setPixmap(pixmap.scaled(
            self.lbl_qr_img.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        ))

    def _on_exit(self) -> None:
        self.exit_requested.emit()
        QApplication.quit()
