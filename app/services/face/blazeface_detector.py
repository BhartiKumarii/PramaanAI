"""Face detection via Google's BlazeFace (short-range) through the
MediaPipe Tasks API. BlazeFace is a lightweight (~230KB) single-shot
face detector optimised for mobile/edge — the same model that powers
MediaPipe's on-device face detection pipeline.

The detector instance is created once (module-level singleton) and
reused across requests.
"""
import io
import threading
from pathlib import Path

import mediapipe as mp
import numpy as np
from PIL import Image, ImageOps

from app.services.face.base import DetectedFace, FaceDetectionResult, FaceDetector

_MODEL_PATH = str(
    Path(__file__).resolve().parent.parent.parent.parent / "models" / "blaze_face_short_range.tflite"
)
_MIN_DETECTION_CONFIDENCE = 0.5
_EDGE_MARGIN = 5

_lock = threading.Lock()
_detector: mp.tasks.vision.FaceDetector | None = None


def _get_detector() -> mp.tasks.vision.FaceDetector:
    global _detector
    if _detector is None:
        with _lock:
            if _detector is None:
                base_options = mp.tasks.BaseOptions(model_asset_path=_MODEL_PATH)
                options = mp.tasks.vision.FaceDetectorOptions(
                    base_options=base_options,
                    min_detection_confidence=_MIN_DETECTION_CONFIDENCE,
                )
                _detector = mp.tasks.vision.FaceDetector.create_from_options(options)
    return _detector


class BlazeFaceDetector(FaceDetector):
    def detect(self, image_bytes: bytes) -> FaceDetectionResult:
        try:
            pil_image = Image.open(io.BytesIO(image_bytes))
            pil_image = ImageOps.exif_transpose(pil_image)
            rgb = pil_image.convert("RGB")
            img_array = np.asarray(rgb)
            height, width = img_array.shape[:2]
        except Exception as exc:
            return FaceDetectionResult(
                status="NO_FACE", faces=[], reason=f"failed to decode image: {exc}"
            )

        try:
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_array)
            result = _get_detector().detect(mp_image)
        except Exception as exc:
            return FaceDetectionResult(
                status="NO_FACE", faces=[], reason=f"BlazeFace inference failed: {exc}"
            )

        faces: list[DetectedFace] = []
        for detection in result.detections:
            bb = detection.bounding_box
            score = detection.categories[0].score if detection.categories else 0.0

            x0 = max(0, bb.origin_x)
            y0 = max(0, bb.origin_y)
            x1 = min(width, bb.origin_x + bb.width)
            y1 = min(height, bb.origin_y + bb.height)

            touches_edge = (
                x0 <= _EDGE_MARGIN
                or y0 <= _EDGE_MARGIN
                or x1 >= width - _EDGE_MARGIN
                or y1 >= height - _EDGE_MARGIN
            )

            faces.append(
                DetectedFace(
                    location={"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0},
                    confidence=round(float(score), 4),
                    touches_edge=touches_edge,
                )
            )

        if not faces:
            return FaceDetectionResult(
                status="NO_FACE", faces=[], reason="no face detected in the image"
            )

        faces.sort(key=lambda f: f.confidence, reverse=True)

        if len(faces) == 1:
            f = faces[0]
            edge_note = " (touches image edge)" if f.touches_edge else ""
            return FaceDetectionResult(
                status="SINGLE_FACE",
                faces=faces,
                reason=f"1 face detected, confidence {f.confidence:.2f}{edge_note}",
            )

        return FaceDetectionResult(
            status="MULTIPLE_FACES",
            faces=faces,
            reason=f"{len(faces)} faces detected (expected exactly one)",
        )
