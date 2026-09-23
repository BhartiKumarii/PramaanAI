"""Region-scoped image forensics.

Why a new layer on top of app/services/tampering: the existing whole-image
provider is kept (and still used by the original screening endpoints), but on
real genuine card photos it reports tampering_risk 1.0 with many
"noise_high_variance" findings, because printed photos, holograms and
guilloche legitimately differ from plain background. Here each region
(photo, stamp, text, QR, security feature) is compared against a ring of its
OWN surroundings, with several independent methods:

  sharpness    — Laplacian variance ratio (region vs ring)
  noise        — high-pass residual std ratio (region vs ring)
  compression  — error-level (JPEG re-save) ratio (region vs ring)
  jpeg_grid    — 8x8 block-grid strength ratio (a JPEG patch pasted into a
                 lossless or differently-compressed page shows a grid the
                 surroundings don't)
  duplicate    — near-identical copies of the same patch elsewhere
                 (copy-paste), via normalised cross-correlation

A region is flagged only when enough independent methods agree ("consensus":
2 for photographs and other regions, 3 for ink regions — text and stamps);
fewer is reported as a weak indicator only. An exact duplicate always flags.
Thresholds live in THRESHOLDS and are calibrated on genuine images (see
scripts/docverify/calibrate_forensics.py) — never presented as certainty.
"""
from __future__ import annotations

import io
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

MIN_METHODS = 2
# Ink on textured paper (text fields, stamps) differs from its surroundings
# more often for innocent reasons, so it needs broader agreement.
MIN_METHODS_BY_FAMILY = {"TEXT": 3, "STAMP": 3}

# ratio thresholds: indicator fires when ratio > high or ratio < low.
THRESHOLDS: dict[str, dict[str, float]] = {
    "sharpness": {"high": 6.0, "low": 0.12},
    "noise": {"high": 3.2, "low": 0.25},
    "compression": {"high": 2.6, "low": 0.3},
    "jpeg_grid": {"high": 2.2, "low": 0.0},
}

_CALIBRATION_FILE = Path(__file__).with_name("forensics_thresholds.json")


@lru_cache
def calibrated_thresholds() -> dict[str, dict[str, dict[str, float]]]:
    """Per region family (PHOTOGRAPH / TEXT / STAMP / QR_CODE /
    SECURITY_FEATURE) thresholds produced by
    scripts/docverify/calibrate_forensics.py. Falls back to THRESHOLDS."""
    if _CALIBRATION_FILE.exists():
        return json.loads(_CALIBRATION_FILE.read_text())["families"]
    return {}


def region_family(label: str) -> str:
    return "TEXT" if label.startswith("TEXT") else label


def thresholds_for(label: str) -> dict[str, dict[str, float]]:
    fam = calibrated_thresholds().get(region_family(label), {})
    return {m: fam.get(m, t) for m, t in THRESHOLDS.items()}


INDICATOR_NAMES = {
    "sharpness": "inconsistent_sharpness",
    "noise": "inconsistent_noise",
    "compression": "inconsistent_compression_region",
    "jpeg_grid": "compression_grid_mismatch",
    "duplicate": "duplicated_image_region",
    "metadata": "editing_software_metadata",
}

PLAIN = {
    "inconsistent_sharpness": "sharpness differs sharply from the surrounding area",
    "inconsistent_noise": "image noise differs from the surrounding area",
    "inconsistent_compression_region": "compression level differs from the surrounding area",
    "compression_grid_mismatch": "a compression pattern appears only in this area",
    "duplicated_image_region": "an identical copy of this area appears elsewhere in the image",
    "editing_software_metadata": "file metadata names image-editing software",
}

_EDITING_SOFTWARE = ("photoshop", "gimp", "paint.net", "pixlr", "canva", "snapseed", "picsart", "affinity", "lightroom")


def _ring(bbox: list[int], shape: tuple[int, ...], pad_frac: float = 0.35) -> tuple[list[int], list[int]]:
    h, w = shape[:2]
    bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = int(max(bw, bh) * pad_frac) + 6
    outer = [max(0, bbox[0] - pad), max(0, bbox[1] - pad), min(w, bbox[2] + pad), min(h, bbox[3] + pad)]
    inner = [max(0, bbox[0]), max(0, bbox[1]), min(w, bbox[2]), min(h, bbox[3])]
    return inner, outer


