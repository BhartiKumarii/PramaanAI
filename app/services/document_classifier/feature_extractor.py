"""Extract structural features from document images for classification."""
import cv2
import numpy as np

_blazeface_detector = None


def _get_face_detector():
    """Use BlazeFace via MediaPipe for face detection in feature extraction."""
    global _blazeface_detector
    if _blazeface_detector is not None:
        return _blazeface_detector
    try:
        from app.services.face.blazeface_detector import BlazeFaceDetector
        _blazeface_detector = BlazeFaceDetector()
    except Exception:
        pass
    return _blazeface_detector


def decode_image(image_bytes: bytes) -> np.ndarray | None:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


def extract_features(image: np.ndarray) -> dict:
    h, w = image.shape[:2]
    total_pixels = h * w

    aspect_ratio = w / h if h > 0 else 0.0

    # --- Color histogram in HSV (3 channels × 16 bins) ---
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hist_h = cv2.calcHist([hsv], [0], None, [16], [0, 180]).flatten()
    hist_s = cv2.calcHist([hsv], [1], None, [16], [0, 256]).flatten()
    hist_v = cv2.calcHist([hsv], [2], None, [16], [0, 256]).flatten()
    # Normalise each channel to sum to 1
    hist_h = (hist_h / (hist_h.sum() + 1e-8)).tolist()
    hist_s = (hist_s / (hist_s.sum() + 1e-8)).tolist()
    hist_v = (hist_v / (hist_v.sum() + 1e-8)).tolist()

    # --- Text density via Canny edge detection ---
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    text_density = float(np.count_nonzero(edges) / total_pixels)

    # --- Face presence (BlazeFace via MediaPipe) ---
    face_count = 0
    face_area_ratio = 0.0
    detector = _get_face_detector()
    if detector is not None:
        try:
            _, buf = cv2.imencode(".jpg", image)
            result = detector.detect(buf.tobytes())
            face_count = result.face_count
            for face in result.faces:
                face_area_ratio += (face.width * face.height) / (w * h)
        except Exception:
            pass
    face_present = 1.0 if face_count > 0 else 0.0

    # --- Horizontal line count (HoughLinesP on edges) ---
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80, minLineLength=w * 0.3, maxLineGap=10)
    h_line_count = 0
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
            if angle < 10 or angle > 170:
                h_line_count += 1

    # --- Color dominance (% of certain colour ranges in HSV) ---
    h_ch, s_ch, v_ch = cv2.split(hsv)

    # Blue region (hue ~100-130)
    blue_mask = cv2.inRange(hsv, np.array([100, 50, 50]), np.array([130, 255, 255]))
    blue_ratio = float(np.count_nonzero(blue_mask) / total_pixels)

    # Green region (hue ~35-85)
    green_mask = cv2.inRange(hsv, np.array([35, 50, 50]), np.array([85, 255, 255]))
    green_ratio = float(np.count_nonzero(green_mask) / total_pixels)

    # Red region (hue 0-10 or 170-180)
    red_mask1 = cv2.inRange(hsv, np.array([0, 50, 50]), np.array([10, 255, 255]))
    red_mask2 = cv2.inRange(hsv, np.array([170, 50, 50]), np.array([180, 255, 255]))
    red_ratio = float((np.count_nonzero(red_mask1) + np.count_nonzero(red_mask2)) / total_pixels)

    # White region (low saturation, high value)
    white_mask = cv2.inRange(hsv, np.array([0, 0, 200]), np.array([180, 30, 255]))
    white_ratio = float(np.count_nonzero(white_mask) / total_pixels)

    # --- Structured text score (ratio of lines matching label:value pattern) ---
    # Approximate via measuring uniformity of edge distribution in horizontal bands
    band_count = 10
    band_h = h // band_count
    band_densities = []
    for i in range(band_count):
        band = edges[i * band_h : (i + 1) * band_h, :]
        band_densities.append(float(np.count_nonzero(band) / (band.size + 1e-8)))
    edge_uniformity = float(1.0 - np.std(band_densities) / (np.mean(band_densities) + 1e-8))
    edge_uniformity = max(0.0, min(1.0, edge_uniformity))

    return {
        "aspect_ratio": aspect_ratio,
        "text_density": text_density,
        "face_present": face_present,
        "face_count": float(face_count),
        "face_area_ratio": face_area_ratio,
        "h_line_count": float(h_line_count),
        "blue_ratio": blue_ratio,
        "green_ratio": green_ratio,
        "red_ratio": red_ratio,
        "white_ratio": white_ratio,
        "edge_uniformity": edge_uniformity,
        "hist_h": hist_h,
        "hist_s": hist_s,
        "hist_v": hist_v,
    }


def extract_features_from_bytes(image_bytes: bytes) -> dict | None:
    img = decode_image(image_bytes)
    if img is None:
        return None
    return extract_features(img)
