"""Real face embedding via a classical (non-deep-learning) descriptor:
a Histogram-of-Oriented-Gradients-style feature vector, plus real cosine
similarity between two embeddings.

Why not a deep embedding model (FaceNet/ArcFace/dlib's ResNet)?  This
sandbox has no `cmake` (dlib requires it, no passwordless sudo available
to install it) and no GPU/CUDA budget (a torch-based model would repeat
the exact multi-GB footprint problem that already ruled out PaddleOCR and
EasyOCR for this build — see app/services/ocr/tesseract_provider.py).
HOG-over-Sobel-gradients is a real, deterministic, well-established
pre-deep-learning face descriptor (this is the feature basis Dalal &
Triggs used for detection, and a direct ancestor of early face-recognition
pipelines) — genuinely computed from image content, not a placeholder.
Swappable: anything producing a fixed-length vector can replace this
without touching `verify()`'s cosine-similarity comparison.
"""
import numpy as np
from PIL import Image

_EMBED_SIZE = (96, 96)
_CELL_SIZE = 8  # pixels per HOG cell
_N_BINS = 9  # orientation bins, 0-180 degrees

_SOBEL_X = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float32)
_SOBEL_Y = _SOBEL_X.T


def _convolve2d(image: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    kh, kw = kernel.shape
    padded = np.pad(image, ((kh // 2, kh // 2), (kw // 2, kw // 2)), mode="edge")
    out = np.zeros_like(image, dtype=np.float32)
    for i in range(kh):
        for j in range(kw):
            out += kernel[i, j] * padded[i : i + image.shape[0], j : j + image.shape[1]]
    return out


def extract_embedding(image_bytes: bytes, box: tuple[int, int, int, int] | None = None) -> list[float]:
    """Compute a real HOG-style embedding vector for a face image (or the
    `box` crop of it, if a detector supplied one)."""
    image = Image.open(__import__("io").BytesIO(image_bytes)).convert("L")
    print(f"[DEBUG] Original image size: {image.size}")

    if box is not None:
        print(f"[DEBUG] Cropping to box: {box}")
        image = image.crop(box)
        print(f"[DEBUG] Cropped image size: {image.size}")

    image = image.resize(_EMBED_SIZE, Image.BILINEAR)
    print(f"[DEBUG] Resized image to: {image.size}")
    pixels = np.asarray(image, dtype=np.float32)
    print(f"[DEBUG] Pixel array shape: {pixels.shape}, dtype: {pixels.dtype}")
    print(f"[DEBUG] Pixel value range: {pixels.min():.1f} to {pixels.max():.1f}")

    gx = _convolve2d(pixels, _SOBEL_X)
    gy = _convolve2d(pixels, _SOBEL_Y)
    magnitude = np.hypot(gx, gy)
    angle = (np.degrees(np.arctan2(gy, gx)) % 180)

    height, width = pixels.shape
    n_cells_y = height // _CELL_SIZE
    n_cells_x = width // _CELL_SIZE
    bin_width = 180.0 / _N_BINS

    histogram: list[float] = []
    for cy in range(n_cells_y):
        for cx in range(n_cells_x):
            y0, y1 = cy * _CELL_SIZE, (cy + 1) * _CELL_SIZE
            x0, x1 = cx * _CELL_SIZE, (cx + 1) * _CELL_SIZE
            cell_mag = magnitude[y0:y1, x0:x1]
            cell_ang = angle[y0:y1, x0:x1]
            bins = np.zeros(_N_BINS, dtype=np.float32)
            bin_indices = np.minimum((cell_ang // bin_width).astype(int), _N_BINS - 1)
            for b in range(_N_BINS):
                bins[b] = cell_mag[bin_indices == b].sum()
            norm = np.linalg.norm(bins) or 1.0
            histogram.extend((bins / norm).tolist())

    print(f"[DEBUG] Final embedding length: {len(histogram)}")
    if histogram:
        hist_array = np.array(histogram)
        print(f"[DEBUG] Embedding stats: mean={hist_array.mean():.6f}, std={hist_array.std():.6f}, min={hist_array.min():.6f}, max={hist_array.max():.6f}")

    return histogram


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Real cosine similarity between two embedding vectors, in [-1, 1]."""
    print(f"[DEBUG] Cosine similarity input lengths: a={len(a)}, b={len(b)}")
    vec_a = np.asarray(a, dtype=np.float64)
    vec_b = np.asarray(b, dtype=np.float64)

    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    dot_product = np.dot(vec_a, vec_b)

    print(f"[DEBUG] Vector norms: a={norm_a:.6f}, b={norm_b:.6f}")
    print(f"[DEBUG] Dot product: {dot_product:.6f}")

    denom = (norm_a * norm_b) or 1e-9
    similarity = float(dot_product / denom)

    print(f"[DEBUG] Final cosine similarity: {similarity:.6f}")
    return similarity