def _masked_stats(values: np.ndarray, inner: list[int], outer: list[int], fn,
                  keep: np.ndarray | None = None) -> tuple[float, float]:
    """Statistic inside the region vs in the surrounding ring. `keep` (a
    full-image boolean mask) restricts both sides to the same kind of
    pixels — e.g. background paper only, so ink strokes are never compared
    with blank paper."""
    ox0, oy0, ox1, oy1 = outer
    ring_mask = np.ones((oy1 - oy0, ox1 - ox0), dtype=bool)
    ring_mask[inner[1] - oy0:inner[3] - oy0, inner[0] - ox0:inner[2] - ox0] = False
    inside_mask = np.zeros_like(ring_mask)
    inside_mask[inner[1] - oy0:inner[3] - oy0, inner[0] - ox0:inner[2] - ox0] = True
    crop = values[oy0:oy1, ox0:ox1]
    if keep is not None:
        k = keep[oy0:oy1, ox0:ox1]
        ring_mask &= k
        inside_mask &= k
    inside, ring = crop[inside_mask], crop[ring_mask]
    if inside.size < 64 or ring.size < 64:
        return float("nan"), float("nan")
    return fn(inside), fn(ring)


def _ela_map(rgb: np.ndarray, quality: int = 90) -> np.ndarray:
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, "JPEG", quality=quality)
    resaved = np.asarray(Image.open(io.BytesIO(buf.getvalue())).convert("RGB"))
    return np.abs(rgb.astype(np.int16) - resaved.astype(np.int16)).mean(axis=2).astype(np.float32)


def _grid_map(gray: np.ndarray) -> np.ndarray:
    """Per-pixel strength of 8x8 JPEG block boundaries: the absolute
    horizontal/vertical second difference sampled on the block grid."""
    g = gray.astype(np.float32)
    dx = np.zeros_like(g)
    dy = np.zeros_like(g)
    dx[:, 1:-1] = np.abs(2 * g[:, 1:-1] - g[:, :-2] - g[:, 2:])
    dy[1:-1, :] = np.abs(2 * g[1:-1, :] - g[:-2, :] - g[2:, :])
    grid = np.zeros_like(g)
    grid[:, 7::8] += dx[:, 7::8]
    grid[7::8, :] += dy[7::8, :]
    off = np.zeros_like(g)
    off[:, 3::8] += dx[:, 3::8]
    off[3::8, :] += dy[3::8, :]
    # grid energy relative to off-grid energy, smoothed over 16px
    return cv2.blur(grid, (16, 16)) / (cv2.blur(off, (16, 16)) + 1.0)


class ForensicMaps:
    """Per-image maps computed once and reused for every region."""

    def __init__(self, rgb: np.ndarray):
        self.rgb = rgb
        self.gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        self.lap = np.abs(cv2.Laplacian(self.gray, cv2.CV_32F))
        self.residual = np.abs(self.gray.astype(np.float32) - cv2.medianBlur(self.gray, 3).astype(np.float32))
        self.ela = _ela_map(rgb)
        self.grid = _grid_map(self.gray)
        # Background (paper) pixels: close to the local median brightness and
        # weakly saturated. Ink, print and photo content are excluded.
        local_bg = cv2.medianBlur(self.gray, 21).astype(np.int16)
        sat = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)[..., 1]
        foreground = ((np.abs(self.gray.astype(np.int16) - local_bg) >= 18) | (sat >= 60)).astype(np.uint8)
        # Dilate so anti-aliased ink edges never count as "paper".
        foreground = cv2.dilate(foreground, np.ones((7, 7), np.uint8))
        self.background = foreground == 0


# Which methods are meaningful for which region family:
#  * QR codes are high-contrast by design, so sharpness/noise differences are
#    content, not evidence — only compression-based methods apply.
#  * Stamps and text are ink on paper: every method is measured on the
#    background paper pixels only, so ink is never compared with blank paper.
#  * Security features (chip-like pads, holograms) are designed to look
#    unlike their surroundings — same rule as QR codes.
#  * A printed portrait is naturally smoother / less noisy than guilloche and
#    text around it, so only a SHARPER or NOISIER photo (a pasted-in capture)
#    is evidence; the "low" direction is not used for photographs.
#  * For QR codes, barcodes and security features, region-vs-surroundings
#    statistics are dominated by the (deliberately unusual) content, so no
#    statistical method is applied — their integrity is checked by decoding,
#    signatures and consistency instead; exact duplicates are still flagged.
_METHODS_BY_FAMILY = {"QR_CODE": (), "BARCODE": (), "SECURITY_FEATURE": ()}
_HIGH_ONLY = {"PHOTOGRAPH": {"sharpness", "noise"}}
_BACKGROUND_ONLY = {"STAMP", "TEXT"}


