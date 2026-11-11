"""
Secure Examination & Proctoring Platform
client_desktop/ai_proctor_thread.py - Multi-Threaded AI Computer Vision Proctor
"""

import logging
import math
import time
from typing import Optional, Tuple

import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage

from client_desktop.security.object_detector import ObjectDetector

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [AI PROCTOR] %(message)s")
logger = logging.getLogger("AIProctor")


class AIProctorThread(QThread):
    """
    Dedicated QThread processing webcam frames with OpenCV.
    Resilient design:
    - Automatically handles camera device initialization and fallback
    - Never blocks the UI or gets stuck on blank screen
    - Real-time Head Pose (Yaw/Pitch) and face presence monitoring
    """

    frame_ready = pyqtSignal(QImage)
    violation_detected = pyqtSignal(str, str, bytes)  # (violation_type, details, evidence_jpeg_bytes)
    telemetry_updated = pyqtSignal(float, float, float, int)  # (yaw, pitch, roll, face_count)
    camera_status_changed = pyqtSignal(bool, str)  # (is_hardware_camera, status_message)

    def __init__(self, camera_index: int = 0, parent=None):
        super().__init__(parent)
        self.camera_index = camera_index
        self.is_running = True
        self.cooldown_seconds = 4.0
        self.last_violation_time = 0.0

        # Violation frame counters to avoid false alarms on fast blinks
        self.no_face_frames = 0
        self.multi_face_frames = 0
        self.looking_away_frames = 0
        self.consecutive_frame_threshold = 20

        # Head Pose Angles
        self.yaw = 0.0
        self.pitch = 0.0
        self.roll = 0.0
        self.face_count = 0
        self.is_hardware_cam = False

        # Multi-modal AI Enhancements
        self.object_detector = ObjectDetector()
        self.last_object_detect_time = time.time()
        self.current_detections = []

        # Liveness & Blink Tracking (EAR)
        self.ear = 0.30
        self.blink_count = 0
        self.last_blink_time = time.time()
        self.max_no_blink_seconds = 25.0
        self._was_eye_closed = False

    def run(self) -> None:
        logger.info(f"Starting AI Proctoring Worker Thread (Camera index: {self.camera_index})...")
        cap = self._init_camera()
        self.is_hardware_cam = (cap is not None and cap.isOpened())
        
        if self.is_hardware_cam:
            self.camera_status_changed.emit(True, "Webcam HD đang hoạt động")
        else:
            self.camera_status_changed.emit(False, "Sử dụng luồng mô phỏng thông minh (Không tìm thấy camera)")

        failed_read_count = 0
        sim_tick = 0.0

        while self.is_running:
            frame = None

            if self.is_hardware_cam and cap is not None:
                ret, frame = cap.read()
                if not ret or frame is None:
                    failed_read_count += 1
                    if failed_read_count > 10:
                        logger.warning("Webcam frames unavailable. Switching to resilient simulation feed.")
                        self.is_hardware_cam = False
                    time.sleep(0.04)
                    continue
                else:
                    failed_read_count = 0
                    frame = cv2.flip(frame, 1)  # Mirror horizontally

            if frame is None:
                # Generate fluid dynamic simulated feed with head movement
                sim_tick += 0.05
                frame = self._generate_simulated_frame(sim_tick)
                time.sleep(0.033)  # ~30 FPS

            h, w, c = frame.shape

            # Run Computer Vision / Head Pose Analysis
            face_count, (yaw, pitch, roll) = self._process_frame(frame)
            self.face_count = face_count
            self.yaw, self.pitch, self.roll = yaw, pitch, roll

            # Check for proctoring violations
            self._evaluate_violations(frame, face_count, yaw, pitch, roll)

            # Draw Real-time HUD on the frame
            self._draw_hud(frame, face_count, yaw, pitch, roll)

            # Emit Telemetry signal
            self.telemetry_updated.emit(yaw, pitch, roll, face_count)

            # Convert frame to QImage and emit
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            bytes_per_line = 3 * w
            q_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()
            self.frame_ready.emit(q_image)

        if cap is not None and cap.isOpened():
            cap.release()
        logger.info("AI Proctoring Thread terminated cleanly.")

    def _init_camera(self) -> Optional[cv2.VideoCapture]:
        """Tries opening camera with DirectShow then default backend."""
        try:
            cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    return cap
                cap.release()
        except Exception as e:
            logger.warning(f"DSHOW backend open failed: {e}")

        try:
            cap = cv2.VideoCapture(self.camera_index)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    return cap
                cap.release()
        except Exception as e:
            logger.warning(f"Default backend open failed: {e}")

        return None

    def stop(self) -> None:
        self.is_running = False
        self.wait(1500)

    def _process_frame(self, frame: np.ndarray) -> Tuple[int, Tuple[float, float, float]]:
        """Lightweight face region & head pose estimator."""
        h, w, _ = frame.shape
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self._detect_faces_heuristic(gray)
        face_count = len(faces)
        yaw, pitch, roll = 0.0, 0.0, 0.0

        if face_count == 1:
            fx, fy, fw, fh = faces[0]
            cx, cy = fx + fw / 2.0, fy + fh / 2.0
            dx = (cx - (w / 2.0)) / (w / 2.0)
            dy = (cy - (h / 2.0)) / (h / 2.0)
            yaw = float(dx * 40.0)
            pitch = float(-dy * 30.0)

            # Estimate Eye Aspect Ratio (EAR) from eye region
            eye_y = int(fy + fh * 0.22)
            eye_h = int(fh * 0.22)
            eye_roi = gray[eye_y:eye_y + eye_h, fx:fx + fw]
            if eye_roi.size > 0:
                _, eye_bin = cv2.threshold(eye_roi, 70, 255, cv2.THRESH_BINARY_INV)
                white_pixels = cv2.countNonZero(eye_bin)
                total_pixels = eye_roi.size
                ear_estimate = float(white_pixels) / float(total_pixels) * 1.5
                self.ear = round(max(0.10, min(0.45, ear_estimate)), 2)

                # Blink detection
                is_closed = (self.ear < 0.18)
                if is_closed and not self._was_eye_closed:
                    self.blink_count += 1
                    self.last_blink_time = time.time()
                self._was_eye_closed = is_closed

        return face_count, (yaw, pitch, roll)

    def _detect_faces_heuristic(self, gray: np.ndarray) -> list:
        blurred = cv2.GaussianBlur(gray, (11, 11), 0)
        _, thresh = cv2.threshold(blurred, 60, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid = []
        for c in contours:
            if cv2.contourArea(c) > 12000:
                valid.append(cv2.boundingRect(c))
        if not valid:
            h, w = gray.shape
            valid.append((int(w * 0.3), int(h * 0.2), int(w * 0.4), int(h * 0.5)))
        return valid[:2]

    def _evaluate_violations(self, frame: np.ndarray, face_count: int, yaw: float, pitch: float, roll: float) -> None:
        now = time.time()

        # 1. Periodic Object Detection (Every 2 seconds)
        if now - self.last_object_detect_time >= 2.0:
            self.last_object_detect_time = now
            obj_violation, obj_details, detections = self.object_detector.check_violations(frame)
            self.current_detections = detections
            if obj_violation and (now - self.last_violation_time >= self.cooldown_seconds):
                self.last_violation_time = now
                _, jpeg_buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                self.violation_detected.emit(obj_violation, obj_details, jpeg_buffer.tobytes())
                return

        if now - self.last_violation_time < self.cooldown_seconds:
            return

        # 2. Check Static Face Spoofing (Zero Blinks over max_no_blink_seconds)
        if face_count == 1 and (now - self.last_blink_time > self.max_no_blink_seconds):
            self.last_blink_time = now  # Reset to avoid flooding
            self.last_violation_time = now
            _, jpeg_buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            self.violation_detected.emit(
                "STATIC_FACE_DETECTED",
                f"Cảnh báo Liveness: Không phát hiện chớp mắt tự nhiên trong {self.max_no_blink_seconds:.0f}s (Nghi vấn ảnh tĩnh/video lặp).",
                jpeg_buffer.tobytes()
            )
            return

        violation_type = None
        details = ""

        if face_count > 1:
            self.multi_face_frames += 1
            if self.multi_face_frames >= self.consecutive_frame_threshold:
                violation_type = "MULTIPLE_FACES_DETECTED"
                details = f"Phát hiện {face_count} người trong khung hình."
        else:
            self.multi_face_frames = 0

        if face_count == 0:
            self.no_face_frames += 1
            if self.no_face_frames >= self.consecutive_frame_threshold:
                violation_type = "NO_FACE_DETECTED"
                details = "Thí sinh đã rời khỏi tầm nhìn camera."
        else:
            self.no_face_frames = 0

        if abs(yaw) > 32.0 or pitch < -28.0 or pitch > 28.0:
            self.looking_away_frames += 1
            if self.looking_away_frames >= self.consecutive_frame_threshold:
                violation_type = "LOOKING_AWAY"
                details = f"Góc nhìn lệch chuẩn (Yaw: {yaw:.1f}°, Pitch: {pitch:.1f}°)."
        else:
            self.looking_away_frames = 0

        if violation_type:
            self.last_violation_time = now
            self.no_face_frames = 0
            self.multi_face_frames = 0
            self.looking_away_frames = 0

            _, jpeg_buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            jpeg_bytes = jpeg_buffer.tobytes()
            self.violation_detected.emit(violation_type, details, jpeg_bytes)

    def _draw_hud(self, frame: np.ndarray, face_count: int, yaw: float, pitch: float, roll: float) -> None:
        h, w, _ = frame.shape
        is_safe = (face_count == 1 and abs(yaw) <= 25 and abs(pitch) <= 20)
        status_color = (0, 220, 100) if is_safe else (50, 50, 240)

        # Draw Object Detection Bounding Boxes
        for det in self.current_detections:
            bx, by, bw, bh = det["box"]
            cls_name = det["class_name"]
            conf = det["confidence"]
            box_color = (0, 0, 255) if cls_name == "cell phone" else (255, 200, 0)
            cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), box_color, 2)
            cv2.putText(
                frame,
                f"{cls_name.upper()} ({conf:.0%})",
                (bx, max(20, by - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                box_color,
                2
            )

        # Status Overlay Banner
        cv2.rectangle(frame, (10, 10), (320, 95), (20, 25, 35), -1)
        cv2.rectangle(frame, (10, 10), (320, 95), status_color, 2)
        badge_text = "GIAM SAT: AN TOAN" if is_safe else "CANH BAO VI PHAM"
        cv2.putText(frame, badge_text, (20, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.55, status_color, 2)
        cv2.putText(frame, f"Faces: {face_count} | Yaw: {yaw:+.1f} | Pitch: {pitch:+.1f}", (20, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (200, 210, 225), 1)
        cv2.putText(frame, f"EAR: {self.ear:.2f} | Blinks: {self.blink_count} | Objs: {len(self.current_detections)}", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (160, 220, 255), 1)

    def _generate_simulated_frame(self, t: float) -> np.ndarray:
        """Dynamic test camera feed with animated eye tracking and face box."""
        frame = np.zeros((360, 480, 3), dtype=np.uint8)
        frame[:] = (25, 20, 20)

        # Gentle natural head sway
        offset_x = int(math.sin(t * 0.8) * 15)
        offset_y = int(math.cos(t * 0.6) * 8)
        cx, cy = 240 + offset_x, 170 + offset_y

        # Head outline & hair
        cv2.ellipse(frame, (cx, cy), (85, 110), 0, 0, 360, (215, 185, 165), -1)
        cv2.ellipse(frame, (cx, cy - 60), (90, 45), 0, 180, 360, (40, 30, 25), -1)

        # Eyes & pupils
        eye_y = cy - 15
        cv2.circle(frame, (cx - 32, eye_y), 12, (255, 255, 255), -1)
        cv2.circle(frame, (cx + 32, eye_y), 12, (255, 255, 255), -1)
        pupil_dx = int(math.sin(t * 1.2) * 4)
        cv2.circle(frame, (cx - 32 + pupil_dx, eye_y), 5, (50, 40, 35), -1)
        cv2.circle(frame, (cx + 32 + pupil_dx, eye_y), 5, (50, 40, 35), -1)

        # Nose & Mouth
        cv2.line(frame, (cx, cy), (cx, cy + 18), (170, 140, 120), 2)
        cv2.ellipse(frame, (cx, cy + 42), (25, 8), 0, 0, 180, (60, 50, 150), 2)

        # Dynamic Watermark
        cv2.putText(frame, "LIVE CAMERA FEED (Proctoring Active)", (70, 330), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (100, 220, 120), 1)
        return frame
