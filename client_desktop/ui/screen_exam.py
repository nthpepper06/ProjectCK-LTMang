"""
Secure Examination & Proctoring Platform
client_desktop/ui/screen_exam.py - Screen 3: Optimized Exam View with Question Palette, Local Auto-Save & Sticky Bottom Bar
"""

import os
import sys
import time
from typing import Any, Dict, Optional

from PyQt6.QtCore import QEvent, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QImage, QPixmap, QWheelEvent
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from client_desktop.network_client import NetworkClient
from client_desktop.storage.local_db import LocalDraftStorage
from client_desktop.ui.cyber_camera_hud import CyberCameraHUD


class SubmissionConfirmationDialog(QDialog):
    """Modal displaying answered vs unanswered question statistics before final submission."""

    def __init__(self, total: int, done: int, not_done: int, review: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Xác nhận Nộp bài thi")
        self.setFixedSize(460, 330)
        self.setStyleSheet("background-color: #1E293B; color: #F8FAFC;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(14)

        lbl_head = QLabel("XÁC NHẬN NỘP BÀI THI & KÝ SỐ RSA")
        lbl_head.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        lbl_head.setStyleSheet("color: #60A5FA;")
        layout.addWidget(lbl_head)

        lbl_desc = QLabel("Vui lòng kiểm tra kỹ số lượng câu trả lời trước khi đóng bài:")
        lbl_desc.setFont(QFont("Segoe UI", 10))
        layout.addWidget(lbl_desc)

        box = QFrame()
        box.setStyleSheet("background-color: #0F172A; border: 1px solid #334155; border-radius: 8px; padding: 12px;")
        box_layout = QVBoxLayout(box)

        lbl_total = QLabel(f"• Tổng số câu hỏi: <b>{total} câu</b>")
        lbl_done = QLabel(f"• Đã hoàn thành câu trả lời: <b style='color: #10B981;'>{done} câu</b>")
        lbl_not_done = QLabel(f"• Chưa hoàn thành: <b style='color: #EF4444;'>{not_done} câu</b>")
        lbl_review = QLabel(f"• Đánh dấu cần xem lại: <b style='color: #F59E0B;'>{review} câu</b>")

        for lbl in (lbl_total, lbl_done, lbl_not_done, lbl_review):
            lbl.setFont(QFont("Segoe UI", 10))
            box_layout.addWidget(lbl)
        layout.addWidget(box)

        lbl_note = QLabel("⚠️ Bài làm sẽ được ký số bằng khóa bí mật RSA 2048-bit và gửi biên lai xác thực từ máy chủ.")
        lbl_note.setWordWrap(True)
        lbl_note.setFont(QFont("Segoe UI", 9))
        lbl_note.setStyleSheet("color: #94A3B8;")
        layout.addWidget(lbl_note)

        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Quay lại làm tiếp")
        btn_cancel.setStyleSheet("background-color: #334155; color: white; border-radius: 6px; padding: 9px 18px;")
        btn_cancel.clicked.connect(self.reject)

        btn_confirm = QPushButton("XÁC NHẬN NỘP BÀI")
        btn_confirm.setStyleSheet("background-color: #2563EB; color: white; font-weight: bold; border-radius: 6px; padding: 9px 24px;")
        btn_confirm.clicked.connect(self.accept)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_confirm)
        layout.addLayout(btn_layout)


class ExamScreen(QWidget):
    """
    Screen 3: Main exam screen with:
    - Left Question Palette
    - Center scrollable questions with mouse-wheel pass-through
    - Sticky bottom bar with Submit button always accessible
    - Real-time Network widget & AI proctor feed
    """

    exam_submitted = pyqtSignal(dict, str, str)
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

        self.questions_data: list = []
        self.answers_widgets: Dict[int, QTextEdit] = {}
        self.review_checkboxes: Dict[int, QCheckBox] = {}
        self.palette_buttons: Dict[int, QPushButton] = {}
        self.question_frames: Dict[int, QFrame] = {}

        self._init_ui()

        # Timers
        self.auto_save_timer = QTimer(self)
        self.auto_save_timer.timeout.connect(self._auto_save_all)
        self.auto_save_timer.start(15000)

        self.net_watch_timer = QTimer(self)
        self.net_watch_timer.timeout.connect(self._check_network_status)
        self.net_watch_timer.start(4000)

        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self._on_timer_tick)

        QTimer.singleShot(150, self._load_exam_paper)

    def _init_ui(self) -> None:
        self.setMinimumSize(900, 520)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 8, 14, 8)
        main_layout.setSpacing(8)

        # 1. TOP HEADER BAR
        top_bar = QFrame()
        top_bar.setObjectName("ExamTopBar")
        top_bar.setFixedHeight(50)
        top_bar.setStyleSheet("""
            QFrame#ExamTopBar {
                background-color: #1A2332;
                border: 1px solid #2D3748;
                border-radius: 8px;
            }
        """)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(14, 6, 14, 6)

        self.lbl_title = QLabel("KỲ THI CUỐI KỲ LẬP TRÌNH MẠNG & AN TOÀN HỆ THỐNG")
        self.lbl_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.lbl_title.setStyleSheet("color: #60A5FA;")

        self.lbl_candidate = QLabel(f"Thí sinh: <b>{self.student_name}</b> ({self.student_id})")
        self.lbl_candidate.setFont(QFont("Segoe UI", 10))

        self.lbl_net_widget = QLabel("🌐 Ping: <50ms [Ổn định]")
        self.lbl_net_widget.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.lbl_net_widget.setStyleSheet("color: #10B981; background-color: #0F172A; padding: 4px 10px; border-radius: 6px;")

        self.lbl_countdown = QLabel("Thời gian: 60:00")
        self.lbl_countdown.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.lbl_countdown.setStyleSheet("color: #F59E0B;")

        top_layout.addWidget(self.lbl_title)
        top_layout.addStretch()
        top_layout.addWidget(self.lbl_candidate)
        top_layout.addSpacing(15)
        top_layout.addWidget(self.lbl_net_widget)
        top_layout.addSpacing(15)
        top_layout.addWidget(self.lbl_countdown)
        main_layout.addWidget(top_bar)

        # 2. MIDDLE CONTENT (Question Palette | Scrollable Exam Paper | AI Monitor)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(10)

        # LEFT PANEL: Question Palette
        palette_frame = QFrame()
        palette_frame.setObjectName("ExamPaletteFrame")
        palette_frame.setFixedWidth(200)
        palette_frame.setStyleSheet("""
            QFrame#ExamPaletteFrame {
                background-color: #1A2332;
                border: 1px solid #2D3748;
                border-radius: 8px;
            }
        """)
        palette_layout = QVBoxLayout(palette_frame)
        palette_layout.setContentsMargins(8, 10, 8, 10)
        palette_layout.setSpacing(8)

        lbl_palette_head = QLabel("BẢNG CÂU HỎI")
        lbl_palette_head.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        lbl_palette_head.setStyleSheet("color: #E2E8F0;")
        palette_layout.addWidget(lbl_palette_head)

        legend_layout = QVBoxLayout()
        legend_layout.setSpacing(3)
        for text, color in [("✔ Đã làm", "#10B981"), ("- Chưa làm", "#64748B"), ("★ Xem lại", "#F59E0B")]:
            lbl = QLabel(text)
            lbl.setFont(QFont("Segoe UI", 8))
            lbl.setStyleSheet(f"color: {color};")
            legend_layout.addWidget(lbl)
        palette_layout.addLayout(legend_layout)

        palette_scroll = QScrollArea()
        palette_scroll.setWidgetResizable(True)
        palette_scroll.setStyleSheet("border: none; background: transparent;")
        self.palette_container = QWidget()
        self.palette_grid = QGridLayout(self.palette_container)
        self.palette_grid.setContentsMargins(0, 4, 0, 4)
        self.palette_grid.setSpacing(6)
        palette_scroll.setWidget(self.palette_container)
        palette_layout.addWidget(palette_scroll)
        content_layout.addWidget(palette_frame)

        # CENTER PANEL: Scrollable Exam Paper
        paper_frame = QFrame()
        paper_frame.setObjectName("ExamPaperFrame")
        paper_frame.setStyleSheet("""
            QFrame#ExamPaperFrame {
                background-color: #121820;
                border: 1px solid #2D3748;
                border-radius: 8px;
            }
        """)
        paper_layout = QVBoxLayout(paper_frame)
        paper_layout.setContentsMargins(6, 6, 6, 6)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #121820;
            }
            QScrollBar:vertical {
                border: none;
                background-color: #1E293B;
                width: 12px;
                border-radius: 6px;
                margin: 2px 2px 2px 2px;
            }
            QScrollBar::handle:vertical {
                background-color: #3B82F6;
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #60A5FA;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        self.questions_container = QWidget()
        self.questions_layout = QVBoxLayout(self.questions_container)
        self.questions_layout.setContentsMargins(10, 10, 10, 10)
        self.questions_layout.setSpacing(14)
        self.scroll_area.setWidget(self.questions_container)
        paper_layout.addWidget(self.scroll_area)
        content_layout.addWidget(paper_frame, 3)

        # RIGHT PANEL: AI Proctor Monitor
        proctor_frame = QFrame()
        proctor_frame.setObjectName("ExamProctorFrame")
        proctor_frame.setFixedWidth(280)
        proctor_frame.setStyleSheet("""
            QFrame#ExamProctorFrame {
                background-color: #1A2332;
                border: 1px solid #2D3748;
                border-radius: 8px;
            }
        """)
        proctor_layout = QVBoxLayout(proctor_frame)
        proctor_layout.setContentsMargins(10, 8, 10, 8)
        proctor_layout.setSpacing(6)

        lbl_proctor_head = QLabel("GIÁM SÁT AI REAL-TIME")
        lbl_proctor_head.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        lbl_proctor_head.setStyleSheet("color: #60A5FA;")
        proctor_layout.addWidget(lbl_proctor_head)

        self.camera_hud = CyberCameraHUD(self, is_compact=True)
        self.camera_hud.setFixedSize(260, 160)
        self.camera_hud.student_id = self.student_id
        proctor_layout.addWidget(self.camera_hud)

        self.lbl_telemetry = QLabel("Góc đầu: Yaw 0.0° | Pitch 0.0°\nKhuôn mặt: 1 | Trạng thái: An toàn")
        self.lbl_telemetry.setFont(QFont("Consolas", 8))
        self.lbl_telemetry.setStyleSheet("color: #E2E8F0; background-color: #0F172A; padding: 5px; border-radius: 4px;")
        proctor_layout.addWidget(self.lbl_telemetry)

        lbl_v_title = QLabel("NHẬT KÝ CẢNH BÁO VI PHẠM:")
        lbl_v_title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        proctor_layout.addWidget(lbl_v_title)

        self.txt_violation_log = QTextEdit()
        self.txt_violation_log.setReadOnly(True)
        self.txt_violation_log.setFont(QFont("Consolas", 8))
        self.txt_violation_log.setStyleSheet("background-color: #0F172A; color: #F87171; border: 1px solid #334155; border-radius: 4px;")
        self.txt_violation_log.setMinimumHeight(60)
        self.txt_violation_log.setMaximumHeight(105)
        proctor_layout.addWidget(self.txt_violation_log)

        proctor_layout.addStretch()
        content_layout.addWidget(proctor_frame)
        main_layout.addLayout(content_layout, 1)

        # 3. STICKY BOTTOM ACTION BAR (ALWAYS VISIBLE - NEVER HIDDEN)
        bottom_bar = QFrame()
        bottom_bar.setObjectName("ExamBottomBar")
        bottom_bar.setFixedHeight(50)
        bottom_bar.setStyleSheet("""
            QFrame#ExamBottomBar {
                background-color: #1A2332;
                border: 1px solid #2D3748;
                border-radius: 8px;
            }
        """)
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(16, 6, 16, 6)

        self.lbl_autosave = QLabel("💾 Tự động lưu: Sẵn sàng")
        self.lbl_autosave.setFont(QFont("Segoe UI", 10))
        self.lbl_autosave.setStyleSheet("color: #94A3B8;")

        self.lbl_progress = QLabel("Đã trả lời: 0/3 câu")
        self.lbl_progress.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.lbl_progress.setStyleSheet("color: #60A5FA;")

        self.btn_submit = QPushButton("📝 NỘP BÀI THI & XÁC NHẬN CHỮ KÝ SỐ RSA")
        self.btn_submit.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.btn_submit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_submit.setStyleSheet("""
            QPushButton {
                background-color: #2563EB; color: white; border-radius: 8px; padding: 9px 24px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
            QPushButton:disabled { background-color: #475569; color: #94A3B8; }
        """)
        self.btn_submit.clicked.connect(self._prompt_submit_confirmation)

        bottom_layout.addWidget(self.lbl_autosave)
        bottom_layout.addSpacing(25)
        bottom_layout.addWidget(self.lbl_progress)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.btn_submit)

        main_layout.addWidget(bottom_bar)

    def _load_exam_paper(self) -> None:
        paper = self.net_client.request_exam_paper()
        if not paper or "questions" not in paper:
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

        cached_drafts = self.storage.load_drafts(self.student_id, self.exam_id)
        self._build_questions_ui(cached_drafts)
        self._build_palette_ui(cached_drafts)
        self._update_progress_label()

        self.is_exam_active = True
        self.countdown_timer.start(1000)

    def _build_questions_ui(self, cached_drafts: dict) -> None:
        # 1. Clear existing question frames to prevent duplication
        while self.questions_layout.count():
            item = self.questions_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.answers_widgets.clear()
        self.review_checkboxes.clear()
        self.question_frames.clear()

        for q in self.questions_data:
            q_id = q["id"]
            box = QFrame()
            box.setObjectName(f"QuestionBox_{q_id}")
            box.setStyleSheet(f"""
                QFrame#QuestionBox_{q_id} {{
                    background-color: #1E293B;
                    border: 1px solid #334155;
                    border-radius: 8px;
                }}
            """)
            box.installEventFilter(self)
            layout = QVBoxLayout(box)
            layout.setContentsMargins(16, 14, 16, 14)
            layout.setSpacing(10)

            q_type = q.get("type", "essay")
            options = q.get("options")
            is_mc = bool(options or q_type == "multiple_choice")
            type_label = "[TRẮC NGHIỆM]" if is_mc else "[TỰ LUẬN]"

            q_title = QLabel(f"<b>Câu {q_id}:</b> <span style='color: #60A5FA; font-weight: bold;'>{type_label}</span> {q['question']}")
            q_title.setWordWrap(True)
            q_title.setFont(QFont("Segoe UI", 11))
            q_title.setStyleSheet("color: #F8FAFC;")
            q_title.installEventFilter(self)
            layout.addWidget(q_title)

            cached_ans = cached_drafts.get(q_id, {}).get("answer_text", "")

            if is_mc:
                # 1. Multiple Choice Question: QRadioButton Group
                btn_group = QButtonGroup(box)
                opt_container = QWidget()
                opt_layout = QVBoxLayout(opt_container)
                opt_layout.setContentsMargins(4, 2, 4, 2)
                opt_layout.setSpacing(6)

                for opt_idx, opt_text in enumerate(options or []):
                    r_btn = QRadioButton(opt_text)
                    r_btn.setFont(QFont("Segoe UI", 10))
                    r_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    r_btn.setStyleSheet("""
                        QRadioButton {
                            color: #E2E8F0;
                            padding: 6px 12px;
                            border-radius: 6px;
                            background-color: #0F172A;
                            border: 1px solid #334155;
                        }
                        QRadioButton:hover {
                            background-color: #1E293B;
                            border-color: #3B82F6;
                        }
                        QRadioButton:checked {
                            background-color: #1E3A8A;
                            color: #60A5FA;
                            border: 1px solid #60A5FA;
                            font-weight: bold;
                        }
                    """)
                    r_btn.installEventFilter(self)
                    btn_group.addButton(r_btn, opt_idx)
                    opt_layout.addWidget(r_btn)

                    # Check if answer draft matches option
                    if cached_ans:
                        opt_prefix = opt_text.split(".")[0].strip() if "." in opt_text else ""
                        if (cached_ans.strip() == opt_text.strip() or 
                            (opt_prefix and cached_ans.strip().upper() == opt_prefix.upper())):
                            r_btn.setChecked(True)

                btn_group.buttonClicked.connect(lambda _, qid=q_id: self._on_answer_changed(qid))
                layout.addWidget(opt_container)
                self.answers_widgets[q_id] = btn_group

            else:
                # 2. Essay Question: QTextEdit
                ans_input = QTextEdit()
                ans_input.setPlaceholderText("Nhập nội dung câu trả lời tự luận của bạn tại đây...")
                ans_input.setFont(QFont("Segoe UI", 10))
                ans_input.setStyleSheet("""
                    QTextEdit {
                        background-color: #0F172A;
                        border: 1px solid #334155;
                        border-radius: 6px;
                        color: white;
                        padding: 8px;
                    }
                    QTextEdit:focus {
                        border-color: #3B82F6;
                    }
                """)
                ans_input.setMinimumHeight(110)
                ans_input.setMaximumHeight(200)
                ans_input.installEventFilter(self)
                ans_input.viewport().installEventFilter(self)

                if cached_ans:
                    ans_input.setPlainText(cached_ans)

                ans_input.textChanged.connect(lambda qid=q_id: self._on_answer_changed(qid))
                layout.addWidget(ans_input)
                self.answers_widgets[q_id] = ans_input

            chk_review = QCheckBox("★ Đánh dấu câu này để xem lại sau")
            chk_review.setFont(QFont("Segoe UI", 9))
            chk_review.setStyleSheet("color: #F59E0B;")
            chk_review.installEventFilter(self)
            if q_id in cached_drafts and cached_drafts[q_id].get("status") == "REVIEW":
                chk_review.setChecked(True)
            chk_review.toggled.connect(lambda checked, qid=q_id: self._on_review_toggled(qid, checked))
            layout.addWidget(chk_review)

            self.review_checkboxes[q_id] = chk_review
            self.question_frames[q_id] = box
            self.questions_layout.addWidget(box)

        # 3. End-of-Exam Action Card (Submit directly at bottom of question list)
        end_card = QFrame()
        end_card.setObjectName("ExamEndActionCard")
        end_card.setStyleSheet("""
            QFrame#ExamEndActionCard {
                background-color: #1A2332;
                border: 2px dashed #3B82F6;
                border-radius: 10px;
                padding: 18px;
            }
        """)
        end_layout = QVBoxLayout(end_card)
        end_layout.setContentsMargins(18, 14, 18, 14)
        end_layout.setSpacing(10)

        lbl_end_title = QLabel("🏁 BẠN ĐÃ ĐI ĐẾN CUỐI ĐỀ THI")
        lbl_end_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl_end_title.setStyleSheet("color: #60A5FA;")
        lbl_end_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        end_layout.addWidget(lbl_end_title)

        lbl_end_desc = QLabel("Hãy rà soát kỹ các câu trả lời trên Bảng câu hỏi trước khi đóng bài nộp.")
        lbl_end_desc.setFont(QFont("Segoe UI", 9))
        lbl_end_desc.setStyleSheet("color: #94A3B8;")
        lbl_end_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        end_layout.addWidget(lbl_end_desc)

        self.btn_bottom_submit = QPushButton("📝 XÁC NHẬN NỘP BÀI THI & KÝ SỐ RSA NGAY TẠI ĐÂY")
        self.btn_bottom_submit.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.btn_bottom_submit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_bottom_submit.setStyleSheet("""
            QPushButton {
                background-color: #2563EB; color: white; border-radius: 8px; padding: 11px 24px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
            QPushButton:disabled { background-color: #475569; color: #94A3B8; }
        """)
        self.btn_bottom_submit.clicked.connect(self._prompt_submit_confirmation)
        end_layout.addWidget(self.btn_bottom_submit)

        self.questions_layout.addWidget(end_card)

        # Generous padding at bottom so last card can be scrolled completely into view
        self.questions_layout.addSpacing(50)
        self.questions_layout.addStretch()
        self.questions_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)

    def eventFilter(self, obj, event: QEvent) -> bool:
        """Passes wheel events to QScrollArea so page scrolls smoothly without getting trapped."""
        if event.type() == QEvent.Type.Wheel:
            delta = event.angleDelta().y()
            if delta != 0:
                vbar = self.scroll_area.verticalScrollBar()
                vbar.setValue(vbar.value() - int(delta * 0.9))
                return True
        return super().eventFilter(obj, event)

    def _build_palette_ui(self, cached_drafts: dict) -> None:
        # Clear existing buttons
        while self.palette_grid.count():
            item = self.palette_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.palette_buttons.clear()

        cols = 2
        for idx, q in enumerate(self.questions_data):
            q_id = q["id"]
            btn = QPushButton(f"Câu {q_id}")
            btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            btn.setFixedSize(76, 32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, qid=q_id: self._scroll_to_question(qid))

            status = "NOT_DONE"
            if q_id in cached_drafts:
                status = cached_drafts[q_id].get("status", "NOT_DONE")
            elif self._get_answer_text(q_id):
                status = "DONE"

            self._set_palette_btn_style(btn, status)
            self.palette_buttons[q_id] = btn
            self.palette_grid.addWidget(btn, idx // cols, idx % cols)

    def _scroll_to_question(self, q_id: int) -> None:
        if q_id in self.question_frames:
            target = self.question_frames[q_id]
            target_pos = target.mapTo(self.questions_container, target.rect().topLeft())
            self.scroll_area.verticalScrollBar().setValue(max(0, target_pos.y() - 10))

    def _get_answer_text(self, q_id: int) -> str:
        """Retrieves normalized answer string from either Multiple Choice or Essay widget."""
        widget = self.answers_widgets.get(q_id)
        if isinstance(widget, QButtonGroup):
            checked = widget.checkedButton()
            if checked:
                txt = checked.text().strip()
                # If option starts with "A.", return "A" (or full text if no prefix)
                if "." in txt and len(txt.split(".")[0]) <= 2:
                    return txt.split(".")[0].strip()
                return txt
            return ""
        elif isinstance(widget, QTextEdit):
            return widget.toPlainText().strip()
        return ""

    def _on_answer_changed(self, q_id: int) -> None:
        text = self._get_answer_text(q_id)
        is_review = self.review_checkboxes[q_id].isChecked()
        status = "REVIEW" if is_review else ("DONE" if text else "NOT_DONE")

        if q_id in self.palette_buttons:
            self._set_palette_btn_style(self.palette_buttons[q_id], status)
        self._update_progress_label()

    def _on_review_toggled(self, q_id: int, checked: bool) -> None:
        text = self._get_answer_text(q_id)
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

    def _update_progress_label(self) -> None:
        total = len(self.questions_data)
        done = sum(1 for qid in self.answers_widgets if self._get_answer_text(qid))
        self.lbl_progress.setText(f"Đã trả lời: {done}/{total} câu")

    def _auto_save_all(self) -> None:
        answers = {qid: self._get_answer_text(qid) for qid in self.answers_widgets}
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
        if self.net_client and self.net_client.is_connected:
            self.lbl_net_widget.setText("🌐 Ping: <50ms [Ổn định]")
            self.lbl_net_widget.setStyleSheet("color: #10B981; background-color: #0F172A; padding: 4px 10px; border-radius: 6px;")
        else:
            self.lbl_net_widget.setText("⚠️ Rớt mạng: Đang kết nối lại...")
            self.lbl_net_widget.setStyleSheet("color: #EF4444; background-color: #0F172A; padding: 4px 10px; border-radius: 6px;")
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
            self.log_violation("⏰ HẾT THỜI GIAN LÀM BÀI! Tự động nộp bài và ký số RSA...")
            self._execute_submit_exam(is_forced=True)

    def update_camera_frame(self, q_image: QImage) -> None:
        """Paints real-time video frame to Cyber Camera HUD."""
        if hasattr(self, "camera_hud"):
            self.camera_hud.update_frame(q_image)

    def update_telemetry(self, yaw: float, pitch: float, roll: float, face_count: int) -> None:
        status_text = "An toàn" if face_count == 1 and abs(yaw) <= 25 and abs(pitch) <= 20 else "Nghi vấn"
        if hasattr(self, "camera_hud"):
            self.camera_hud.update_telemetry(yaw, pitch, roll, face_count, student_id=self.student_id)
        self.lbl_telemetry.setText(
            f"Góc đầu: Yaw {yaw:+.1f}° | Pitch {pitch:+.1f}°\n"
            f"Khuôn mặt: {face_count} | Đánh giá: {status_text}"
        )

    def log_violation(self, text: str) -> None:
        ts = time.strftime("%H:%M:%S")
        self.txt_violation_log.append(f"[{ts}] {text}")

    def _prompt_submit_confirmation(self) -> None:
        total = len(self.questions_data)
        done = 0
        not_done = 0
        review = 0

        for qid in self.answers_widgets:
            txt = self._get_answer_text(qid)
            is_rev = self.review_checkboxes[qid].isChecked()
            if is_rev:
                review += 1
            if txt:
                done += 1
            else:
                not_done += 1

        modal = SubmissionConfirmationDialog(total, done, not_done, review, self)
        if modal.exec() == QDialog.DialogCode.Accepted:
            self._execute_submit_exam(is_forced=False)

    def _execute_submit_exam(self, is_forced: bool = False) -> None:
        if self.is_submitted:
            return
        self.is_submitted = True
        self.countdown_timer.stop()
        self.btn_submit.setEnabled(False)
        if hasattr(self, "btn_bottom_submit"):
            self.btn_bottom_submit.setEnabled(False)

        # 1. Lock all input fields immediately (Anti-Tamper & Timeout Enforcement)
        for widget in self.answers_widgets.values():
            if isinstance(widget, QTextEdit):
                widget.setReadOnly(True)
            elif isinstance(widget, QButtonGroup):
                for btn in widget.buttons():
                    btn.setEnabled(False)

        for chk in self.review_checkboxes.values():
            chk.setEnabled(False)
        for p_btn in self.palette_buttons.values():
            p_btn.setEnabled(False)

        if is_forced:
            self.lbl_autosave.setText("🔒 BÀI THI ĐÃ BỊ KHÓA (CƯỠNG CHẾ NỘP DO HẾT GIỜ)")
            self.lbl_autosave.setStyleSheet("color: #EF4444; font-weight: bold;")
            self.log_violation("⏰ Hết thời gian! Đang tự động ký số RSA 2048-bit và nộp bài...")
        else:
            self.log_violation("Đang ký số RSA 2048-bit và nộp bài lên máy chủ...")

        answers = {qid: self._get_answer_text(qid) for qid in self.answers_widgets}
        self._auto_save_all()

        res = self.net_client.submit_exam_paper(self.exam_id, answers)

        if res.get("success"):
            self.storage.clear_drafts(self.student_id, self.exam_id)
            receipt = res.get("receipt", {})
            server_sig = res.get("server_signature", "")
            student_sig = res.get("student_signature", "")
            self.exam_submitted.emit(receipt, server_sig, student_sig)
        else:
            if not is_forced:
                QMessageBox.critical(self, "Lỗi nộp bài", f"Lỗi từ máy chủ: {res.get('error')}")
                # Unlock if submission failed
                for widget in self.answers_widgets.values():
                    if isinstance(widget, QTextEdit):
                        widget.setReadOnly(False)
                    elif isinstance(widget, QButtonGroup):
                        for btn in widget.buttons():
                            btn.setEnabled(True)
                for chk in self.review_checkboxes.values():
                    chk.setEnabled(True)
                for p_btn in self.palette_buttons.values():
                    p_btn.setEnabled(True)
                self.btn_submit.setEnabled(True)
                if hasattr(self, "btn_bottom_submit"):
                    self.btn_bottom_submit.setEnabled(True)
                self.is_submitted = False
            else:
                self.log_violation(f"❌ Lỗi nộp cưỡng chế: {res.get('error')}")
