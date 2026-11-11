"""
Secure Examination & Proctoring Platform
client_desktop/security/object_detector.py - Prohibited Object & Secondary Person Detector
Runs periodic inference (every 2s) via ONNX Runtime / Vision Heuristics to detect:
1. 'cell phone' (Điện thoại di động)
2. 'person' (Nhiều người trong phòng thi)
"""

import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger("OBJECT_DETECTOR")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [OBJECT_DETECTOR] %(message)s")


class ObjectDetector:
    """
    Lightweight object detection engine running on CPU every 2 seconds.
    Uses ONNX Runtime (e.g. YOLOv8n.onnx) when available, with graceful
    fallback to OpenCV HOG People Detector + Aspect-Ratio Phone Detector.
    """

    # COCO Class index for YOLOv8 (Class 0: person, Class 67: cell phone)
    COCO_CLASSES = {0: "person", 67: "cell phone"}

    def __init__(self, model_path: str = "models/yolov8n.onnx", conf_threshold: float = 0.40):
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.session = None
        self.is_onnx = False

        # Fallback HOG People Detector
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

        self._init_model()

    def _init_model(self) -> None:
        """Attempts to load ONNX model via onnxruntime."""
        if os.path.exists(self.model_path):
            try:
                import onnxruntime as ort
                opts = ort.SessionOptions()
                opts.intra_op_num_threads = 2
                opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                self.session = ort.InferenceSession(self.model_path, opts, providers=["CPUExecutionProvider"])
                self.is_onnx = True
                logger.info(f"✅ ONNX Runtime Object Detector loaded: {self.model_path}")
                return
            except Exception as e:
                logger.warning(f"Failed to load ONNX model {self.model_path}: {e}")

        logger.info("ℹ️ Using Built-in OpenCV HOG + Geometric Vision Fallback Detector.")

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Runs object detection on frame, returning list of detected objects:
        [{"class_name": "cell phone" | "person", "confidence": float, "box": (x, y, w, h)}]
        """
        if self.is_onnx and self.session is not None:
            return self._detect_onnx(frame)
        return self._detect_fallback(frame)

    def _detect_onnx(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """YOLOv8 ONNX inference implementation."""
        h, w, _ = frame.shape
        input_size = 640

        # Letterbox / resize
        blob = cv2.resize(frame, (input_size, input_size))
        blob = blob.astype(np.float32) / 255.0
        blob = np.transpose(blob, (2, 0, 1))
        blob = np.expand_dims(blob, axis=0)

        input_name = self.session.get_inputs()[0].name
        outputs = self.session.run(None, {input_name: blob})

        # YOLOv8 output shape is typically (1, 84, 8400)
        output = outputs[0][0]  # (84, 8400)
        output = np.transpose(output, (1, 0))  # (8400, 84)

        detections = []
        for row in output:
            classes_scores = row[4:]
            class_id = int(np.argmax(classes_scores))
            score = float(classes_scores[class_id])

            if score >= self.conf_threshold and class_id in self.COCO_CLASSES:
                cx, cy, bw, bh = row[0:4]
                x = int((cx - bw / 2.0) * (w / input_size))
                y = int((cy - bh / 2.0) * (h / input_size))
                box_w = int(bw * (w / input_size))
                box_h = int(bh * (h / input_size))

                detections.append({
                    "class_name": self.COCO_CLASSES[class_id],
                    "confidence": score,
                    "box": (max(0, x), max(0, y), box_w, box_h)
                })

        return detections

    def _detect_fallback(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """OpenCV HOG People Detector + Smartphone aspect-ratio contour detector."""
        detections = []
        h, w, _ = frame.shape

        # 1. Detect people via HOG
        small = cv2.resize(frame, (320, 240))
        boxes, weights = self.hog.detectMultiScale(small, winStride=(8, 8), padding=(4, 4), scale=1.05)
        for (bx, by, bw, bh), weight in zip(boxes, weights):
            if weight > 0.35:
                scale_x = w / 320.0
                scale_y = h / 240.0
                detections.append({
                    "class_name": "person",
                    "confidence": float(min(1.0, weight)),
                    "box": (int(bx * scale_x), int(by * scale_y), int(bw * scale_x), int(bh * scale_y))
                })

        # 2. Detect cell phone heuristics (vertical handheld black/shiny rectangular objects)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            area = cv2.contourArea(cnt)
            # Typical phone area in webcam frame: ~1500 to ~15000 pixels
            if 1500 < area < 15000:
                bx, by, bw, bh = cv2.boundingRect(cnt)
                aspect = float(bh) / max(1, bw)
                # Cell phones typically have aspect ratio between 1.8 and 2.4 (held vertically)
                if 1.7 <= aspect <= 2.5:
                    # Check corner rectangularity
                    approx = cv2.approxPolyDP(cnt, 0.04 * cv2.arcLength(cnt, True), True)
                    if len(approx) in (4, 5):
                        detections.append({
                            "class_name": "cell phone",
                            "confidence": 0.65,
                            "box": (bx, by, bw, bh)
                        })
                        break  # Limit to 1 detected phone to avoid duplicates

        return detections

    def check_violations(self, frame: np.ndarray) -> Tuple[Optional[str], str, List[Dict[str, Any]]]:
        """
        Evaluates frame for prohibited objects.
        Returns:
            Tuple[violation_type, details, detections_list]
        """
        detections = self.detect(frame)
        phone_count = sum(1 for d in detections if d["class_name"] == "cell phone")
        person_count = sum(1 for d in detections if d["class_name"] == "person")

        if phone_count > 0:
            return (
                "PROHIBITED_DEVICE_PHONE",
                "Phát hiện thiết bị di động (Smartphone/Điện thoại) trong tầm quan sát.",
                detections
            )

        if person_count > 1:
            return (
                "MULTIPLE_PERSONS_IN_ROOM",
                f"Phát hiện {person_count} người trong khu vực thi cử.",
                detections
            )

        return None, "", detections
