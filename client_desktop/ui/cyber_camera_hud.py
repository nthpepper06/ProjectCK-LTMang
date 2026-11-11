"""
Secure Examination & Proctoring Platform
client_desktop/ui/cyber_camera_hud.py - Cyber Optical Camera HUD Widget
Custom PyQt6 QWidget rendering high-tech biometric proctoring overlays:
- 4-corner L-shaped cyber reticles around detected candidate face
- Dynamic animated laser sweep for Face ID alignment & scanning
- 3D Gaze Ray vector indicating candidate line-of-sight and head pose
- Glassmorphism semi-transparent HUD telemetry badges (FPS, Ping, EAR, Pose)
"""

import math
import time
from typing import Optional, Tuple

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)
from PyQt6.QtWidgets import QWidget


class CyberCameraHUD(QWidget):
    """
    Futuristic Cyber Proctoring Camera HUD Widget.
    Renders real-time camera frames with custom QPainter overlays:
    - Reticle brackets around face
    - Scanning laser beam
    - 3D Head pose / Gaze vector projection
    - Glassmorphism HUD status badges
    """

    def __init__(self, parent=None, is_compact: bool = False):
        super().__init__(parent)
        self.is_compact = is_compact

        # State & Telemetry
        self.current_frame: Optional[QImage] = None
        self.yaw: float = 0.0
        self.pitch: float = 0.0
        self.roll: float = 0.0
        self.face_count: int = 1
        self.ear: float = 0.32
        self.blink_count: int = 0
        self.fps: float = 30.0
        self.ping_ms: float = 24.0
        self.student_id: str = "SV2026_01"
        self.status_verdict: str = "AN TOÀN"
        self.is_scanning: bool = False

        # Laser sweep animation
        self.laser_y_ratio: float = 0.2
        self.laser_direction: float = 0.02
        self.pulse_phase: float = 0.0

        # Animation timer (30 FPS repaint for smooth laser and reticle animation)
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._on_anim_tick)
        self.anim_timer.start(33)

        self.setStyleSheet("background-color: #0B0F19; border-radius: 10px;")

    def update_frame(self, q_image: QImage) -> None:
        """Receives new camera frame from worker thread and queues repaint."""
        self.current_frame = q_image
        self.update()

    def update_telemetry(
        self,
        yaw: float,
        pitch: float,
        roll: float,
        face_count: int,
        ear: float = 0.32,
        blink_count: int = 0,
        student_id: str = ""
    ) -> None:
        """Updates biometric telemetry values and triggers HUD refresh."""
        self.yaw = yaw
        self.pitch = pitch
        self.roll = roll
        self.face_count = face_count
        self.ear = ear
        self.blink_count = blink_count
        if student_id:
            self.student_id = student_id

        # Determine verdict
        if face_count == 0:
            self.status_verdict = "VẮNG MẶT"
        elif face_count > 1:
            self.status_verdict = "NHIỀU NGƯỜI"
        elif abs(yaw) > 25 or abs(pitch) > 20:
            self.status_verdict = "QUAY ĐẦU"
        else:
            self.status_verdict = "AN TOÀN"

        self.update()

    def set_scanning(self, is_scanning: bool) -> None:
        """Enables/disables futuristic laser scan animation."""
        self.is_scanning = is_scanning
        self.update()

    def _on_anim_tick(self) -> None:
        """Animates sweeping laser and pulse phase."""
        self.pulse_phase = (self.pulse_phase + 0.1) % (2 * math.pi)

        if self.is_scanning:
            self.laser_y_ratio += self.laser_direction
            if self.laser_y_ratio >= 0.85:
                self.laser_y_ratio = 0.85
                self.laser_direction = -0.025
            elif self.laser_y_ratio <= 0.15:
                self.laser_y_ratio = 0.15
                self.laser_direction = 0.025
            self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        w = self.width()
        h = self.height()

        # 1. DRAW BACKGROUND & BASE CAMERA FRAME
        if self.current_frame and not self.current_frame.isNull():
            scaled = self.current_frame.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            # Center crop
            sx = (scaled.width() - w) // 2
            sy = (scaled.height() - h) // 2
            painter.drawImage(0, 0, scaled, sx, sy, w, h)
        else:
            # Fallback Cyber Grid
            self._draw_cyber_grid(painter, w, h)

        # 2. DRAW VIGNETTE & SUBTLE SCANLINES
        self._draw_cyber_scanlines(painter, w, h)

        # 3. DRAW 4-CORNER RETICLE BRACKETS AROUND FACE
        reticle_color = self._get_status_color()
        box_w = min(w * 0.58, h * 0.72)
        box_h = box_w * 1.25
        cx = w / 2.0
        cy = h / 2.0 - (h * 0.04)

        face_rect = QRectF(cx - box_w / 2.0, cy - box_h / 2.0, box_w, box_h)
        self._draw_reticle_corners(painter, face_rect, reticle_color)

        # 4. DRAW 3D GAZE RAY (HEAD POSE VECTOR)
        self._draw_3d_gaze_ray(painter, cx, cy, reticle_color)

        # 5. DRAW LASER SCAN SWEEP (WHEN SCANNING)
        if self.is_scanning:
            self._draw_laser_scan(painter, face_rect)

        # 6. DRAW GLASSMORPHISM HUD TELEMETRY BADGES
        self._draw_hud_badges(painter, w, h, reticle_color)

    def _get_status_color(self) -> QColor:
        """Determines primary HUD accent color based on proctoring status."""
        if self.status_verdict == "AN TOÀN":
            return QColor(16, 185, 129)  # Emerald #10B981
        elif self.status_verdict in ("QUAY ĐẦU", "VẮNG MẶT"):
            return QColor(245, 158, 11)  # Amber #F59E0B
        else:
            return QColor(239, 68, 68)   # Red #EF4444

    def _draw_cyber_grid(self, painter: QPainter, w: int, h: int) -> None:
        """Draws high-tech dark grid background when camera frame is pending."""
        painter.fillRect(0, 0, w, h, QColor(11, 15, 25))

        pen = QPen(QColor(30, 41, 59, 120), 1, Qt.PenStyle.DotLine)
        painter.setPen(pen)
        step = 30
        for x in range(0, w, step):
            painter.drawLine(x, 0, x, h)
        for y in range(0, h, step):
            painter.drawLine(0, y, w, y)

        painter.setPen(QColor(96, 165, 250))
        painter.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        painter.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "📷 CONNECTING CYBER OPTICAL SENSOR...")

    def _draw_cyber_scanlines(self, painter: QPainter, w: int, h: int) -> None:
        """Draws subtle glass vignette and dark edges."""
        vignette = QLinearGradient(0, 0, 0, h)
        vignette.setColorAt(0.0, QColor(11, 15, 25, 140))
        vignette.setColorAt(0.2, QColor(0, 0, 0, 0))
        vignette.setColorAt(0.8, QColor(0, 0, 0, 0))
        vignette.setColorAt(1.0, QColor(11, 15, 25, 180))
        painter.fillRect(0, 0, w, h, vignette)

    def _draw_reticle_corners(self, painter: QPainter, rect: QRectF, color: QColor) -> None:
        """Draws 4 L-shaped cyber bracket corners framing the detected face."""
        pen = QPen(color, 2.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        corner_len = min(rect.width() * 0.18, 24.0)

        x1 = rect.left()
        y1 = rect.top()
        x2 = rect.right()
        y2 = rect.bottom()

        # Top-Left
        painter.drawLine(QPointF(x1, y1 + corner_len), QPointF(x1, y1))
        painter.drawLine(QPointF(x1, y1), QPointF(x1 + corner_len, y1))

        # Top-Right
        painter.drawLine(QPointF(x2 - corner_len, y1), QPointF(x2, y1))
        painter.drawLine(QPointF(x2, y1), QPointF(x2, y1 + corner_len))

        # Bottom-Left
        painter.drawLine(QPointF(x1, y2 - corner_len), QPointF(x1, y2))
        painter.drawLine(QPointF(x1, y2), QPointF(x1 + corner_len, y2))

        # Bottom-Right
        painter.drawLine(QPointF(x2 - corner_len, y2), QPointF(x2, y2))
        painter.drawLine(QPointF(x2, y2), QPointF(x2, y2 - corner_len))

        # Center subtle crosshair tick marks
        center_x = rect.center().x()
        center_y = rect.center().y()
        tick = 6.0
        pen_tick = QPen(QColor(color.red(), color.green(), color.blue(), 130), 1)
        painter.setPen(pen_tick)
        painter.drawLine(QPointF(center_x - tick, center_y), QPointF(center_x + tick, center_y))
        painter.drawLine(QPointF(center_x, center_y - tick), QPointF(center_x, center_y + tick))

    def _draw_3d_gaze_ray(self, painter: QPainter, cx: float, cy: float, color: QColor) -> None:
        """Draws 3D Gaze Ray vector showing line-of-sight based on Yaw and Pitch."""
        # Convert degrees to radians
        rad_yaw = math.radians(self.yaw)
        rad_pitch = math.radians(self.pitch)

        # Projected ray vector (invert X because of mirror feed)
        ray_len = 45.0 if not self.is_compact else 32.0
        dx = -math.sin(rad_yaw) * ray_len
        dy = math.sin(rad_pitch) * ray_len

        target_x = cx + dx
        target_y = cy + dy

        # Ray line
        pen_ray = QPen(color, 2, Qt.PenStyle.SolidLine)
        pen_ray.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_ray)
        painter.drawLine(QPointF(cx, cy), QPointF(target_x, target_y))

        # Arrowhead / Target ring
        painter.setBrush(QBrush(color))
        painter.drawEllipse(QPointF(target_x, target_y), 3.5, 3.5)

    def _draw_laser_scan(self, painter: QPainter, rect: QRectF) -> None:
        """Draws high-tech glowing laser scan line sweeping vertically."""
        scan_y = rect.top() + rect.height() * self.laser_y_ratio

        # Cyan/Blue Laser beam with glow gradient
        laser_grad = QLinearGradient(0, scan_y - 12, 0, scan_y + 12)
        laser_grad.setColorAt(0.0, QColor(56, 189, 248, 0))
        laser_grad.setColorAt(0.4, QColor(56, 189, 248, 90))
        laser_grad.setColorAt(0.5, QColor(14, 165, 233, 230))
        laser_grad.setColorAt(0.6, QColor(56, 189, 248, 90))
        laser_grad.setColorAt(1.0, QColor(56, 189, 248, 0))

        painter.fillRect(QRectF(rect.left() - 10, scan_y - 12, rect.width() + 20, 24), laser_grad)

        # Core sharp white-cyan beam
        pen_core = QPen(QColor(224, 242, 254, 250), 1.8)
        painter.setPen(pen_core)
        painter.drawLine(QPointF(rect.left() - 8, scan_y), QPointF(rect.right() + 8, scan_y))

    def _draw_hud_badges(self, painter: QPainter, w: int, h: int, status_color: QColor) -> None:
        """Draws glassmorphism HUD status badges on the 4 corners of the video feed."""
        painter.setFont(QFont("Segoe UI", 8 if self.is_compact else 9, QFont.Weight.Bold))

        # 1. Top-Left: LIVE AI PROCTOR & FPS BADGE
        pulse_alpha = int(170 + 70 * math.sin(self.pulse_phase))
        top_left_rect = QRectF(10, 10, 140 if not self.is_compact else 115, 24)
        self._draw_glass_pill(painter, top_left_rect)

        # Pulsing dot
        painter.setBrush(QBrush(QColor(16, 185, 129, pulse_alpha)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(22, 22), 4, 4)

        painter.setPen(QColor(241, 245, 249))
        label_proctor = "AI PROCTOR" if self.is_compact else "LIVE AI PROCTOR"
        painter.drawText(QRectF(30, 10, 110, 24), Qt.AlignmentFlag.AlignVCenter, f"{label_proctor}")

        # 2. Top-Right: HEAD POSE YAW / PITCH
        top_right_rect = QRectF(w - 150, 10, 140, 24)
        self._draw_glass_pill(painter, top_right_rect)
        painter.setPen(QColor(148, 163, 184))
        painter.drawText(
            top_right_rect,
            Qt.AlignmentFlag.AlignCenter,
            f"Y: {self.yaw:+.0f}° | P: {self.pitch:+.0f}°"
        )

        # 3. Bottom-Left: EAR LIVENESS BADGE
        bot_left_rect = QRectF(10, h - 34, 130 if not self.is_compact else 105, 24)
        self._draw_glass_pill(painter, bot_left_rect)
        painter.setPen(QColor(56, 189, 248))
        painter.drawText(
            bot_left_rect,
            Qt.AlignmentFlag.AlignCenter,
            f"👁 EAR: {self.ear:.2f}"
        )

        # 4. Bottom-Right: STATUS VERDICT
        bot_right_rect = QRectF(w - 140, h - 34, 130, 24)
        self._draw_glass_pill(painter, bot_right_rect)
        painter.setPen(status_color)
        painter.drawText(
            bot_right_rect,
            Qt.AlignmentFlag.AlignCenter,
            f"● {self.status_verdict}"
        )

    def _draw_glass_pill(self, painter: QPainter, rect: QRectF) -> None:
        """Renders dark glassmorphic rounded capsule."""
        painter.setBrush(QBrush(QColor(15, 23, 42, 190)))
        painter.setPen(QPen(QColor(51, 65, 85, 160), 1))
        painter.drawRoundedRect(rect, 6, 6)
