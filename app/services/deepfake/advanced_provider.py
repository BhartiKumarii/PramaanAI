"""BlazeFace-based deepfake detection.

Uses MediaPipe FaceLandmarker (which runs BlazeFace internally) to extract
478 face mesh landmarks, then analyzes:
1. Facial landmark symmetry — deepfakes have subtle L/R asymmetry artifacts
2. Face proportion consistency — golden ratio violations
3. Face-background boundary noise — splicing/blending artifacts
4. Frequency domain analysis — GAN fingerprints in the face region
5. Noise consistency — face vs. background noise pattern mismatch

Falls back to frequency+noise heuristics when no face is detected.
"""
import io
import logging
import os
import threading
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from app.services.deepfake.base import DeepfakeProvider, DeepfakeResult
from app.services.deepfake.heuristic import compute_stats

logger = logging.getLogger("pramaan.deepfake")

_MODEL_PATH = str(Path(__file__).resolve().parent.parent.parent.parent / "models" / "face_landmarker.task")
_lock = threading.Lock()
_landmarker = None


def _ensure_model():
    if os.path.exists(_MODEL_PATH):
        return
    import urllib.request
    os.makedirs(os.path.dirname(_MODEL_PATH), exist_ok=True)
    url = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
    logger.info("Downloading FaceLandmarker model...")
    urllib.request.urlretrieve(url, _MODEL_PATH)


def _get_landmarker():
    global _landmarker
    if _landmarker is not None:
        return _landmarker
    with _lock:
        if _landmarker is not None:
            return _landmarker
        try:
            _ensure_model()
            import mediapipe as mp
            base_options = mp.tasks.BaseOptions(model_asset_path=_MODEL_PATH)
            options = mp.tasks.vision.FaceLandmarkerOptions(
                base_options=base_options,
                num_faces=1,
                min_face_detection_confidence=0.5,
                min_face_presence_confidence=0.5,
            )
            _landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(options)
        except Exception as e:
            logger.warning("FaceLandmarker init failed: %s", e)
    return _landmarker


def _symmetry_score(landmarks: list) -> tuple[float, str]:
    """Measure left-right facial symmetry from mesh landmarks.
    Returns (anomaly_score 0-1, description)."""
    if len(landmarks) < 468:
        return 0.0, "insufficient landmarks"

    pairs = [
        (234, 454), (130, 359), (33, 263), (159, 386),
        (145, 374), (133, 362), (46, 276), (105, 334),
        (107, 336), (70, 300), (63, 293), (52, 282),
    ]

    midline_x = landmarks[1].x
    diffs = []
    for l_idx, r_idx in pairs:
        l_dist = abs(landmarks[l_idx].x - midline_x)
        r_dist = abs(landmarks[r_idx].x - midline_x)
        if max(l_dist, r_dist) > 0.001:
            diffs.append(abs(l_dist - r_dist) / max(l_dist, r_dist))

    if not diffs:
        return 0.0, "no measurable pairs"

    mean_asymmetry = float(np.mean(diffs))
    score = min(1.0, mean_asymmetry * 5.0)
    return score, f"mean L/R asymmetry {mean_asymmetry:.4f}"