def _ratio(a: float, b: float) -> float | None:
    if np.isnan(a) or np.isnan(b):
        return None
    return round(float((a + 1e-3) / (b + 1e-3)), 3)


def analyze_region(maps: ForensicMaps, region_id: str, label: str, bbox: list[int]) -> dict[str, Any]:
    inner, outer = _ring(bbox, maps.gray.shape)
    family = region_family(label)
    keep = maps.background if family in _BACKGROUND_ONLY else None
    applicable = _METHODS_BY_FAMILY.get(family, ("sharpness", "noise", "compression", "jpeg_grid"))
    sources = {"sharpness": (maps.lap ** 2, np.mean), "noise": (maps.residual, np.std),
               "compression": (maps.ela, np.mean), "jpeg_grid": (maps.grid, np.mean)}
    measures: dict[str, float | None] = {
        m: (_ratio(*_masked_stats(sources[m][0], inner, outer, sources[m][1], keep)) if m in applicable else None)
        for m in sources}
    fired: list[dict[str, Any]] = []
    limits = thresholds_for(label)
    for method, value in measures.items():
        if value is None:
            continue
        t = limits[method]
        low_applies = t["low"] and method not in _HIGH_ONLY.get(family, set())
        if value > t["high"] or (low_applies and value < t["low"]):
            name = INDICATOR_NAMES[method]
            fired.append({"indicator": name, "method": method, "ratio": value,
                          "threshold": t, "reason": PLAIN[name]})
    return {"region_id": region_id, "region_label": label, "bbox": bbox, "measures": measures, "indicators": fired}


def analyze_text_peers(maps: ForensicMaps, targets: list[tuple[str, str, list[int]]]) -> list[dict[str, Any]]:
    """Text fields compared with the document's OTHER text fields (not with
    their surroundings, which mix blank paper with guilloche). A field typed
    or pasted in afterwards carries different noise/compression/sharpness
    from its sibling fields that were printed together. Needs >= 3 fields;
    otherwise falls back to the region-vs-surroundings comparison."""
    if len(targets) < 3:
        return [analyze_region(maps, rid, label, bbox) for rid, label, bbox in targets]
    h, w = maps.gray.shape
    sources = {"sharpness": (maps.lap ** 2, np.mean), "noise": (maps.residual, np.std),
               "compression": (maps.ela, np.mean), "jpeg_grid": (maps.grid, np.mean)}
    stats: list[dict[str, float | None]] = []
    for _, _, b in targets:
        x0, y0, x1, y1 = max(0, b[0]), max(0, b[1]), min(w, b[2]), min(h, b[3])
        keep = maps.background[y0:y1, x0:x1]
        row = {}
        for m, (arr, fn) in sources.items():
            vals = arr[y0:y1, x0:x1][keep]
            row[m] = float(fn(vals)) if vals.size >= 64 else None
        stats.append(row)
    out = []
    for k, (rid, label, bbox) in enumerate(targets):
        measures: dict[str, float | None] = {}
        fired: list[dict[str, Any]] = []
        limits = thresholds_for(label)
        for m in sources:
            others = [s[m] for j, s in enumerate(stats) if j != k and s[m] is not None]
            if stats[k][m] is None or len(others) < 2:
                measures[m] = None
                continue
            ratio = _ratio(stats[k][m], float(np.median(others)))
            measures[m] = ratio
            t = limits[m]
            if ratio is not None and (ratio > t["high"] or (t["low"] and ratio < t["low"])):
                name = INDICATOR_NAMES[m]
                fired.append({"indicator": name, "method": m, "ratio": ratio, "threshold": t,
                              "reason": PLAIN[name].replace("the surrounding area", "the document's other text fields")})
        out.append({"region_id": rid, "region_label": label, "bbox": bbox, "measures": measures, "indicators": fired,
                    "comparison": "peer_text_fields"})
    return out


