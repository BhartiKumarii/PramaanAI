"""Layout (template) consistency and visual security-feature analysis.

Everything here is *visual evidence* scored against a document-type-specific
template (reference_data/<country>/<doc>/templates.json). Nothing here
authenticates a document:

  * Layout: detected photo / QR / MRZ / yellow-gold feature positions are
    compared with the template's expected relative regions, with generous
    tolerance (cameras, crops and legitimate variants differ).
  * Yellow/gold feature (driving licences): detected as a VISUAL SECURITY
    FEATURE and checked for position, size, shape, orientation, colour and
    texture consistency. It is never assumed to be an electronic chip, and
    its colour is never evidence of genuineness.
  * Electronic chip / contactless component: never read, cloned or
    bypassed — always NOT_VERIFIED unless an authorised reader adapter is
    configured (none is, in this build).
  * Guilloche / hologram: presence *indicators* only.
  * UV / microprint: require equipment a phone photo can't provide ->
    NOT_VERIFIED.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import cv2
import numpy as np

from app.services.docverify import reference
from app.services.docverify.types import Region, RegionLabel

_ANCHOR_LABELS = {"PHOTOGRAPH": RegionLabel.PHOTOGRAPH, "QR_CODE": RegionLabel.QR_CODE, "MRZ": RegionLabel.MRZ}


def _rel(bbox: list[int], w: int, h: int) -> list[float]:
    return [bbox[0] / w, bbox[1] / h, bbox[2] / w, bbox[3] / h]


def _centre(b: list[float]) -> tuple[float, float]:
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def _area(b: list[float]) -> float:
    return max(1e-6, (b[2] - b[0]) * (b[3] - b[1]))


def compare_position(detected_rel: list[float], expected_rel: list[float],
                     centre_tol: float = 0.14, size_range: tuple[float, float] = (0.3, 3.0)) -> dict[str, Any]:
    cx, cy = _centre(detected_rel)
    ex, ey = _centre(expected_rel)
    dist = float(np.hypot(cx - ex, cy - ey))
    size_ratio = _area(detected_rel) / _area(expected_rel)
    return {"centre_distance": round(dist, 3), "size_ratio": round(size_ratio, 3),
            "position_ok": dist <= centre_tol, "size_ok": size_range[0] <= size_ratio <= size_range[1]}


def layout_consistency(document_type: str, country: str | None, regions: list[Region], shape: tuple[int, ...],
                       on: date, extra_anchors: dict[str, list[int]] | None = None) -> dict[str, Any]:
    """Best-matching template version and per-anchor comparison."""
    h, w = shape[:2]
    versions = reference.template_versions(document_type, country, on)
    if not versions:
        return {"status": "REFERENCE_NOT_AVAILABLE", "reason": f"no layout template for {document_type}/{country}"}
    detected: dict[str, list[int]] = {}
    for key, label in _ANCHOR_LABELS.items():
        cands = [r for r in regions if r.label == label]
        if cands:
            detected[key] = max(cands, key=lambda r: r.confidence).bbox
    detected.update(extra_anchors or {})

    best: dict[str, Any] | None = None
    for v in versions:
        anchors = v.get("layout_anchors", {})
        comparisons = {}
        for key, expected in anchors.items():
            if key in detected:
                comp = compare_position(_rel(detected[key], w, h), expected)
                if key == "MRZ":
                    rel = _rel(detected[key], w, h)
                    comp.update(position_ok=abs((rel[1] + rel[3]) / 2 - (expected[1] + expected[3]) / 2) <= 0.1,
                                size_ok=True)
                comparisons[key] = {**comp, "expected_region": expected,
                                    "detected_region": [round(x, 3) for x in _rel(detected[key], w, h)],
                                    "bbox": detected[key]}
            else:
                comparisons[key] = {"detected": False, "expected_region": expected}
        checked = [c for c in comparisons.values() if c.get("detected", True)]
        ok = [c for c in checked if c["position_ok"] and c["size_ok"]]
        score = len(ok) / len(checked) if checked else 0.0
        candidate = {"template_version": v["version"], "anchors": comparisons, "checked": len(checked),
                     "consistent": len(ok), "score": round(score, 3),
                     "expected_text_patterns": v.get("expected_text_patterns", [])}
        if best is None or (candidate["score"], candidate["checked"]) > (best["score"], best["checked"]):
            best = candidate
    assert best is not None
    if best["checked"] == 0:
        best["status"] = "NOT_VERIFIED"
        best["reason"] = "none of the template's layout anchors (photo/QR/MRZ) could be located"
    elif best["score"] >= 0.66:
        best["status"] = "PASS"
        best["reason"] = f"{best['consistent']}/{best['checked']} layout anchors match template {best['template_version']}"
    else:
        best["status"] = "REVIEW_REQUIRED"
        bad = [k for k, c in best["anchors"].items() if c.get("detected", True) and not (c["position_ok"] and c["size_ok"])]
        best["reason"] = (f"{', '.join(k.lower().replace('_', ' ') for k in bad)} not where template "
                          f"{best['template_version']} expects it")
    best["aspect_ratio"] = round(w / h, 3)
    return best


# ----------------------------------------------------------- yellow/gold feature

def detect_yellow_gold_feature(bgr: np.ndarray, expected_rel: list[float] | None,
                               exclude: list[list[int]] | None = None) -> dict[str, Any]:
    """Locate a yellow/gold rectangular chip-like VISUAL feature and describe
    it. Returns detected=False (-> NOT_VERIFIED upstream) when nothing
    reliable is found; never a genuineness verdict."""
    h, w = bgr.shape[:2]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    # OpenCV hue 0-180: yellow/gold ≈ 12-38. Moderate saturation keeps
    # metallic (desaturated) gold while dropping cream/white paper.
    mask = ((hsv[..., 0] >= 12) & (hsv[..., 0] <= 38) & (hsv[..., 1] >= 55) & (hsv[..., 2] >= 80)).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8), iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for c in contours:
        area = cv2.contourArea(c)
        rel_area = area / (w * h)
        if not 0.004 <= rel_area <= 0.08:
            continue
        rect = cv2.minAreaRect(c)
        (rw, rh), angle = rect[1], rect[2]
        if min(rw, rh) < 12:
            continue
        rectangularity = area / max(1.0, rw * rh)
        aspect = max(rw, rh) / max(1.0, min(rw, rh))
        if rectangularity < 0.72 or aspect > 1.9:
            continue
        x, y, bw, bh = cv2.boundingRect(c)
        if exclude and any(_overlap(([x, y, x + bw, y + bh]), e) > 0.5 for e in exclude):
            continue
        score = rectangularity * (1.0 / aspect)
        if expected_rel:
            comp = compare_position(_rel([x, y, x + bw, y + bh], w, h), expected_rel)
            score *= 1.5 if comp["position_ok"] else 1.0
        candidates.append((score, c, rect, rectangularity, aspect, (x, y, bw, bh)))
    if not candidates:
        return {"detected": False, "feature_type": "VISUAL_SECURITY_FEATURE",
                "reason": "no yellow/gold rectangular feature could be reliably identified"}

    score, contour, rect, rectangularity, aspect, (x, y, bw, bh) = max(candidates, key=lambda t: t[0])
    roi = bgr[y:y + bh, x:x + bw]
    roi_hsv = hsv[y:y + bh, x:x + bw]
    roi_mask = mask[y:y + bh, x:x + bw] > 0
    hue_std = float(roi_hsv[..., 0][roi_mask].std()) if roi_mask.any() else 99.0
    sat_mean = float(roi_hsv[..., 1][roi_mask].mean()) if roi_mask.any() else 0.0
    edges = cv2.Canny(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY), 60, 160)
    edge_density = float((edges > 0).mean())
    angle = rect[2] if rect[2] <= 45 else rect[2] - 90

    bbox_xyxy = [x, y, x + bw, y + bh]
    pos = compare_position(_rel(bbox_xyxy, w, h), expected_rel, centre_tol=0.12, size_range=(0.35, 2.6)) if expected_rel else None
    position_consistency = ("PASS" if pos and pos["position_ok"] else "REVIEW_REQUIRED") if pos else "REFERENCE_NOT_AVAILABLE"
    size_consistency = ("PASS" if pos and pos["size_ok"] else "REVIEW_REQUIRED") if pos else "REFERENCE_NOT_AVAILABLE"
    shape_ok = rectangularity >= 0.8 and aspect <= 1.7
    orientation_ok = abs(angle) <= 12
    # Appearance: a uniform metallic hue with internal structure (contact
    # dividers / relief) — a flat, structureless patch is only "not
    # confirmed", never a finding of forgery.
    appearance_ok = hue_std <= 9 and sat_mean >= 60
    texture = "structured" if 0.03 <= edge_density <= 0.45 else ("flat" if edge_density < 0.03 else "noisy")
    appearance_consistency = "PASS" if appearance_ok and texture == "structured" else "NOT_VERIFIED"
    template_consistency = ("PASS" if position_consistency == "PASS" and size_consistency == "PASS" and shape_ok
                            else ("REFERENCE_NOT_AVAILABLE" if not expected_rel else "REVIEW_REQUIRED"))
    parts = [rectangularity, 1.0 if shape_ok else 0.6, 1.0 if orientation_ok else 0.7,
             1.0 if position_consistency == "PASS" else 0.5, 1.0 if appearance_consistency == "PASS" else 0.7]
    confidence = round(float(np.prod(parts)) ** (1 / len(parts)), 3)
    return {
        "detected": True,
        "feature_type": "VISUAL_SECURITY_FEATURE",
        "is_electronic_chip": "UNKNOWN_NOT_ASSESSED",
        "bbox": [x, y, bw, bh],  # [x, y, width, height] as requested
        "bbox_xyxy": bbox_xyxy,
        "relative_position": [round(v, 3) for v in _rel(bbox_xyxy, w, h)],
        "approximate_relative_size": round((bw * bh) / (w * h), 4),
        "shape": {"rectangularity": round(rectangularity, 3), "aspect_ratio": round(aspect, 3), "consistent": shape_ok},
        "orientation_degrees": round(float(angle), 1),
        "orientation_consistent": orientation_ok,
        "appearance": {"hue_std": round(hue_std, 2), "mean_saturation": round(sat_mean, 1),
                       "edge_density": round(edge_density, 3), "texture": texture},
        "position_consistency": position_consistency,
        "size_consistency": size_consistency,
        "appearance_consistency": appearance_consistency,
        "template_consistency": template_consistency,
        "template_comparison": pos,
        "confidence": confidence,
        "note": ("Visual feature only. Not treated as an electronic chip; its colour is never used "
                 "as evidence that the licence is genuine."),
    }


def _overlap(inner: list[int], outer: list[int]) -> float:
    ix0, iy0, ix1, iy1 = max(inner[0], outer[0]), max(inner[1], outer[1]), min(inner[2], outer[2]), min(inner[3], outer[3])
    inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
    return inter / max(1, (inner[2] - inner[0]) * (inner[3] - inner[1]))


# ----------------------------------------------------------- other indicators

def texture_indicator(gray: np.ndarray, rel_region: list[float], text_boxes: list[list[int]]) -> dict[str, Any]:
    """Fine-line (guilloche-like) texture indicator in a template region,
    excluding OCR text boxes. Presence indicator only."""
    h, w = gray.shape
    x0, y0, x1, y1 = int(rel_region[0] * w), int(rel_region[1] * h), int(rel_region[2] * w), int(rel_region[3] * h)
    roi = gray[y0:y1, x0:x1]
    if roi.size < 400:
        return {"observed": None, "reason": "region too small"}
    mask = np.ones(roi.shape, bool)
    for b in text_boxes:
        mask[max(0, b[1] - y0):max(0, b[3] - y0), max(0, b[0] - x0):max(0, b[2] - x0)] = False
    lines = cv2.Canny(cv2.GaussianBlur(roi, (3, 3), 0), 20, 60) > 0
    density = float(lines[mask].mean()) if mask.any() else 0.0
    return {"observed": density >= 0.04, "fine_line_density": round(density, 4), "bbox": [x0, y0, x1, y1]}


def hologram_indicator(bgr: np.ndarray, rel_region: list[float]) -> dict[str, Any]:
    h, w = bgr.shape[:2]
    x0, y0, x1, y1 = int(rel_region[0] * w), int(rel_region[1] * h), int(rel_region[2] * w), int(rel_region[3] * h)
    roi = bgr[y0:y1, x0:x1]
    if roi.size < 400:
        return {"observed": None, "reason": "region too small"}
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    sat = hsv[..., 1] > 40
    hue_spread = float(np.std(hsv[..., 0][sat])) if sat.mean() > 0.05 else 0.0
    specular = float((hsv[..., 2] > 235).mean())
    return {"observed": hue_spread > 25 or specular > 0.08, "hue_spread": round(hue_spread, 2),
            "specular_fraction": round(specular, 4), "bbox": [x0, y0, x1, y1],
            "note": "A hologram can only be indicated, never authenticated, from a single photo."}


def assess_security_features(bgr: np.ndarray, gray: np.ndarray, template: dict[str, Any] | None,
                             text_boxes: list[list[int]], exclude: list[list[int]]) -> list[dict[str, Any]]:
    if not template:
        return []
    results = []
    for feat in template.get("features", []):
        name, method, region = feat["feature_name"], feat["verification_method"], feat.get("expected_region")
        entry: dict[str, Any] = {"feature_name": name, "verification_method": method, "expected_region": region}
        if method in ("requires_uv_illumination", "requires_magnification"):
            entry.update(status="NOT_VERIFIED", reason=feat.get("note") or "requires equipment beyond a visible-light photo")
        elif method in ("official_chip_reader_required", "official_reader_required"):
            entry.update(status="NOT_VERIFIED", feature_class="ELECTRONIC_COMPONENT",
                         reason="electronic component not read — only an authorised reader may verify it; no adapter configured")
        elif method == "visual_texture_indicator" and region:
            ind = texture_indicator(gray, region, text_boxes)
            entry.update(ind, status="PASS" if ind.get("observed") else "NOT_VERIFIED",
                         reason="fine-line background pattern indicator " + ("observed" if ind.get("observed") else "not observed in this image"))
        elif method == "visual_specular_indicator" and region:
            ind = hologram_indicator(bgr, region)
            entry.update(ind, status="PASS" if ind.get("observed") else "NOT_VERIFIED",
                         reason="hologram-like colour/specular variation " + ("observed" if ind.get("observed") else "not observed (may be lighting-dependent)"))
        elif method == "visual_feature_consistency" and name == "yellow_gold_visual_feature":
            yg = detect_yellow_gold_feature(bgr, region, exclude)
            status = ("NOT_VERIFIED" if not yg["detected"] else
                      "PASS" if yg["template_consistency"] == "PASS" and yg["appearance_consistency"] == "PASS" else
                      "REVIEW_REQUIRED" if yg["template_consistency"] == "REVIEW_REQUIRED" else "NOT_VERIFIED")
            entry.update(status=status, yellow_security_feature=yg,
                         reason=yg.get("reason") or f"yellow/gold visual feature: template {yg['template_consistency']}, appearance {yg['appearance_consistency']}")
        else:
            continue  # photo / QR / MRZ features are verified by their own dedicated checks
        results.append(entry)
    return results
