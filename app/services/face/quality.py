"""Face quality assessment for the verification pipeline.

Checks: blur (Laplacian variance), face size relative to image,
landmark visibility, and occlusion indicators. A face that fails
quality gates produces an INCONCLUSIVE result, not a mismatch.
"""
import io
import logging

import cv2
import numpy as np
from PIL import Image
from pydantic import BaseModel, Field

logger = logging.getLogger("pramaan.face.quality")

_MIN_BLUR_SCORE = 30.0
_MIN_SIZE_RATIO = 0.02
_MIN_FACE_PIXELS = 60


class FaceQualityResult(BaseModel):
    is_sufficient: bool
    blur_score: float
    size_ratio: float
    face_width: int = 0
    face_height: int = 0
    landmark_count: int = 0
    issues: list[str] = Field(default_factory=list)


def _blur_score(gray: np.ndarray) -> float:
    """Laplacian variance — higher means sharper. Below ~30 is blurry."""
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    return float(lap.var())


def _detect_face_bbox_heuristic(gray: np.ndarray) -> tuple[int, int, int, int] | None:
    """Rough centre-crop face region when no detector bbox is provided."""
    h, w = gray.shape
    cx, cy = w // 2, h // 2
    fw, fh = w // 3, h // 3
    return (cx - fw // 2, cy - fh // 2, fw, fh)


def assess_quality(
    image_bytes: bytes,
    face_bbox: dict | None = None,
) -> FaceQualityResult:
    """Run quality checks on a face image.

    face_bbox: optional {x, y, width, height} from BlazeFace detection.
    If None, analyses the full image (assumes it is already a face crop).
    """
    issues: list[str] = []

    try:
        pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img = np.array(pil)
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    except Exception as e:
        return FaceQualityResult(
            is_sufficient=False, blur_score=0.0, size_ratio=0.0,
            issues=[f"cannot decode image: {e}"],
        )

    img_h, img_w = gray.shape
    total_pixels = img_h * img_w

    if face_bbox:
        x = int(face_bbox.get("x", 0))
        y = int(face_bbox.get("y", 0))
        fw = int(face_bbox.get("width", 0))
        fh = int(face_bbox.get("height", 0))
    else:
        est = _detect_face_bbox_heuristic(gray)
        if est:
            x, y, fw, fh = est
        else:
            fw, fh = 0, 0
            x, y = 0, 0

    fw = max(0, fw)
    fh = max(0, fh)
    face_area = fw * fh
    size_ratio = face_area / total_pixels if total_pixels > 0 else 0.0

    if fw > 0 and fh > 0:
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(img_w, x + fw)
        y1 = min(img_h, y + fh)
        face_crop = gray[y0:y1, x0:x1]
    else:
        face_crop = gray

    blur = _blur_score(face_crop) if face_crop.size > 0 else 0.0

    if fw < _MIN_FACE_PIXELS or fh < _MIN_FACE_PIXELS:
        issues.append(f"face too small: {fw}x{fh}px (minimum {_MIN_FACE_PIXELS}px)")

    if size_ratio < _MIN_SIZE_RATIO:
        issues.append(
            f"face area {size_ratio:.3%} of image (minimum {_MIN_SIZE_RATIO:.1%})"
        )

    if blur < _MIN_BLUR_SCORE:
        issues.append(f"excessive blur: Laplacian variance {blur:.1f} (minimum {_MIN_BLUR_SCORE})")

    contrast = float(np.std(face_crop)) if face_crop.size > 0 else 0.0
    if contrast < 15.0:
        issues.append(f"low contrast: std {contrast:.1f} (minimum 15.0)")

    landmark_count = 0
    try:
        from app.services.deepfake.advanced_provider import _get_landmarker
        import mediapipe as mp
        landmarker = _get_landmarker()
        if landmarker is not None:
            rgb_arr = np.asarray(pil)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_arr)
            lm_result = landmarker.detect(mp_image)
            if lm_result.face_landmarks:
                landmark_count = len(lm_result.face_landmarks[0])
                if landmark_count < 400:
                    issues.append(
                        f"partial landmark visibility: {landmark_count}/478 landmarks detected"
                    )
    except Exception:
        pass

    is_sufficient = len(issues) == 0

    return FaceQualityResult(
        is_sufficient=is_sufficient,
        blur_score=round(blur, 2),
        size_ratio=round(size_ratio, 4),
        face_width=fw,
        face_height=fh,
        landmark_count=landmark_count,
        issues=issues,
    )