def _proportion_score(landmarks: list) -> tuple[float, str]:
    """Check facial proportions against expected ratios."""
    if len(landmarks) < 468:
        return 0.0, "insufficient landmarks"

    eye_l = landmarks[33]
    eye_r = landmarks[263]
    nose_tip = landmarks[1]
    mouth_center = landmarks[13]
    chin = landmarks[152]
    forehead = landmarks[10]

    eye_dist = np.sqrt((eye_l.x - eye_r.x)**2 + (eye_l.y - eye_r.y)**2)
    if eye_dist < 0.01:
        return 0.0, "face too small"

    nose_to_mouth = np.sqrt((nose_tip.x - mouth_center.x)**2 + (nose_tip.y - mouth_center.y)**2)
    mouth_to_chin = np.sqrt((mouth_center.x - chin.x)**2 + (mouth_center.y - chin.y)**2)
    forehead_to_eye = np.sqrt((forehead.x - eye_l.x)**2 + (forehead.y - eye_l.y)**2)

    ratio1 = nose_to_mouth / eye_dist if eye_dist > 0 else 0
    ratio2 = mouth_to_chin / eye_dist if eye_dist > 0 else 0
    ratio3 = forehead_to_eye / eye_dist if eye_dist > 0 else 0

    deviations = [
        abs(ratio1 - 0.35),
        abs(ratio2 - 0.45),
        abs(ratio3 - 0.55),
    ]

    mean_dev = float(np.mean(deviations))
    score = min(1.0, mean_dev * 4.0)
    return score, f"proportion deviation {mean_dev:.4f} (r1={ratio1:.3f} r2={ratio2:.3f} r3={ratio3:.3f})"


def _boundary_score(img_array: np.ndarray, landmarks: list) -> tuple[float, str]:
    """Analyze noise at face-background boundary for splicing artifacts."""
    h, w = img_array.shape[:2]
    if len(landmarks) < 200:
        return 0.0, "insufficient landmarks"

    contour_indices = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361,
                       288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149,
                       150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]

    pts = np.array([(int(landmarks[i].x * w), int(landmarks[i].y * h))
                     for i in contour_indices if i < len(landmarks)], dtype=np.int32)

    if len(pts) < 10:
        return 0.0, "too few boundary points"

    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillConvexPoly(mask, pts, 255)

    kernel = np.ones((15, 15), np.uint8)
    dilated = cv2.dilate(mask, kernel)
    boundary = dilated - mask

    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY).astype(np.float32)
    blurred = cv2.GaussianBlur(gray, (3, 3), 1.0)
    noise = gray - blurred

    boundary_pixels = noise[boundary > 0]
    interior_pixels = noise[mask > 0]

    if len(boundary_pixels) < 50 or len(interior_pixels) < 50:
        return 0.0, "insufficient pixels for analysis"

    boundary_var = float(np.var(boundary_pixels))
    interior_var = float(np.var(interior_pixels))

    ratio = boundary_var / (interior_var + 1e-6)
    score = min(1.0, max(0.0, (ratio - 1.5) / 3.0))
    return score, f"boundary/interior noise ratio {ratio:.3f}"


def _frequency_score(img_array: np.ndarray, landmarks: list) -> tuple[float, str]:
    """FFT analysis of the face region for GAN spectral fingerprints."""
    h, w = img_array.shape[:2]

    if landmarks and len(landmarks) > 300:
        xs = [lm.x for lm in landmarks]
        ys = [lm.y for lm in landmarks]
        x0 = max(0, int(min(xs) * w) - 10)
        y0 = max(0, int(min(ys) * h) - 10)
        x1 = min(w, int(max(xs) * w) + 10)
        y1 = min(h, int(max(ys) * h) + 10)
    else:
        x0, y0, x1, y1 = 0, 0, w, h

    face_region = cv2.cvtColor(img_array[y0:y1, x0:x1], cv2.COLOR_RGB2GRAY)
    if face_region.size < 100:
        return 0.0, "face region too small"

    face_64 = cv2.resize(face_region, (128, 128)).astype(np.float64)
    fft = np.fft.fftshift(np.fft.fft2(face_64))
    magnitude = np.log1p(np.abs(fft))

    cy, cx = 64, 64
    y_grid, x_grid = np.ogrid[:128, :128]
    radius = np.sqrt((y_grid - cy)**2 + (x_grid - cx)**2).astype(int)

    profile = []
    for r in range(16, 56):
        ring = magnitude[radius == r]
        if ring.size > 0:
            profile.append(float(ring.mean()))

    if len(profile) < 10:
        return 0.0, "insufficient frequency data"

    profile_arr = np.array(profile)
    gradient = np.gradient(profile_arr)
    spikiness = float(np.std(gradient) / (np.mean(np.abs(gradient)) + 1e-6))

    score = min(1.0, max(0.0, (spikiness - 1.0) / 4.0))
    return score, f"spectral spikiness {spikiness:.3f}"