def find_duplicates(gray: np.ndarray, bboxes: list[tuple[str, list[int]]], min_corr: float = 0.97) -> list[dict[str, Any]]:
    """Near-identical copies of a region elsewhere in the image (copy-move).
    Compares each region's patch against the full image by normalised cross-
    correlation, ignoring its own location."""
    hits: list[dict[str, Any]] = []
    h, w = gray.shape
    for rid, b in bboxes:
        x0, y0, x1, y1 = max(0, b[0]), max(0, b[1]), min(w, b[2]), min(h, b[3])
        patch = gray[y0:y1, x0:x1]
        if patch.size < 900 or patch.std() < 8:
            continue
        # Match near full resolution: downsampling breaks pixel-exact copies
        # whose offset is not a multiple of the scale factor.
        scale = 1200 / max(gray.shape) if max(gray.shape) > 1200 else 1.0
        g_s = cv2.resize(gray, None, fx=scale, fy=scale)
        p_s = cv2.resize(patch, None, fx=scale, fy=scale)
        if min(p_s.shape) < 12:
            continue
        res = cv2.matchTemplate(g_s, p_s, cv2.TM_CCOEFF_NORMED)
        sx, sy = int(x0 * scale), int(y0 * scale)
        ph, pw = p_s.shape
        res[max(0, sy - ph // 2):sy + ph // 2 + 1, max(0, sx - pw // 2):sx + pw // 2 + 1] = -1
        _, max_val, _, loc = cv2.minMaxLoc(res)
        if max_val >= min_corr:
            dup = [int(loc[0] / scale), int(loc[1] / scale), int(loc[0] / scale) + (x1 - x0), int(loc[1] / scale) + (y1 - y0)]
            hits.append({"region_id": rid, "indicator": "duplicated_image_region", "method": "duplicate",
                         "correlation": round(float(max_val), 3), "duplicate_bbox": dup,
                         "reason": PLAIN["duplicated_image_region"]})
    return hits


def metadata_indicators(image_bytes: bytes) -> list[dict[str, Any]]:
    try:
        img = Image.open(io.BytesIO(image_bytes))
        exif = img.getexif()
        software = str(exif.get(0x0131, "") or img.info.get("Software", "")).strip()
    except Exception:
        return []
    if software and any(s in software.lower() for s in _EDITING_SOFTWARE):
        return [{"indicator": "editing_software_metadata", "method": "metadata", "software": software,
                 "reason": PLAIN["editing_software_metadata"] + f" ({software})"}]
    return []


def summarize(region_results: list[dict[str, Any]], duplicates: list[dict[str, Any]],
              metadata: list[dict[str, Any]]) -> dict[str, Any]:
    """Consensus: a region is 'flagged' when >= MIN_METHODS independent
    methods fire on it. Duplicates count as a method for their region."""
    by_region = {r["region_id"]: r for r in region_results}
    for d in duplicates:
        if d["region_id"] in by_region:
            by_region[d["region_id"]]["indicators"].append(d)
    flagged, weak = [], []
    for r in by_region.values():
        methods = {i["method"] for i in r["indicators"]}
        r["methods_agreeing"] = sorted(methods)
        needed = MIN_METHODS_BY_FAMILY.get(region_family(r["region_label"]), MIN_METHODS)
        if len(methods) >= needed or "duplicate" in methods:
            r["consensus"] = "FLAGGED"
            flagged.append(r)
        elif methods:
            r["consensus"] = "WEAK_INDICATOR"
            weak.append(r)
        else:
            r["consensus"] = "NONE"
    indicators = sorted({i["indicator"] for r in flagged for i in r["indicators"]} |
                        {m["indicator"] for m in metadata})
    n_methods = max((len(r["methods_agreeing"]) for r in flagged), default=0)
    confidence = round(min(0.9, 0.35 + 0.15 * n_methods + (0.1 if metadata else 0.0)), 2) if flagged else (0.3 if metadata else 0.0)
    return {
        "tampering_detected": bool(flagged),
        "confidence": confidence,
        "indicators": indicators,
        "flagged_regions": [{"region_id": r["region_id"], "region_label": r["region_label"], "bbox": r["bbox"],
                             "methods": r["methods_agreeing"],
                             "reasons": sorted({i["reason"] for i in r["indicators"]})} for r in flagged],
        "weak_indicators": [{"region_id": r["region_id"], "region_label": r["region_label"],
                             "methods": r["methods_agreeing"]} for r in weak],
        "metadata": metadata,
        "regions": list(by_region.values()),
        "method_note": ("Region-vs-surroundings comparison with consensus of independent methods. "
                        "Indicators are evidence for officer review, not proof of manipulation."),
    }
