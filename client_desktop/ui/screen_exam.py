"""
Secure Examination & Proctoring Platform
client_desktop/ui/screen_exam.py - Screen 3: Optimized Exam View with Question Palette, Local Auto-Save & Auto-Reconnect
"""

import os
import sys
import time
from typing import Any, Dict, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QImage, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from client_desktop.network_client import NetworkClient
from client_desktop.storage.local_db import LocalDraftStorage
from common.protocol import CommandType


class SubmissionConfirmationDialog(QDialog):
    """Modal displaying answered vs unanswered question statistics before final submission."""

    def __init__(self, total: int, done: int, not_done: int, review: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Xác nhận Nộp bài thi")
        self.setFixedSize(450, 320)
        self.setStyleSheet("background-color: #1E293B; color: #F8FAFC;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(15)

        lbl_head = QLabel("XÁC NHẬN NỘP BÀI THI & KÝ SỐ")
        lbl_head.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        lbl_head.setStyleSheet("color: #60A5FA;")
        layout.addWidget(lbl_head)

        lbl_desc = QLabel("Vui lòng rà soát thống kê các câu hỏi trước khi đóng bài:")
        lbl_desc.setFont(QFont("Segoe UI", 10))
        layout.addWidget(lbl_desc)

        # Stats summary box
        box = QFrame()
        box.setStyleSheet("background-color: #0F172A; border: 1px solid #334155; border-radius: 8px; padding: 12px;")
        box_layout = QVBoxLayout(box)

        lbl_total = QLabel(f"• Tổng số câu hỏi: <b>{total} câu</b>")
        lbl_done = QLabel(f"• Đã hoàn thành câu trả lời: <b style='color: #10B981;'>{done} câu</b>")
        lbl_not_done = QLabel(f"• Chưa trả lời: <b style='color: #EF4444;'>{not_done} câu</b>")
        lbl_review = QLabel(f"• Câu đánh dấu cần xem lại: <b style='color: #F59E0B;'>{review} câu</b>")

        for lbl in (lbl_total, lbl_done, lbl_not_done, lbl_review):
            lbl.setFont(QFont("Segoe UI", 10))
            box_layout.addWidget(lbl)

        layout.addWidget(box)

        lbl_note = QLabel("⚠️ Lưu ý: Sau khi nộp, bài làm sẽ được băm SHA-256 và ký số điện tử RSA 2048-bit để chống chối bỏ. Bạn sẽ không thể sửa đổi câu trả lời.")
        lbl_note.setWordWrap(True)
        lbl_note.setFont(QFont("Segoe UI", 9))
        lbl_note.setStyleSheet("color: #94A3B8;")
        layout.addWidget(lbl_note)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Quay lại làm tiếp")
        btn_cancel.setStyleSheet("background-color: #334155; color: white; border-radius: 6px; padding: 8px 16px;")
        btn_cancel.clicked.connect(self.reject)

        btn_confirm = QPushButton("XÁC NHẬN NỘP BÀI")
        btn_confirm.setStyleSheet("background-color: #2563EB; color: white; font-weight: bold; border-radius: 6px; padding: 8px 20px;")
        btn_confirm.clicked.connect(self.accept)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_confirm)
        layout.addLayout(btn_layout)


class ExamScreen(QWidget):
    """
    Screen 3: Main exam taking screen featuring:
    - Left Question Palette (Done / Not Done / Mark for Review)
    - Center scrollable exam question paper with auto-save
    - Real-time Network widget with auto-reconnect background thread
    - Right AI Proctoring video monitor
    """

    exam_submitted = pyqtSignal(dict, str, str)  # (receipt_dict, server_sig, student_sig)
    violation_occurred = pyqtSignal(str, str, bytes)

    def __init__(self, net_client: NetworkClient, student_id: str, student_name: str, parent=None):
        super().__init__(parent)
        self.net_client = net_client
        self.student_id = student_id
        self.student_name = student_name

        self.exam_id = "LTM_2026_FINAL"
        self.storage = LocalDraftStorage()
        self.time_remaining_seconds = 3600
        self.is_exam_active = False
        self.is_paused = False
        self.is_submitted = False

        # Data structures for questions and UI widgets
        self.questions_data: list = []
        self.answers_widgets: Dict[int, QTextEdit] = {}
        self.review_checkboxes: Dict[int, QCheckBox] = {}
        self.palette_buttons: Dict[int, QPushButton] = {}
        self.question_frames: Dict[int, QFrame] = {}

        self._init_ui()

        # Local Auto-Save Timer (every 15 seconds)
        self.auto_save_timer = QTimer(self)
        self.auto_save_timer.timeout.connect(self._auto_save_all)
        self.auto_save_timer.start(15000)

        # Network Ping & Auto-Reconnect Watcher Timer (every 4 seconds)
        self.net_watch_timer = QTimer(self)
        self.net_watch_timer.timeout.connect(self._check_network_status)
        self.net_watch_timer.start(4000)

        # Exam Countdown Timer (every 1 second)
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self._on_timer_tick)

        # Load questions paper from server or fallback
        QTimer.singleShot(200, self._load_exam_paper)

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 12, 15, 12)
        main_layout.setSpacing(10)

        # TOP BAR
        top_bar = QFrame()
        top_bar.setStyleSheet("""
            background-color: #1A2332;
            border: 1px solid #2D3748;
            border-radius: 8px;
            padding: 8px 14px;
        """)
        top_layout = QHBoxLayout(top_bar)

        self.lbl_title = QLabel("KỲ THI CUỐI KỲ LẬP TRÌNH MẠNG")
        self.lbl_title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.lbl_title.setStyleSheet("color: #60A5FA;")

        self.lbl_candidate = QLabel(f"Thí sinh: <b>{self.student_name}</b> ({self.student_id})")
        self.lbl_candidate.setFont(QFont("Segoe UI", 10))

        # Real-time Network Status Widget
        self.lbl_net_widget = QLabel("🌐 Ping: 12ms [Ổn định]")
        self.lbl_net_widget.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.lbl_net_widget.setStyleSheet("color: #10B981; background-color: #0F172A; padding: 4px 10px; border-radius: 6px;")

        # Auto-save status label
        self.lbl_autosave = QLabel("💾 Đã lưu nháp")
        self.lbl_autosave.setFont(QFont("Segoe UI", 9))
        self.lbl_autosave.setStyleSheet("color: #94A3B8;")

        # Timer countdown
        self.lbl_countdown = QLabel("Thời gian: 60:00")
        self.lbl_countdown.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        self.lbl_countdown.setStyleSheet("color: #F59E0B;")

        top_layout.addWidget(self.lbl_title)
        top_layout.addStretch()
        top_layout.addWidget(self.lbl_candidate)
        top_layout.addSpacing(15)
        top_layout.addWidget(self.lbl_autosave)
        top_layout.addSpacing(15)
        top_layout.addWidget(self.lbl_net_widget)
        top_layout.addSpacing(15)
        top_layout.addWidget(self.lbl_countdown)
        main_layout.addWidget(top_bar)

        # MAIN CONTENT (3 PANELS: Palette - Question Paper - Camera Proctor)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(12)

        # 1. LEFT PANEL: Question Palette
        palette_frame = QFrame()
        palette_frame.setFixedWidth(200)
        palette_frame.setStyleSheet("background-color: #1A2332; border: 1px solid #2D3748; border-radius: 8px; padding: 8px;")
        palette_layout = QVBoxLayout(palette_frame)
        palette_layout.setSpacing(8)

        lbl_palette_head = QLabel("BẢNG CÂU HỎI")
        lbl_palette_head.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        lbl_palette_head.setStyleSheet("color: #E2E8F0;")
        palette_layout.addWidget(lbl_palette_head)

        # Legend explanation
        legend_layout = QVBoxLayout()
        legend_layout.setSpacing(4)
        for text, color in [("✔ Đã làm", "#10B981"), ("- Chưa làm", "#64748B"), ("★ Xem lại", "#F59E0B")]:
            lbl = QLabel(text)
            lbl.setFont(QFont("Segoe UI", 9))
            lbl.setStyleSheet(f"color: {color};")
            legend_layout.addWidget(lbl)
        palette_layout.addLayout(legend_layout)

        # Grid for question numbers
        palette_scroll = QScrollArea()
        palette_scroll.setWidgetResizable(True)
        self.palette_container = QWidget()
        self.palette_grid = QGridLayout(self.palette_container)
        self.palette_grid.setSpacing(6)
        palette_scroll.setWidget(self.palette_container)
        palette_layout.addWidget(palette_scroll)

        content_layout.addWidget(palette_frame)

        # 2. CENTER PANEL: Scrollable Exam Paper
        paper_frame = QFrame()
        paper_frame.setStyleSheet("background-color: #121820; border: 1px solid #2D3748; border-radius: 8px;")
        paper_layout = QVBoxLayout(paper_frame)
        paper_layout.setContentsMargins(10, 10, 10, 10)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.questions_container = QWidget()
        self.questions_layout = QVBoxLayout(self.questions_container)
        self.questions_layout.setSpacing(14)
        self.scroll_area.setWidget(self.questions_container)
        paper_layout.addWidget(self.scroll_area)

        # Submit Button
        btn_bar = QHBoxLayout()
        self.btn_submit = QPushButton("📝 NỘP BÀI THI & XÁC NHẬN CHỮ KÝ SỐ RSA")
        self.btn_submit.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.btn_submit.setStyleSheet("""
            QPushButton {
                background-color: #2563EB; color: white; border-radius: 8px; padding: 12px 24px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
            QPushButton:disabled { background-color: #475569; color: #94A3B8; }
        """)
        self.btn_submit.clicked.connect(self._prompt_submit_confirmation)
        btn_bar.addStretch()
        btn_bar.addWidget(self.btn_submit)
        paper_layout.addLayout(btn_bar)

        content_layout.addWidget(paper_frame, 3)

        # 3. RIGHT PANEL: AI Proctor Video Preview & Security telemetry
        proctor_frame = QFrame()
        proctor_frame.setFixedWidth(290)
        proctor_frame.setStyleSheet("background-color: #1A2332; border: 1px solid #2D3748; border-radius: 8px; padding: 10px;")
        proctor_layout = QVBoxLayout(proctor_frame)
        proctor_layout.setSpacing(8)

        lbl_proctor_head = QLabel("GIÁM SÁT AI REAL-TIME")
        lbl_proctor_head.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        lbl_proctor_head.setStyleSheet("color: #60A5FA;")
        proctor_layout.addWidget(lbl_proctor_head)

        # Camera preview
        self.lbl_camera = QLabel("Đang mở camera...")
        self.lbl_camera.setFixedSize(270, 200)
        self.lbl_camera.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_camera.setStyleSheet("background-color: #0D1117; border: 2px solid #3B82F6; border-radius: 6px;")
        proctor_layout.addWidget(self.lbl_camera)

        # Telemetry stats
        self.lbl_telemetry = QLabel("Góc đầu: Yaw 0.0° | Pitch 0.0°\nKhuôn mặt: 1 | Trạng thái: An toàn")
        self.lbl_telemetry.setFont(QFont("Consolas", 9))
        self.lbl_telemetry.setStyleSheet("color: #E2E8F0; background-color: #0F172A; padding: 6px; border-radius: 4px;")
        proctor_layout.addWidget(self.lbl_telemetry)

        # Violation log
        lbl_v_title = QLabel("NHẬT KÝ CẢNH BÁO VI PHẠM:")
        lbl_v_title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        proctor_layout.addWidget(lbl_v_title)

        self.txt_violation_log = QTextEdit()
        self.txt_violation_log.setReadOnly(True)
        self.txt_violation_log.setFont(QFont("Consolas", 8))
        self.txt_violation_log.setStyleSheet("background-color: #0F172A; color: #F87171; border: 1px solid #334155; border-radius: 4px;")
        self.txt_violation_log.setMaximumHeight(160)
        proctor_layout.addWidget(self.txt_violation_log)

        proctor_layout.addStretch()
        content_layout.addWidget(proctor_frame)

        main_layout.addLayout(content_layout)

    def _load_exam_paper(self) -> None:
        """Fetches questions from server or loads defaults and restores local drafts."""
        paper = self.net_client.request_exam_paper()
        if not paper or "questions" not in paper:
            # Fallback nominal questions
            paper = {
                "exam_id": "LTM_2026_FINAL",
                "title": "Kỳ thi Cuối kỳ Lập trình Mạng & An toàn Hệ thống",
                "duration_minutes": 60,
                "questions": [
                    {
                        "id": 1,
                        "question": "Phân tích cơ chế bắt tay 3 bước (Three-way handshake) của TCP và cách phòng chống tấn công SYN Flood.",
                        "type": "essay"
                    },
                    {
                        "id": 2,
                        "question": "So sánh ưu nhược điểm của giao thức UDP Multicast so với TCP Unicast trong việc đồng bộ hóa dữ liệu cho hàng trăm máy thi.",
                        "type": "essay"
                    },
                    {
                        "id": 3,
                        "question": "Trình bày vai trò của Chữ ký số (Digital Signature) và hàm băm SHA-256 trong việc chống chối bỏ bài thi trực tuyến.",
                        "type": "essay"
                    }
                ]
            }

        self.exam_id = paper.get("exam_id", self.exam_id)
        self.lbl_title.setText(paper.get("title", self.lbl_title.text()))
        self.questions_data = paper.get("questions", [])
        self.time_remaining_seconds = paper.get("duration_minutes", 60) * 60

        # Load any saved local drafts
        cached_drafts = self.storage.load_drafts(self.student_id, self.exam_id)

        # Populate UI
        self._build_questions_ui(cached_drafts)
        self._build_palette_ui(cached_drafts)

        # Unlock exam & start timer
        self.is_exam_active = True
        self.countdown_timer.start(1000)

    def _build_questions_ui(self, cached_drafts: dict) -> None:
        for q in self.questions_data:
            q_id = q["id"]
            box = QFrame()
            box.setObjectName(f"QuestionBox_{q_id}")
            box.setStyleSheet("""
                background-color: #1E293B;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 12px;
            """)
            layout = QVBoxLayout(box)

            q_title = QLabel(f"<b>Câu {q_id}:</b> {q['question']}")
            q_title.setWordWrap(True)
            q_title.setFont(QFont("Segoe UI", 11))
            q_title.setStyleSheet("color: #F8FAFC;")
            layout.addWidget(q_title)

            # Answer input
            ans_input = QTextEdit()
            ans_input.setPlaceholderText("Nhập câu trả lời của bạn tại đây...")
            ans_input.setFont(QFont("Segoe UI", 10))
            ans_input.setStyleSheet("background-color: #0F172A; border: 1px solid #334155; border-radius: 6px; color: white; padding: 8px;")
            ans_input.setMinimumHeight(130)

            # Restore cached answer if exists
            if q_id in cached_drafts:
                ans_input.setPlainText(cached_drafts[q_id].get("answer_text", ""))

            ans_input.textChanged.connect(lambda qid=q_id: self._on_answer_changed(qid))
            layout.addWidget(ans_input)

            # Review Checkbox
            chk_review = QCheckBox("★ Đánh dấu câu này để xem lại sau")
            chk_review.setFont(QFont("Segoe UI", 9))
            chk_review.setStyleSheet("color: #F59E0B;")
            if q_id in cached_drafts and cached_drafts[q_id].get("status") == "REVIEW":
                chk_review.setChecked(True)
            chk_review.toggled.connect(lambda checked, qid=q_id: self._on_review_toggled(qid, checked))
            layout.addWidget(chk_review)

            self.answers_widgets[q_id] = ans_input
            self.review_checkboxes[q_id] = chk_review
            self.question_frames[q_id] = box
            self.questions_layout.addWidget(box)

        self.questions_layout.addStretch()

    def _build_palette_ui(self, cached_drafts: dict) -> None:
        cols = 3
        for idx, q in enumerate(self.questions_data):
            q_id = q["id"]
            btn = QPushButton(f"Câu {q_id}")
            btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            btn.setFixedSize(50, 40)
            btn.clicked.connect(lambda _, qid=q_id: self._scroll_to_question(qid))

            # Determine initial status
            status = "NOT_DONE"
            if q_id in cached_drafts:
                status = cached_drafts[q_id].get("status", "NOT_DONE")
            elif self.answers_widgets[q_id].toPlainText().strip():
                status = "DONE"

            self._set_palette_btn_style(btn, status)
            self.palette_buttons[q_id] = btn
            self.palette_grid.addWidget(btn, idx // cols, idx % cols)

    def _scroll_to_question(self, q_id: int) -> None:
        """Smoothly scrolls the view to the selected question."""
        if q_id in self.question_frames:
            target_widget = self.question_frames[q_id]
            self.scroll_area.ensureWidgetVisible(target_widget)

    def _on_answer_changed(self, q_id: int) -> None:
        """Triggered on keystroke: updates palette and triggers auto-save."""
        text = self.answers_widgets[q_id].toPlainText().strip()
        is_review = self.review_checkboxes[q_id].isChecked()

        if is_review:
            new_status = "REVIEW"
        elif text:
            new_status = "DONE"
        else:
            new_status = "NOT_DONE"

        if q_id in self.palette_buttons:
            self._set_palette_btn_style(self.palette_buttons[q_id], new_status)

    def _on_review_toggled(self, q_id: int, checked: bool) -> None:
        text = self.answers_widgets[q_id].toPlainText().strip()
        status = "REVIEW" if checked else ("DONE" if text else "NOT_DONE")
        if q_id in self.palette_buttons:
            self._set_palette_btn_style(self.palette_buttons[q_id], status)

    def _set_palette_btn_style(self, btn: QPushButton, status: str) -> None:
        if status == "DONE":
            btn.setStyleSheet("background-color: #10B981; color: white; border-radius: 6px; border: 1px solid #059669;")
        elif status == "REVIEW":
            btn.setStyleSheet("background-color: #F59E0B; color: #1E293B; border-radius: 6px; border: 1px solid #D97706; font-weight: bold;")
        else:
            btn.setStyleSheet("background-color: #334155; color: #94A3B8; border-radius: 6px; border: 1px solid #475569;")

    def _auto_save_all(self) -> None:
        """Persists all answers and review statuses to local SQLite database."""
        answers = {qid: w.toPlainText() for qid, w in self.answers_widgets.items()}
        statuses = {}
        for qid in answers:
            if self.review_checkboxes[qid].isChecked():
                statuses[qid] = "REVIEW"
            elif answers[qid].strip():
                statuses[qid] = "DONE"
            else:
                statuses[qid] = "NOT_DONE"

        ts = self.storage.save_all_drafts(self.student_id, self.exam_id, answers, statuses)
        time_str = time.strftime("%H:%M:%S", time.localtime(ts))
        self.lbl_autosave.setText(f"💾 Tự động lưu: {time_str}")

    def _check_network_status(self) -> None:
        """Monitors network socket status and triggers background auto-reconnect if dropped."""
        if self.net_client and self.net_client.is_connected:
            self.lbl_net_widget.setText("🌐 Ping: <50ms [Ổn định]")
            self.lbl_net_widget.setStyleSheet("color: #10B981; background-color: #0F172A; padding: 4px 10px; border-radius: 6px;")
        else:
            self.lbl_net_widget.setText("⚠️ Rớt mạng: Đang thử kết nối lại...")
            self.lbl_net_widget.setStyleSheet("color: #EF4444; background-color: #0F172A; padding: 4px 10px; border-radius: 6px;")
            # Attempt non-blocking reconnect
            QTimer.singleShot(100, self._attempt_reconnect)

    def _attempt_reconnect(self) -> None:
        if self.net_client and not self.net_client.is_connected:
            self.net_client.connect()

    def _on_timer_tick(self) -> None:
        if self.is_paused or not self.is_exam_active:
            return
        if self.time_remaining_seconds > 0:
            self.time_remaining_seconds -= 1
            m = self.time_remaining_seconds // 60
            s = self.time_remaining_seconds % 60
            self.lbl_countdown.setText(f"Thời gian: {m:02d}:{s:02d}")
        else:
            self.countdown_timer.stop()
            self._execute_submit_exam()

    def update_camera_frame(self, q_image: QImage) -> None:
        pixmap = QPixmap.fromImage(q_image)
        scaled = pixmap.scaled(
            self.lbl_camera.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.lbl_camera.setPixmap(scaled)

    def update_telemetry(self, yaw: float, pitch: float, roll: float, face_count: int) -> None:
        status_text = "An toàn" if face_count == 1 and abs(yaw) <= 25 and abs(pitch) <= 20 else "Nghi vấn"
        self.lbl_telemetry.setText(
            f"Góc đầu: Yaw {yaw:+.1f}° | Pitch {pitch:+.1f}°\n"
            f"Khuôn mặt: {face_count} | Đánh giá: {status_text}"
        )

    def log_violation(self, text: str) -> None:
        ts = time.strftime("%H:%M:%S")
        self.txt_violation_log.append(f"[{ts}] {text}")

    def _prompt_submit_confirmation(self) -> None:
        """Opens modal review dialog displaying completion counts."""
        total = len(self.questions_data)
        done = 0
        not_done = 0
        review = 0

        for qid, w in self.answers_widgets.items():
            txt = w.toPlainText().strip()
            is_rev = self.review_checkboxes[qid].isChecked()
            if is_rev:
                review += 1
            if txt:
                done += 1
            else:
                not_done += 1

        modal = SubmissionConfirmationDialog(total, done, not_done, review, self)
        if modal.exec() == QDialog.DialogCode.Accepted:
            self._execute_submit_exam()

    def _execute_submit_exam(self) -> None:
        if self.is_submitted:
            return
        self.is_submitted = True
        self.countdown_timer.stop()
        self.btn_submit.setEnabled(False)

        # Collect student answers
        answers = {qid: w.toPlainText() for qid, w in self.answers_widgets.items()}

        # Final auto-save
        self._auto_save_all()

        # Submit to server with digital signature
        self.log_violation("Đang ký số RSA 2048-bit và nộp bài thi lên server...")
        res = self.net_client.submit_exam_paper(self.exam_id, answers)

        if res.get("success"):
            # Clear local drafts upon confirmed server receipt
            self.storage.clear_drafts(self.student_id, self.exam_id)
            receipt = res.get("receipt", {})
            server_sig = res.get("server_signature", "")
            student_sig = res.get("student_signature", "")
            self.exam_submitted.emit(receipt, server_sig, student_sig)
        else:
            QMessageBox.critical(self, "Lỗi nộp bài", f"Lỗi từ máy chủ: {res.get('error')}")
            self.btn_submit.setEnabled(True)
            self.is_submitted = False