class AdvancedDeepfakeProvider(DeepfakeProvider):
    def analyze(self, image_bytes: bytes) -> DeepfakeResult:
        try:
            pil_image = Image.open(io.BytesIO(image_bytes))
            pil_image = ImageOps.exif_transpose(pil_image)
            rgb = pil_image.convert("RGB")
            img_array = np.asarray(rgb)
        except Exception as e:
            return DeepfakeResult(status="ANALYZED", score=0.5,
                                  reason=f"Image decode failed: {e}")

        heuristic = compute_stats(image_bytes)
        freq_risk = max(0.0, min(1.0, heuristic.frequency_spikiness / 3.0))
        noise_risk = max(0.0, min(1.0, 1.0 - (heuristic.noise_uniformity_cv / 1.5)))

        landmarker = _get_landmarker()
        if landmarker is None:
            combined = 0.5 * freq_risk + 0.5 * noise_risk
            return DeepfakeResult(
                status="ANALYZED", score=round(combined, 4),
                reason=f"BlazeFace unavailable, heuristic only: frequency spikiness "
                       f"{heuristic.frequency_spikiness:.3f}, noise CV {heuristic.noise_uniformity_cv:.3f}",
            )

        try:
            import mediapipe as mp
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_array)
            result = landmarker.detect(mp_image)
        except Exception as e:
            combined = 0.5 * freq_risk + 0.5 * noise_risk
            return DeepfakeResult(
                status="ANALYZED", score=round(combined, 4),
                reason=f"BlazeFace detection failed ({e}), heuristic fallback",
            )

        if not result.face_landmarks:
            combined = 0.5 * freq_risk + 0.5 * noise_risk
            return DeepfakeResult(
                status="ANALYZED", score=round(combined, 4),
                reason=f"No face landmarks detected, heuristic only: "
                       f"freq={heuristic.frequency_spikiness:.3f}, noise_cv={heuristic.noise_uniformity_cv:.3f}",
            )

        lm = result.face_landmarks[0]
        sym_score, sym_detail = _symmetry_score(lm)
        prop_score, prop_detail = _proportion_score(lm)
        bound_score, bound_detail = _boundary_score(img_array, lm)
        fft_score, fft_detail = _frequency_score(img_array, lm)

        weights = {
            "symmetry": (sym_score, 0.20),
            "proportion": (prop_score, 0.15),
            "boundary": (bound_score, 0.25),
            "frequency": (fft_score, 0.20),
            "heuristic_freq": (freq_risk, 0.10),
            "heuristic_noise": (noise_risk, 0.10),
        }

        overall = sum(s * w for s, w in weights.values())
        overall = round(min(1.0, overall), 4)

        details = []
        for name, (s, _) in sorted(weights.items(), key=lambda x: -x[1][0]):
            if s > 0.3:
                detail_map = {
                    "symmetry": sym_detail, "proportion": prop_detail,
                    "boundary": bound_detail, "frequency": fft_detail,
                    "heuristic_freq": f"spikiness {heuristic.frequency_spikiness:.3f}",
                    "heuristic_noise": f"noise CV {heuristic.noise_uniformity_cv:.3f}",
                }
                details.append(f"{name}={s:.2f} ({detail_map[name]})")

        if details:
            reason = f"BlazeFace analysis score {overall:.3f}: " + "; ".join(details[:3])
        else:
            reason = f"BlazeFace analysis score {overall:.3f}: no significant deepfake indicators"

        return DeepfakeResult(status="ANALYZED", score=overall, reason=reason)
