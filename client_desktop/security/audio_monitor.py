"""
Secure Examination & Proctoring Platform
client_desktop/security/audio_monitor.py - Acoustic Environmental Monitoring
Listens for continuous conversation/noise exceeding conversational RMS thresholds (> 3s).
"""

import logging
import time
from typing import Callable, Optional

import numpy as np
from PyQt6.QtCore import QObject, QThread, pyqtSignal

logger = logging.getLogger("AUDIO_MONITOR")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [AUDIO_MONITOR] %(message)s")


class AudioMonitorThread(QThread):
    """
    Background QThread continuously measuring room ambient noise and conversation.
    Signals violation when sound energy (RMS) stays above conversational threshold for >= 3 seconds.
    """

    audio_alert = pyqtSignal(str, float, float)  # (violation_type, rms, duration_seconds)
    audio_level_updated = pyqtSignal(float)       # current rms (0.0 to 1.0)

    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_duration_sec: float = 0.1,  # 100ms
        rms_threshold: float = 0.045,      # Conversational speech threshold
        trigger_duration_sec: float = 3.0, # Sustained speech duration
        cooldown_sec: float = 10.0,
        parent: Optional[QObject] = None
    ):
        super().__init__(parent)
        self.sample_rate = sample_rate
        self.chunk_size = int(sample_rate * chunk_duration_sec)
        self.rms_threshold = rms_threshold
        self.trigger_duration_sec = trigger_duration_sec
        self.cooldown_sec = cooldown_sec

        self.is_running = False
        self._sustained_high_sec = 0.0
        self._last_alert_time = 0.0

    def run(self) -> None:
        """Main audio capture and RMS analysis loop using sounddevice."""
        try:
            import sounddevice as sd
        except ImportError:
            logger.warning("sounddevice not available. Audio monitoring disabled.")
            return

        self.is_running = True
        logger.info(f"🎤 Audio Environmental Monitoring started (Threshold: {self.rms_threshold}, Trigger: {self.trigger_duration_sec}s)")

        def audio_callback(indata, frames, time_info, status):
            if not self.is_running:
                return

            if status:
                logger.debug(f"Audio stream status: {status}")

            # Compute RMS of current chunk
            chunk = indata[:, 0] if indata.ndim > 1 else indata
            rms = float(np.sqrt(np.mean(chunk**2))) if len(chunk) > 0 else 0.0
            self.audio_level_updated.emit(rms)

            now = time.time()
            if rms >= self.rms_threshold:
                self._sustained_high_sec += (frames / self.sample_rate)
                if self._sustained_high_sec >= self.trigger_duration_sec:
                    if (now - self._last_alert_time) >= self.cooldown_sec:
                        self._last_alert_time = now
                        logger.warning(
                            f"🚨 [AUDIO VIOLATION] Conversational noise detected! Sustained={self._sustained_high_sec:.1f}s, RMS={rms:.4f}"
                        )
                        self.audio_alert.emit(
                            "CONVERSATION_DETECTED",
                            rms,
                            self._sustained_high_sec
                        )
                    # Reset sustained counter to avoid alert flooding
                    self._sustained_high_sec = 0.0
            else:
                # Decay sustained time during silence
                self._sustained_high_sec = max(0.0, self._sustained_high_sec - (frames / self.sample_rate) * 1.5)

        try:
            with sd.InputStream(
                channels=1,
                samplerate=self.sample_rate,
                blocksize=self.chunk_size,
                callback=audio_callback,
                dtype="float32"
            ):
                while self.is_running:
                    self.msleep(100)
        except Exception as e:
            logger.warning(f"Audio monitoring input stream error: {e}")
        finally:
            logger.info("Audio Environmental Monitoring stopped.")

    def stop(self) -> None:
        self.is_running = False
        self.wait(1000)
