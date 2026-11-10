"""
Secure Examination & Proctoring Platform
client_desktop/security/process_watchdog.py - Background Process Anti-Cheat Watchdog
"""

import logging
import os
import sys
import time
from typing import List, Set

import psutil
from PyQt6.QtCore import QThread, pyqtSignal

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [PROCESS WATCHDOG] %(message)s")
logger = logging.getLogger("ProcessWatchdog")

# Blacklist of prohibited processes during exam
PROHIBITED_PROCESSES = {
    "teamviewer.exe": "Phần mềm điều khiển từ xa TeamViewer",
    "anydesk.exe": "Phần mềm điều khiển từ xa AnyDesk",
    "ultraviewer.exe": "Phần mềm điều khiển từ xa UltraViewer",
    "obs64.exe": "Phần mềm quay màn hình / Virtual Camera OBS",
    "obs32.exe": "Phần mềm quay màn hình / Virtual Camera OBS",
    "discord.exe": "Ứng dụng liên lạc / voice chat Discord",
    "chrome.exe": "Trình duyệt web Google Chrome",
    "msedge.exe": "Trình duyệt web Microsoft Edge",
    "firefox.exe": "Trình duyệt web Mozilla Firefox",
    "zoom.exe": "Ứng dụng họp trực tuyến Zoom",
    "skype.exe": "Ứng dụng liên lạc Skype",
    "vncserver.exe": "VNC Server",
    "radmin.exe": "Radmin Remote Administrator"
}


class ProcessWatchdogThread(QThread):
    """
    Scans active running OS processes every 3 seconds to catch prohibited apps.
    """

    prohibited_process_detected = pyqtSignal(str, int, str)  # (proc_name, pid, description)
    scan_completed = pyqtSignal(int)  # total_scanned_count

    def __init__(self, check_interval_seconds: float = 3.0, parent=None):
        super().__init__(parent)
        self.check_interval = check_interval_seconds
        self.is_running = True
        self.detected_pids: Set[int] = set()

    def run(self) -> None:
        logger.info("Process Anti-Cheat Watchdog started.")
        while self.is_running:
            scanned_count = 0
            for proc in psutil.process_iter(["pid", "name"]):
                if not self.is_running:
                    break
                try:
                    p_name = proc.info.get("name", "").lower()
                    pid = proc.info.get("pid", 0)
                    scanned_count += 1

                    if p_name in PROHIBITED_PROCESSES:
                        if pid not in self.detected_pids:
                            self.detected_pids.add(pid)
                            desc = PROHIBITED_PROCESSES[p_name]
                            logger.warning(f"🚨 Prohibited process detected: {p_name} (PID: {pid}) - {desc}")
                            self.prohibited_process_detected.emit(p_name, pid, desc)

                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue

            self.scan_completed.emit(scanned_count)

            # Sleep in small slices to respond quickly to thread stop request
            slept = 0.0
            while slept < self.check_interval and self.is_running:
                time.sleep(0.2)
                slept += 0.2

        logger.info("Process Anti-Cheat Watchdog stopped.")

    def stop(self) -> None:
        self.is_running = False
        self.wait(1500)
