"""
Secure Examination & Proctoring Platform
client_desktop/security/clipboard_hook.py - System Clipboard Protection & Sanitizer
"""

import logging
from PyQt6.QtCore import QObject, QTimer
from PyQt6.QtWidgets import QApplication

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [CLIPBOARD HOOK] %(message)s")
logger = logging.getLogger("ClipboardHook")


class ClipboardSanitizer(QObject):
    """
    Periodically clears system clipboard to prevent copying exam questions
    or pasting unauthorized solutions into the application.
    """

    def __init__(self, sanitize_interval_ms: int = 2000, parent=None):
        super().__init__(parent)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._sanitize_clipboard)
        self.interval_ms = sanitize_interval_ms
        self.is_active = False

    def start(self) -> None:
        """Starts the automatic clipboard wipe cycle."""
        self.is_active = True
        self.timer.start(self.interval_ms)
        self._sanitize_clipboard()
        logger.info(f"Clipboard Sanitizer activated (interval: {self.interval_ms}ms).")

    def stop(self) -> None:
        """Stops the clipboard sanitizer."""
        self.is_active = False
        self.timer.stop()
        logger.info("Clipboard Sanitizer deactivated.")

    def _sanitize_clipboard(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard and not clipboard.text().strip() == "":
            clipboard.clear()
            # Injects protective dummy text
            clipboard.setText("[BẢO VỆ BỞI EXAM SYSTEM - CLIPBOARD ĐÃ BỊ KHÓA]")
