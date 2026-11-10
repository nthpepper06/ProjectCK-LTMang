"""
Secure Examination & Proctoring Platform
client_desktop/security/monitor_blocker.py - Multi-Monitor Detection & Secondary Screen Blocker
"""

import logging
from typing import List, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QGuiApplication
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [MONITOR BLOCKER] %(message)s")
logger = logging.getLogger("MonitorBlocker")


class SecondaryScreenBlackoutWindow(QWidget):
    """Full-screen blackout curtain covering secondary displays."""

    def __init__(self, screen):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setStyleSheet("background-color: #05070A; color: #EF4444;")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_warning = QLabel("⛔ MÀN HÌNH PHỤ BỊ KHÓA BỞI HỆ THỐNG KHẢO THÍ\nVui lòng chỉ tập trung làm bài trên màn hình chính.")
        lbl_warning.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        lbl_warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_warning)

        # Assign to specific secondary screen geometry
        self.setGeometry(screen.geometry())


class MultiMonitorBlocker:
    """
    Detects additional monitors / HDMI projectors and enforces single-screen policy.
    """

    def __init__(self):
        self.blackout_windows: List[SecondaryScreenBlackoutWindow] = []

    @staticmethod
    def get_screen_count() -> int:
        """Returns the number of active display screens."""
        app = QGuiApplication.instance()
        if not app:
            return 1
        return len(QGuiApplication.screens())

    @staticmethod
    def check_screens_allowed() -> Tuple[bool, int, str]:
        """
        Validates if system adheres to strict single-monitor rule.
        Returns: (is_allowed, screen_count, details)
        """
        screens = QGuiApplication.screens() if QGuiApplication.instance() else []
        count = len(screens)
        if count <= 1:
            return True, count, "Hệ thống sử dụng đúng 1 màn hình duy nhất."
        
        details = f"Phát hiện {count} màn hình kết nối! Quy chế thi nghiêm cấm sử dụng màn hình phụ/HDMI."
        logger.warning(f"🚨 {details}")
        return False, count, details

    def blackout_secondary_screens(self) -> None:
        """Covers all non-primary screens with an impassable blackout overlay."""
        self.remove_blackouts()
        screens = QGuiApplication.screens() if QGuiApplication.instance() else []
        if len(screens) <= 1:
            return

        primary_screen = QGuiApplication.primaryScreen()
        for s in screens:
            if s != primary_screen:
                win = SecondaryScreenBlackoutWindow(s)
                win.showFullScreen()
                self.blackout_windows.append(win)
        logger.info(f"Deployed blackout overlays to {len(self.blackout_windows)} secondary screens.")

    def remove_blackouts(self) -> None:
        """Cleans up blackout windows."""
        for w in self.blackout_windows:
            w.close()
        self.blackout_windows.clear()
