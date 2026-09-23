"""Photograph location/integrity and face verification.

Photo checks: presence, bbox, position vs the template's expected photo
region, size / aspect ratio, orientation, face count. A photo in an
unexpected place is an evidence signal, never on its own a finding against
the document.

Face verification reuses the existing InsightFace (buffalo_sc / ArcFace-
family) provider, app.services.face.mobilefacenet_provider, including its
quality gating that returns inconclusive instead of a false mismatch.
Embeddings and similarity internals are not returned to the UI — only the
outcome, a rounded similarity and the reason.
"""
from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from app.services.docverify.security_features import compare_position
from app.services.docverify.types import Region, RegionLabel


def _encode(bgr: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", bgr)
    return buf.tobytes() if ok else b""


def assess_photo(bgr: np.ndarray, regions: list[Region], expected_rel: list[float] | None) -> dict[str, Any]:
    h, w = bgr.shape[:2]
    photos = [r for r in regions if r.label == RegionLabel.PHOTOGRAPH]
    result: dict[str, Any] = {
        "photo_present": bool(photos),
        "face_detected": bool(photos),
        "face_count": len(photos),
        "expected_region": expected_rel,
        "signals": [],
    }
    if not photos:
        result["signals"].append({"signal": "photo_missing_or_face_not_detected",
                                  "reason": "no face could be detected on the document"})
        return result
    main = max(photos, key=lambda r: (r.bbox[2] - r.bbox[0]) * (r.bbox[3] - r.bbox[1]))
    # A second, much smaller face is the normal "ghost image" on many ID
    # cards and passports; only comparable-size faces count as "multiple".
    main_area = (main.bbox[2] - main.bbox[0]) * (main.bbox[3] - main.bbox[1])
    comparable = [p for p in photos if (p.bbox[2] - p.bbox[0]) * (p.bbox[3] - p.bbox[1]) > 0.45 * main_area]
    bw, bh = main.bbox[2] - main.bbox[0], main.bbox[3] - main.bbox[1]
    face = main.meta.get("face_bbox", main.bbox)
    result.update({
        "region_id": main.id,
        "bbox": main.bbox,
        "face_bbox": face,
        "relative_position": [round(main.bbox[0] / w, 3), round(main.bbox[1] / h, 3),
                              round(main.bbox[2] / w, 3), round(main.bbox[3] / h, 3)],
        "aspect_ratio": round(bw / max(1, bh), 3),
        "orientation": "upright" if bh >= bw * 0.9 else "rotated_or_landscape",
        "secondary_small_faces": len(photos) - len(comparable),
        "detector": main.source,
    })
    # Two portraits (main photo + a secondary/"ghost" portrait) is a normal
    # layout on passports, visas and ID cards — it is compared, not flagged
    # (see the secondary_portrait check). Three or more comparable faces
    # matches no standard layout.
    others = sorted((p for p in photos if p is not main),
                    key=lambda r: -(r.bbox[2] - r.bbox[0]) * (r.bbox[3] - r.bbox[1]))
    result["secondary_region"] = others[0].bbox if others else None
    result["secondary_face_bbox"] = others[0].meta.get("face_bbox", others[0].bbox) if others else None
    if len(comparable) > 2:
        result["signals"].append({"signal": "multiple_faces",
                                  "reason": f"{len(comparable)} comparable-size faces found on one document"})
    if result["orientation"] != "upright":
        result["signals"].append({"signal": "unexpected_orientation", "reason": "photo region is wider than tall"})
    if expected_rel:
        comp = compare_position(result["relative_position"], expected_rel, centre_tol=0.18, size_range=(0.25, 3.5))
        result["template_comparison"] = comp
        if not comp["position_ok"]:
            result["signals"].append({"signal": "photo_unexpected_location",
                                      "reason": "photo is not where this document's template places it"})
        if not comp["size_ok"]:
            result["signals"].append({"signal": "photo_unexpected_dimensions",
                                      "reason": f"photo size is {comp['size_ratio']}x the template's expected size"})
    return result


def crop(bgr: np.ndarray, bbox: list[int]) -> np.ndarray:
    h, w = bgr.shape[:2]
    return bgr[max(0, bbox[1]):min(h, bbox[3]), max(0, bbox[0]):min(w, bbox[2])]


# Below the match threshold but above what different people score: a
# printed document photo against a live face scores lower than two live
# photos of the same person. 0.25 sits above the 99th percentile (0.19) of
# 151 different-person pairs of real document photos in the project dataset.
POSSIBLE_MATCH_FLOOR = 0.25


def _outcome(res) -> str:
    if res.inconclusive and res.similarity < POSSIBLE_MATCH_FLOOR:
        return "LOW_QUALITY"
    if res.match:
        return "MATCH"
    return "POSSIBLE_MATCH" if res.similarity >= POSSIBLE_MATCH_FLOOR else "NO_MATCH"


def verify_faces(document_photo: np.ndarray | None, presented: bytes | None, reference: bytes | None) -> dict[str, Any]:
    """Document photo <-> presented person <-> authorised reference photo.
    Returns per-pair outcomes MATCH / NO_MATCH / LOW_QUALITY / NOT_VERIFIED."""
    from app.services.face.mobilefacenet_provider import MobileFaceNetProvider

    out: dict[str, Any] = {"pairs": [], "face_detected": document_photo is not None}
    if document_photo is None or document_photo.size == 0:
        out["overall"] = "NOT_VERIFIED"
        out["reason"] = "no document photograph available to compare"
        return out
    if presented is None and reference is None:
        out["overall"] = "NOT_VERIFIED"
        out["reason"] = "no presented-person capture or authorised reference photo was provided"
        return out
    provider = MobileFaceNetProvider()
    doc_bytes = _encode(document_photo)
    for name, other in (("document_vs_presented", presented), ("document_vs_reference", reference)):
        if other is None:
            continue
        res = provider.verify(doc_bytes, other)
        out["pairs"].append({"pair": name, "outcome": _outcome(res), "similarity_score": round(res.similarity, 3),
                             "image_quality": "LOW" if res.quality_issues else "OK",
                             "quality_issues": res.quality_issues[:4],
                             "reason": res.reason.split(" — ")[0][:200]})
    if presented is not None and reference is not None:
        res = provider.verify(reference, presented)
        out["pairs"].append({"pair": "reference_vs_presented", "outcome": _outcome(res),
                             "similarity_score": round(res.similarity, 3),
                             "image_quality": "LOW" if res.quality_issues else "OK",
                             "reason": res.reason.split(" — ")[0][:200]})
    outcomes = {p["outcome"] for p in out["pairs"]}
    out["overall"] = ("NO_MATCH" if "NO_MATCH" in outcomes else "POSSIBLE_MATCH" if "POSSIBLE_MATCH" in outcomes
                      else "LOW_QUALITY" if "LOW_QUALITY" in outcomes
                      else "MATCH" if outcomes == {"MATCH"} else "NOT_VERIFIED")
    main = out["pairs"][0]
    out.update(face_match=out["overall"] == "MATCH", similarity_score=main["similarity_score"],
               image_quality=main["image_quality"], reason=main["reason"])
    return out
