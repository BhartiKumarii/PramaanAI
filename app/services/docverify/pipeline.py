"""Modular document-verification pipeline (orchestration).

    image(s) --> region detection (YOLO11 | classical) --> PP-OCR (page + regions)
             --> MRZ locate/parse/validate --> QR/barcode decode (OpenCV)
             --> document-type identification --> field extraction
             --> photo / face --> layout + security features (incl. yellow/gold)
             --> stamps (+ checkpoint reference, visual reference, forensics)
             --> region-scoped forensics --> digital signatures --> registries
             --> consistency engine --> border rules --> decision engine

`verify_images` is the server-side (web desk) path. `verify_extracted` is the
device path used by the Android app: it receives only extracted data (fields,
MRZ lines, decoded codes, stamp text, region boxes) — never images — and
re-runs every check that doesn't need pixels.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

import cv2
import numpy as np

from app.services.docverify import (border_rules, consistency, decision, doc_type, forensics, reference,
                                    registries, security_features, signatures, vlm)
from app.services.docverify.detection import decode_image, get_region_detector
from app.services.docverify.fields import extract_fields, extract_native_fields, find_dates
from app.services.docverify.machine_readable import detect_and_decode, parse_payload
from app.services.docverify.mrz import describe_failed_check, locate_mrz, parse_mrz
from app.services.docverify.ocr import (
    DEVANAGARI_ENGINE, ENGINE_NAME, devanagari_available, devanagari_lines, mean_confidence, ocr_image, respace_lines,
)
from app.services.docverify.photo import assess_photo, crop, verify_faces
from app.services.docverify.stamps import analyze_stamp, compare_visual_reference, identify_stamp
from app.services.docverify.types import (
    CheckResult, CheckStatus, DocumentAnalysis, DocumentType, DocumentTypeResult, Evidence, FieldValue,
    MachineReadableCode, OcrLine, PASSPORT_TYPES, Region, RegionLabel, VISA_TYPES, VerificationOutcome,
)
from app.services.validation.mrz import MRZFormatError
from app.services.validation.verhoeff import validate_verhoeff

S = CheckStatus

KEY_FIELDS: dict[str, list[str]] = {
    "PASSPORT": ["name", "document_number", "date_of_birth", "date_of_expiry"],
    "VISA": ["visa_number", "date_of_expiry"],
    DocumentType.BHUTAN_ENTRY_PERMIT.value: ["permit_number"],
    DocumentType.DRIVING_LICENCE.value: ["document_number", "name", "date_of_birth"],
    DocumentType.AADHAAR.value: ["aadhaar_number", "name"],
}

INDIAN_STATE_CODES = {
    "AN", "AP", "AR", "AS", "BR", "CG", "CH", "DD", "DL", "DN", "GA", "GJ", "HP", "HR", "JH", "JK", "KA", "KL", "LA",
    "LD", "MH", "ML", "MN", "MP", "MZ", "NL", "OD", "OR", "PB", "PY", "RJ", "SK", "TN", "TR", "TS", "UK", "UA", "UP",
    "WB", "CT", "TG",
}


def _family(dt: DocumentType) -> str:
    if dt in PASSPORT_TYPES:
        return "PASSPORT"
    if dt in VISA_TYPES:
        return "VISA"
    return dt.value


@dataclass
class Ctx:
    on: date
    db: Any = None
    offline: bool = False
    dl_registry: registries.DrivingLicenceRegistry | None = None
    travel_registry: registries.TravelAuthorisationRegistry | None = None
    checks: list[CheckResult] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    # Biometric working state — kept in memory for this request only, never
    # returned in the response or stored (biometric data minimisation).
    doc_face_embeddings: dict[int, Any] = field(default_factory=dict)
    registry_face_embeddings: dict[int, Any] = field(default_factory=dict)
    # Liveness of the live photo as measured on the phone (see LivenessReport).
    liveness: dict[str, Any] | None = None

    def ev(self, check: str, description: str, doc: int | None, bbox: list[int] | None = None,
           region_id: str | None = None, **values: Any) -> str:
        eid = f"ev-{len(self.evidence) + 1}"
        self.evidence.append(Evidence(id=eid, check=check, description=description, bbox=bbox, region_id=region_id,
                                      document_index=doc, values=values))
        return eid

    def add(self, name: str, status: CheckStatus, summary: str, doc: int | None, *, blocking: bool = True,
            strong: bool = False, evidence: list[str] | None = None, **details: Any) -> CheckResult:
        c = CheckResult(name=name, status=status, summary=summary, blocking=blocking, strong_evidence=strong,
                        evidence_ids=evidence or [], details=details, document_index=doc)
        self.checks.append(c)
        return c


# ============================================================ image analysis

def _quality(gray: np.ndarray) -> dict[str, Any]:
    h, w = gray.shape
    small = cv2.resize(gray, (1000, int(1000 * h / w))) if w > 1000 else gray
    sharp = float(cv2.Laplacian(small, cv2.CV_64F).var())
    bright = float(small.mean())
    issues = []
    if min(h, w) < 300:
        issues.append(f"resolution too low ({w}x{h})")
    if sharp < 25:
        issues.append(f"image is blurred (sharpness {sharp:.0f})")
    if bright < 45:
        issues.append("image is too dark")
    clipped = float((small >= 250).mean())
    if clipped > 0.35:  # white paper is legitimately bright; only clipped highlights count
        issues.append(f"image is overexposed ({clipped:.0%} of pixels clipped)")
    glare = _glare_fraction(small)
    if glare >= 0.004:
        issues.append(f"glare/reflection covers about {glare:.1%} of the image — tilt the document and retake")
    level = "POOR" if (sharp < 12 or min(h, w) < 250 or bright < 30) else "MARGINAL" if issues else "GOOD"
    return {"level": level, "sharpness": round(sharp, 1), "brightness": round(bright, 1),
            "glare_fraction": round(glare, 4), "resolution": [w, h], "issues": issues}


def _glare_fraction(gray: np.ndarray) -> float:
    """Specular highlights: clipped (>=250) blobs noticeably brighter than
    their immediate surroundings. Evenly white paper is not glare."""
    clipped = (gray >= 250).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(clipped)
    total = gray.size
    glare = 0
    for k in range(1, n):
        x, y, w, h, area = stats[k]
        if area < 0.0005 * total or area > 0.2 * total:
            continue
        ring = gray[max(0, y - 12):y + h + 12, max(0, x - 12):x + w + 12]
        ring_mask = labels[max(0, y - 12):y + h + 12, max(0, x - 12):x + w + 12] != k
        if ring_mask.any() and float(ring[ring_mask].mean()) < 215:
            glare += area
    return glare / total


def _best_orientation(rgb: np.ndarray, lines: list[OcrLine]) -> tuple[int, list[OcrLine]]:
    """A document photographed sideways or upside down reads poorly; when
    the first OCR pass finds little text, try the other orientations and keep
    the one PP-OCR reads best (sum of line confidences)."""
    best_rot, best_lines = 0, lines
    best_score = sum(l.confidence for l in lines)
    for rot, code in ((90, cv2.ROTATE_90_CLOCKWISE), (180, cv2.ROTATE_180), (270, cv2.ROTATE_90_COUNTERCLOCKWISE)):
        cand = ocr_image(cv2.rotate(rgb, code))
        score = sum(l.confidence for l in cand)
        cand_tall = sum(1 for l in cand if (l.bbox[3] - l.bbox[1]) > 1.5 * (l.bbox[2] - l.bbox[0]))
        if (score > best_score * 1.3 or (cand_tall < 0.2 * max(1, len(cand)) and score >= best_score * 0.9)) \
                and len(cand) >= 4 and score >= best_score:
            best_rot, best_lines, best_score = rot, cand, score
    return best_rot, best_lines


_NEPAL_MARKERS = ("नेपाल", "अञ्चल", "गाउँपालिका", "नगरपालिका")


def _classify_devanagari(native: list[OcrLine]) -> DocumentTypeResult | None:
    """Fallback for documents printed only in Devanagari, which the Latin
    classifier cannot read. Used only when that classifier is uncertain."""
    text = " ".join(l.text for l in native)
    nepal = any(m in text for m in _NEPAL_MARKERS)
    if nepal and ("नागरिकता" in text or "ना.प्र" in text or "जिल्ला प्रशासन कार्यालय" in text):
        return DocumentTypeResult(document_type=DocumentType.IDENTITY_DOCUMENT, country="NEPAL", confidence=0.6,
                                  basis=["Devanagari text: Nepal citizenship certificate wording"])
    if "अनुमति" in text:
        return DocumentTypeResult(document_type=DocumentType.OTHER_TRAVEL_DOCUMENT, country="NEPAL" if nepal else None,
                                  confidence=0.55, basis=["Devanagari text: permit (अनुमति-पत्र) wording"])
    return None


def analyze_image(image_bytes: bytes, index: int, *, on: date, expected_type: DocumentType | None = None,
                  raw_codes: dict[str, str] | None = None, prelocated: list[Region] | None = None,
                  quality_override: dict[str, Any] | None = None) -> tuple[DocumentAnalysis, np.ndarray, np.ndarray]:
    bgr, rgb = decode_image(image_bytes, max_side=4000 if prelocated is not None else 1800)
    low: list[OcrLine] = []
    lines = ocr_image(rgb, low_out=low)
    rotation = 0
    # Sideways/upside-down capture: most text boxes are taller than wide, or
    # very little text reads at all.
    tall = sum(1 for l in lines if (l.bbox[3] - l.bbox[1]) > 1.5 * (l.bbox[2] - l.bbox[0]))
    if prelocated is None and (len(lines) < 6 or mean_confidence(lines) < 0.6 or tall > 0.5 * len(lines)):
        rotation, lines = _best_orientation(rgb, lines)
        if rotation:
            code = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}[rotation]
            rgb = np.ascontiguousarray(cv2.rotate(rgb, code))
            bgr = np.ascontiguousarray(cv2.rotate(bgr, code))
            low = []  # boxes of the unrotated pass no longer apply
    lines = respace_lines(rgb, lines)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    code_regions, codes = detect_and_decode(bgr, id_prefix=f"d{index}-code", raw_out=raw_codes)

    mrz_info = None
    mrz_region: list[Region] = []
    located = locate_mrz(lines)
    if located:
        mrz_lines, mrz_bbox = located
        mrz_conf = mean_confidence([l for l in lines if l.bbox[1] >= mrz_bbox[1] - 2 and l.bbox[3] <= mrz_bbox[3] + 2])
        try:
            mrz_info = parse_mrz(mrz_lines)
        except MRZFormatError as exc:
            mrz_info = {"format_error": str(exc)}
        mrz_info.update(bbox=mrz_bbox, ocr_confidence=mrz_conf, line_count=len(mrz_lines))
        mrz_region = [Region(id=f"d{index}-mrz", label=RegionLabel.MRZ, bbox=mrz_bbox, confidence=mrz_conf,
                             source="classical:ocr-line-geometry")]

    text = "\n".join(l.text for l in lines)
    prelim = doc_type.classify(text, mrz_info if mrz_info and "format_error" not in mrz_info else None,
                               code_regions + mrz_region)
    fam = _family(prelim.document_type)
    want_stamps = fam in ("PASSPORT", "VISA") or prelim.document_type in (
        DocumentType.IMMIGRATION_STAMP, DocumentType.DOCUMENT_TYPE_UNCERTAIN, DocumentType.BHUTAN_ENTRY_PERMIT,
        DocumentType.OTHER_TRAVEL_DOCUMENT)
    if prelocated is not None:
        # Regions were located on the device (YOLO11n); the server only
        # received those crops. Keep code/MRZ regions found server-side and
        # add the device's other regions.
        own = {RegionLabel.QR_CODE, RegionLabel.BARCODE, RegionLabel.MRZ}
        # The canvas rebuilt from crops has hard crop edges on a blank
        # background that the classical QR locator can mistake for finder
        # patterns. Here the device detector is the region authority: a code
        # the server located but could not decode only counts where the
        # device also found a QR/barcode (measured: phantom QRs on 5/39
        # replayed phone captures — scripts/docverify/device_path_eval.py).
        device_codes = [r.bbox for r in prelocated if r.label in (RegionLabel.QR_CODE, RegionLabel.BARCODE)]
        phantom = {r.id for r in code_regions
                   if not r.meta.get("decoded") and not any(_overlap(r.bbox, b) > 0.3 for b in device_codes)}
        if phantom:
            code_regions = [r for r in code_regions if r.id not in phantom]
            codes[:] = [c for c in codes if c.region_id not in phantom]
        regions = code_regions + mrz_region + [r for r in prelocated if r.label not in own or not any(
            o.label == r.label for o in code_regions + mrz_region)]
        regions = _attach_faces(bgr, regions)
    else:
        detector = get_region_detector()
        regions = code_regions + mrz_region + [
            r.model_copy(update={"id": f"d{index}-{r.id}"}) for r in detector.detect(bgr, lines, want_stamps=want_stamps)]
        regions = _decode_codes_in_regions(bgr, regions, codes, index, raw_codes)
    regions = _dedupe_regions(regions)

    stamps = []
    for r in [r for r in regions if r.label == RegionLabel.STAMP]:
        # A "stamp" candidate that is really the MRZ, QR or photo is skipped.
        if any(_overlap(r.bbox, o.bbox) > 0.5 for o in regions if o.label in (RegionLabel.MRZ, RegionLabel.QR_CODE)):
            continue
        res = analyze_stamp(rgb, r, lines)
        if res is not None:
            stamps.append(res)
    kept = {s.region_id for s in stamps}
    regions = [r for r in regions if r.label != RegionLabel.STAMP or r.id in kept]

    identified = sum(1 for s in stamps if s.identification != "UNIDENTIFIED")
    dtr = doc_type.classify(text, mrz_info if mrz_info and "format_error" not in mrz_info else None, regions,
                            identified_stamps=identified if prelim.document_type in (
                                DocumentType.DOCUMENT_TYPE_UNCERTAIN, DocumentType.IMMIGRATION_STAMP) else 0)
    if dtr.document_type == DocumentType.DOCUMENT_TYPE_UNCERTAIN and prelim.document_type != DocumentType.DOCUMENT_TYPE_UNCERTAIN:
        dtr = prelim
    fields = extract_fields(lines, dtr.document_type)
    # Nepali/Hindi text: a separate Devanagari pass. Skipped when a valid MRZ
    # was read (passport/visa data then comes from the MRZ and Latin text).
    native = devanagari_lines(rgb, lines, low) if not (mrz_info and "format_error" not in mrz_info) else []
    for key, value in extract_native_fields(native).items():
        fields.setdefault(key, value)
    if native and dtr.document_type == DocumentType.DOCUMENT_TYPE_UNCERTAIN:
        dtr = _classify_devanagari(native) or dtr

    from app.services.docverify import electronic
    e_form = electronic.detect(text + "\n" + "\n".join(l.text for l in native), dtr.document_type)

    doc = DocumentAnalysis(
        document_index=index, image_sha256=hashlib.sha256(image_bytes).hexdigest(),
        image_size=[bgr.shape[1], bgr.shape[0]], document_type=dtr, regions=regions, ocr_lines=lines,
        ocr_confidence=mean_confidence(lines), native_lines=native, electronic=e_form, fields=fields, mrz=mrz_info, codes=codes, stamps=stamps,
        quality=quality_override or _quality(gray),
    )
    if rotation:
        doc.quality = {**(doc.quality or {}), "rotation_corrected_degrees": rotation}
    if expected_type and expected_type != dtr.document_type:
        doc.document_type.basis.append(f"submitted as {expected_type.value}")
    return doc, bgr, rgb


def _dedupe_regions(regions: list[Region]) -> list[Region]:
    """One region per object: when a detector box and a decoder/OCR box of the
    same kind overlap, keep the earlier one (decoded QR / OCR-read MRZ come
    first and carry more information)."""
    kept: list[Region] = []
    for r in regions:
        if any(k.label == r.label and (_overlap(r.bbox, k.bbox) > 0.5 or _overlap(k.bbox, r.bbox) > 0.5) for k in kept):
            continue
        kept.append(r)
    return kept


def _attach_faces(bgr: np.ndarray, regions: list[Region]) -> list[Region]:
    """Face boxes inside detector-provided photograph regions (face checks need the face, not the whole photo)."""
    from app.services.docverify.detection import detect_faces
    out = []
    for r in regions:
        if r.label == RegionLabel.PHOTOGRAPH and "face_bbox" not in r.meta:
            x0, y0, x1, y1 = (max(0, v) for v in r.bbox)
            faces = detect_faces(bgr[y0:y1, x0:x1]) if x1 > x0 and y1 > y0 else []
            if faces:
                fb = max(faces, key=lambda f: f[1])[0]
                r = r.model_copy(update={"meta": {**r.meta, "face_bbox": [fb[0] + x0, fb[1] + y0, fb[2] + x0, fb[3] + y0]}})
            else:
                r = r.model_copy(update={"meta": {**r.meta, "face_found": False}})
        out.append(r)
    return out


def _decode_codes_in_regions(bgr: np.ndarray, regions: list[Region], codes: list[MachineReadableCode], index: int,
                             raw_codes: dict[str, str] | None) -> list[Region]:
    """A detector-located QR/barcode that the whole-page decoder missed is
    decoded again from an upscaled crop of just that region."""
    decoded_boxes = [r.bbox for r in regions if r.meta.get("decoded")]
    extra: list[Region] = []
    for r in regions:
        if r.label not in (RegionLabel.QR_CODE, RegionLabel.BARCODE) or r.meta.get("decoded") is not None:
            continue
        if any(_overlap(r.bbox, b) > 0.5 for b in decoded_boxes):
            continue
        h, w = bgr.shape[:2]
        pad = int(0.15 * max(r.bbox[2] - r.bbox[0], r.bbox[3] - r.bbox[1]))
        x0, y0, x1, y1 = max(0, r.bbox[0] - pad), max(0, r.bbox[1] - pad), min(w, r.bbox[2] + pad), min(h, r.bbox[3] + pad)
        crop = cv2.resize(bgr[y0:y1, x0:x1], None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        sub_raw: dict[str, str] = {}
        sub_regions, sub_codes = detect_and_decode(crop, id_prefix=f"d{index}-rcode", raw_out=sub_raw)
        for sr, sc in zip(sub_regions, sub_codes):
            if not sc.decoded:
                continue
            new_id = f"{sr.id}-{len(extra)}"
            bbox = [int(x0 + sr.bbox[0] / 3), int(y0 + sr.bbox[1] / 3), int(x0 + sr.bbox[2] / 3), int(y0 + sr.bbox[3] / 3)]
            extra.append(sr.model_copy(update={"id": new_id, "bbox": bbox, "source": f"{r.source}+{sr.source}:crop"}))
            codes.append(sc.model_copy(update={"region_id": new_id}))
            if raw_codes is not None and sr.id in sub_raw:
                raw_codes[new_id] = sub_raw[sr.id]
        if not any(_overlap(e.bbox, r.bbox) > 0.3 for e in extra):
            # Located by the detector but not decodable: reported as present
            # and UNREADABLE — never dropped, never guessed.
            codes.append(MachineReadableCode(region_id=r.id, symbology=r.label.value, decoded=False,
                                             payload_kind="UNREADABLE"))
    return [r for r in regions if not (r.label in (RegionLabel.QR_CODE, RegionLabel.BARCODE)
                                       and any(_overlap(r.bbox, e.bbox) > 0.5 for e in extra))] + extra


def _overlap(inner: list[int], outer: list[int]) -> float:
    ix0, iy0, ix1, iy1 = max(inner[0], outer[0]), max(inner[1], outer[1]), min(inner[2], outer[2]), min(inner[3], outer[3])
    return max(0, ix1 - ix0) * max(0, iy1 - iy0) / max(1, (inner[2] - inner[0]) * (inner[3] - inner[1]))


# ============================================================ per-document checks

def _template(doc: DocumentAnalysis, on: date) -> dict[str, Any] | None:
    versions = reference.template_versions(doc.document_type.document_type.value, doc.document_type.country, on)
    return versions[0] if versions else None


def _image_checks(ctx: Ctx, doc: DocumentAnalysis, bgr: np.ndarray, rgb: np.ndarray, image_bytes: bytes,
                  live_face: bytes | None, reference_face: bytes | None, raw_codes: dict[str, str]) -> None:
    i = doc.document_index
    dt = doc.document_type.document_type
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    # --- layout
    extra = {}
    layout = security_features.layout_consistency(dt.value, doc.document_type.country, doc.regions, bgr.shape, ctx.on)
    tmpl = None
    if layout.get("template_version"):
        tmpl = next((v for v in reference.template_versions(dt.value, doc.document_type.country, ctx.on)
                     if v["version"] == layout["template_version"]), None)
        doc.template_version = layout["template_version"]
    # --- security features (incl. yellow/gold visual feature) + re-score layout with it
    excl = [r.bbox for r in doc.regions if r.label in (RegionLabel.PHOTOGRAPH, RegionLabel.QR_CODE)]
    feats = security_features.assess_security_features(bgr, gray, tmpl, [l.bbox for l in doc.ocr_lines], excl)
    doc.security_features = feats
    yg = next((f for f in feats if f["feature_name"] == "yellow_gold_visual_feature"), None)
    if yg and yg.get("yellow_security_feature", {}).get("detected"):
        feat = yg["yellow_security_feature"]
        extra["YELLOW_GOLD_FEATURE"] = feat["bbox_xyxy"]
        # the detector may already have located the same feature
        doc.regions = [r for r in doc.regions if not (r.label == RegionLabel.SECURITY_FEATURE and
                                                      _overlap(r.bbox, feat["bbox_xyxy"]) > 0.5)]
        doc.regions.append(Region(id=f"d{i}-yellow-gold", label=RegionLabel.SECURITY_FEATURE, bbox=feat["bbox_xyxy"],
                                  confidence=feat["confidence"], source="classical:colour-shape-consistency",
                                  meta={"detector_label": "YELLOW_GOLD_FEATURE", "feature_type": "VISUAL_SECURITY_FEATURE"}))
        layout = security_features.layout_consistency(dt.value, doc.document_type.country, doc.regions, bgr.shape,
                                                      ctx.on, extra_anchors=extra)
    if layout["status"] == "REFERENCE_NOT_AVAILABLE":
        ctx.add("layout", S.REFERENCE_NOT_AVAILABLE, layout["reason"], i, blocking=False)
    else:
        eids = [ctx.ev("layout", f"{k.lower().replace('_', ' ')}: {'consistent' if c['position_ok'] and c['size_ok'] else 'not where expected'}",
                       i, bbox=c["bbox"], expected_region=c["expected_region"])
                for k, c in layout["anchors"].items() if c.get("detected", True) and "bbox" in c]
        ctx.add("layout", S(layout["status"]), layout["reason"].capitalize(), i, blocking=False, evidence=eids,
                template_version=layout.get("template_version"), score=layout.get("score"),
                aspect_ratio=layout.get("aspect_ratio"))
    if feats:
        visual = [f for f in feats if f["feature_name"] not in ("yellow_gold_visual_feature",)]
        observed = [f["feature_name"].replace("_", " ") for f in visual if f["status"] == "PASS"]
        unverifiable = [f["feature_name"].replace("_", " ") for f in visual if f["status"] == "NOT_VERIFIED"]
        eids = [ctx.ev("security_features", f"{f['feature_name'].replace('_', ' ')}: {f['reason']}", i, bbox=f.get("bbox"))
                for f in visual if f.get("bbox")]
        ctx.add("security_features", S.PASS if observed and len(observed) >= len([f for f in visual if f.get("expected_region")]) else S.NOT_VERIFIED,
                (f"Observed: {', '.join(observed)}. " if observed else "") +
                (f"Not verifiable from this photo: {', '.join(unverifiable)}." if unverifiable else ""),
                i, blocking=False, evidence=eids, features=visual)
    if yg:
        f = yg.get("yellow_security_feature", {})
        eids = [ctx.ev("yellow_gold_feature", "yellow/gold visual security feature", i, bbox=f.get("bbox_xyxy"),
                       region_id=f"d{i}-yellow-gold")] if f.get("detected") else []
        ctx.add("yellow_gold_feature", S(yg["status"]), yg["reason"].capitalize(), i, blocking=False, evidence=eids,
                yellow_security_feature={k: v for k, v in f.items() if k != "bbox_xyxy"})

    # --- photo integrity
    exp_photo = (tmpl or {}).get("layout_anchors", {}).get("PHOTOGRAPH")
    # Photo expectation comes from the document's own template (e.g. Nepal
    # visa stickers carry no photo); ID documents without a template are
    # still expected to carry one.
    photo_expected = bool(exp_photo) or (tmpl is None and dt in (
        DocumentType.IDENTITY_DOCUMENT, DocumentType.VOTER_ID, DocumentType.DRIVING_LICENCE))
    ph = assess_photo(bgr, doc.regions, exp_photo)
    doc.photo = {k: v for k, v in ph.items()}
    if photo_expected:
        photo_regions = [r for r in doc.regions if r.label == RegionLabel.PHOTOGRAPH]
        if not photo_regions and exp_photo and (doc.quality or {}).get("level") != "POOR":
            ctx.add("photo", S.REVIEW_REQUIRED, "No photograph where this document's template places one — "
                    "check the document in person", i, flags=["photo_missing"],
                    evidence=[ctx.ev("photo", "expected photo region (empty)", i, bbox=_abs(exp_photo, bgr.shape))])
        elif not ph["face_detected"]:
            ctx.add("photo", S.NOT_VERIFIED, "No face could be detected on the document photo", i,
                    evidence=[ctx.ev("photo", "expected photo region", i, bbox=_abs(exp_photo, bgr.shape))] if exp_photo else [])
        elif ph["signals"]:
            eid = ctx.ev("photo", "; ".join(s["reason"] for s in ph["signals"]), i, bbox=ph["bbox"], region_id=ph["region_id"])
            ctx.add("photo", S.REVIEW_REQUIRED, "; ".join(s["reason"] for s in ph["signals"]).capitalize(), i,
                    evidence=[eid], signals=[s["signal"] for s in ph["signals"]])
        else:
            ctx.add("photo", S.PASS, "Photo present" + (" with a secondary portrait" if ph.get("secondary_region") else "") +
                    ", position consistent with template", i,
                    evidence=[ctx.ev("photo", "document photograph", i, bbox=ph["bbox"], region_id=ph["region_id"])])

    if ph.get("face_detected"):
        _document_face_quality(ctx, doc, bgr, ph)
    if ph.get("secondary_face_bbox"):
        _secondary_portrait(ctx, doc, bgr, ph)

    # --- face verification (only when a live capture / authorised reference is provided)
    if live_face:
        live_ok = _live_capture_checks(ctx, i, live_face)
        if not live_ok:
            live_face = None  # retake needed — never compared against a bad capture
    if live_face or reference_face:
        doc_face = crop(bgr, ph["bbox"]) if ph.get("bbox") else None
        fv = verify_faces(doc_face, live_face, reference_face)
        doc.photo["face_verification"] = {k: v for k, v in fv.items() if k != "pairs"} | {
            "pairs": [{k: p[k] for k in ("pair", "outcome", "similarity_score", "image_quality", "reason")} for p in fv["pairs"]]}
        status = {"MATCH": S.PASS, "NO_MATCH": S.REVIEW_REQUIRED, "POSSIBLE_MATCH": S.REVIEW_REQUIRED,
                  "LOW_QUALITY": S.NOT_VERIFIED}.get(fv["overall"], S.NOT_VERIFIED)
        summary = {"MATCH": "Face on the document matches the person presented",
                   "NO_MATCH": "Face on the document does not match the person presented — compare in person",
                   "POSSIBLE_MATCH": f"Possible match (similarity {fv.get('similarity_score')}) — below the automatic "
                                     "match level; confirm by comparing the face in person",
                   "LOW_QUALITY": "Face comparison not possible — no clear face found in one of the images; "
                                  "retake the live photo or compare in person"}.get(fv["overall"], fv.get("reason", "Face not verified"))
        ctx.add("face_verification", status, summary, i, strong=fv["overall"] == "NO_MATCH",
                evidence=[ctx.ev("face_verification", summary, i, bbox=ph.get("bbox"))] if ph.get("bbox") else [],
                face_detected=fv.get("face_detected"), face_match=fv.get("face_match"),
                similarity_score=fv.get("similarity_score"), image_quality=fv.get("image_quality"))

    if live_face:
        _liveness_check(ctx, i)

    # --- region-scoped forensics
    maps = forensics.ForensicMaps(rgb)
    targets: list[tuple[str, str, list[int]]] = []
    for r in doc.regions:
        if r.label in (RegionLabel.PHOTOGRAPH, RegionLabel.STAMP, RegionLabel.QR_CODE, RegionLabel.SECURITY_FEATURE):
            targets.append((r.id, r.label.value, r.bbox))
    for key in ("name", "date_of_birth", "document_number", "date_of_expiry", "visa_number", "passport_number"):
        fv_ = doc.fields.get(key)
        if fv_ and fv_.bbox:
            targets.append((f"d{i}-text-{key}", f"TEXT:{key}", fv_.bbox))
    text_targets = [t for t in targets if t[1].startswith("TEXT")]
    region_results = [forensics.analyze_region(maps, rid, label, bbox) for rid, label, bbox in targets
                      if not label.startswith("TEXT")] + forensics.analyze_text_peers(maps, text_targets)
    dups = forensics.find_duplicates(maps.gray, [(rid, bbox) for rid, label, bbox in targets
                                                 if label in ("STAMP", "PHOTOGRAPH", "SECURITY_FEATURE")])
    meta = forensics.metadata_indicators(image_bytes)
    summary = forensics.summarize(region_results, dups, meta)
    doc.tampering = {k: v for k, v in summary.items() if k != "regions"} | {
        "region_measures": [{"region_id": r["region_id"], "region_label": r["region_label"], "consensus": r["consensus"],
                             "measures": r["measures"]} for r in summary["regions"]]}
    stamp_ids = {s.region_id for s in doc.stamps}
    stamp_flags = [r for r in summary["flagged_regions"] if r["region_id"] in stamp_ids]
    other_flags = [r for r in summary["flagged_regions"] if r["region_id"] not in stamp_ids]
    for s in doc.stamps:
        s.forensic_indicators = [ {"indicator": ind["indicator"], "reason": ind["reason"]}
                                  for r in summary["regions"] if r["region_id"] == s.region_id for ind in r["indicators"]]
    if doc.stamps:
        if stamp_flags:
            eids = [ctx.ev("stamp_forensics", "; ".join(r["reasons"]), i, bbox=r["bbox"], region_id=r["region_id"],
                           methods=r["methods"]) for r in stamp_flags]
            ctx.add("stamp_forensics", S.REVIEW_REQUIRED,
                    "Possible image inconsistency around the stamp — " + "; ".join(stamp_flags[0]["reasons"]), i,
                    evidence=eids, flags=["possible_stamp_compositing"])
        else:
            ctx.add("stamp_forensics", S.PASS, "No manipulation indicators agree around the stamp(s)", i)
    if other_flags or meta:
        eids = [ctx.ev("tampering_analysis", f"{r['region_label'].replace('TEXT:', 'text: ').lower()}: {'; '.join(r['reasons'])}",
                       i, bbox=r["bbox"], region_id=r["region_id"], methods=r["methods"]) for r in other_flags]
        where = ", ".join(sorted({r["region_label"].replace("TEXT:", "").replace("_", " ").lower() for r in other_flags}))
        text = (f"Possible image manipulation in: {where}" if other_flags else "") + \
               ("; " if other_flags and meta else "") + ("; ".join(m["reason"] for m in meta))
        flags = ["possible_photo_replacement" if any(r["region_label"] == "PHOTOGRAPH" for r in other_flags) else None,
                 "possible_text_manipulation" if any(r["region_label"].startswith("TEXT") for r in other_flags) else None,
                 "editing_software_metadata" if meta else None]
        ctx.add("tampering_analysis", S.REVIEW_REQUIRED, text, i, blocking=bool(other_flags), evidence=eids,
                tampering_detected=summary["tampering_detected"], confidence=summary["confidence"],
                indicators=summary["indicators"], flags=[f for f in flags if f])
    else:
        weak = len(summary["weak_indicators"])
        ctx.add("tampering_analysis", S.PASS,
                "No strong tampering indicator" + (f" ({weak} single-method weak indicator(s) not corroborated)" if weak else ""),
                i, tampering_detected=False, indicators=[])

    # --- digital signatures (image path: signed codes + visual signature)
    has_visual_sig = any(r.label == RegionLabel.SIGNATURE for r in doc.regions)
    _signature_checks(ctx, doc, signatures.assess(doc.codes, raw_codes, has_visual_sig, ctx.on))


def _document_face_quality(ctx: Ctx, doc: DocumentAnalysis, bgr: np.ndarray, ph: dict[str, Any]) -> None:
    """Face detected in the document photo: size, sharpness, contrast and the
    five facial landmarks (eyes, nose, mouth corners). Keeps the embedding
    in memory for registry reference-photo comparison."""
    from app.services.face.mobilefacenet_provider import _get_insightface_app
    from app.services.face.quality import assess_quality

    i = doc.document_index
    region = crop(bgr, ph["bbox"])
    if region.size == 0:
        return
    app = _get_insightface_app()
    faces = app.get(cv2.copyMakeBorder(region, 32, 32, 32, 32, cv2.BORDER_CONSTANT, value=(255, 255, 255))) if app else []
    if not faces:
        ctx.add("document_face_quality", S.NOT_VERIFIED, "Face landmarks could not be located in the document photo", i,
                blocking=False)
        return
    best = max(faces, key=lambda f: f.det_score)
    x0, y0, x1, y1 = (int(v) for v in best.bbox)
    size = min(x1 - x0, y1 - y0)
    landmarks = best.kps is not None and len(best.kps) == 5
    ctx.doc_face_embeddings[i] = best.normed_embedding
    ok, buf = cv2.imencode(".png", region)
    q = assess_quality(buf.tobytes()) if ok else None
    issues = list(q.issues) if q else []
    if size < 40:
        issues.append(f"face is only {size}px across")
    if not landmarks:
        issues.append("eyes/nose/mouth landmarks not all located")
    ctx.add("document_face_quality", S.PASS if not issues else S.REVIEW_REQUIRED,
            "Document photo face is clear, large enough and has visible eyes, nose and mouth" if not issues
            else "Document photo quality: " + "; ".join(issues[:3]), i, blocking=False,
            detection_score=round(float(best.det_score), 3), face_px=size, landmarks_visible=landmarks)


def _secondary_portrait(ctx: Ctx, doc: DocumentAnalysis, bgr: np.ndarray, ph: dict[str, Any]) -> None:
    """Main photo vs the secondary ("ghost") portrait printed on the same
    document. A match is a passed consistency check; a clear mismatch between
    two good-quality faces is worth the officer's attention (replacing the
    main photo usually leaves the ghost image unchanged). Faint or small
    ghost images are "not assessable", never a finding."""
    i = doc.document_index
    main_crop, other_crop = crop(bgr, ph["face_bbox"]), crop(bgr, ph["secondary_face_bbox"])
    ok, buf = cv2.imencode(".png", other_crop)
    if not ok or min(other_crop.shape[:2]) < 24:
        ctx.add("secondary_portrait", S.NOT_VERIFIED, "Second portrait present (normal for this layout); "
                "too small to compare with the main photo", i, blocking=False,
                evidence=[ctx.ev("secondary_portrait", "secondary portrait", i, bbox=ph["secondary_region"])])
        return
    fv = verify_faces(main_crop, buf.tobytes(), None)
    eids = [ctx.ev("secondary_portrait", "main photo", i, bbox=ph["bbox"]),
            ctx.ev("secondary_portrait", "secondary portrait", i, bbox=ph["secondary_region"])]
    if fv["overall"] == "MATCH":
        ctx.add("secondary_portrait", S.PASS, "Second portrait on the document matches the main photo", i,
                blocking=False, evidence=eids, similarity_score=fv.get("similarity_score"))
    elif fv["overall"] == "NO_MATCH":
        ctx.add("secondary_portrait", S.REVIEW_REQUIRED, "The two portraits on the document do not appear to be "
                "the same person — compare them in person", i, evidence=eids,
                similarity_score=fv.get("similarity_score"))
    else:
        ctx.add("secondary_portrait", S.NOT_VERIFIED, "Second portrait present (normal for this layout); "
                "not clear enough to compare with the main photo", i, blocking=False, evidence=eids)


# Anti-spoof "real" probability below which the live photo is flagged for the
# officer. MiniFASNet-V2 is uncalibrated on field captures; the check is
# advisory until it is (Documentation/DOCUMENT_VERIFICATION.md, Liveness).
PASSIVE_LIVENESS_REVIEW_BELOW = 0.5


def _liveness_check(ctx: Ctx, i: int) -> None:
    lv = ctx.liveness
    if lv is None:
        ctx.add("liveness", S.NOT_VERIFIED, "Liveness not checked for this live photo", i, blocking=False)
        return
    if lv.get("source") == "gallery":
        ctx.add("liveness", S.NOT_VERIFIED, "Live photo chosen from the gallery — liveness not checked; "
                "compare the traveller in person", i, blocking=False, **lv)
        return
    score = lv.get("passive_score")
    passive_low = score is not None and score < PASSIVE_LIVENESS_REVIEW_BELOW
    score_txt = f" (anti-spoof score {score:.2f})" if score is not None else ""
    if lv.get("active") == "PASSED" and not passive_low:
        ctx.add("liveness", S.PASS, "Live person on camera: blink and head-turn prompts completed" + score_txt, i,
                blocking=False, **lv)
    elif passive_low:
        ctx.add("liveness", S.REVIEW_REQUIRED, "Possible photo or screen shown to the camera" + score_txt
                + " — confirm the traveller is present in person", i, blocking=False, **lv)
    else:
        ctx.add("liveness", S.REVIEW_REQUIRED, "Liveness prompts (blink, head turn) not completed" + score_txt
                + " — confirm the traveller is present in person", i, blocking=False, **lv)


def _live_capture_checks(ctx: Ctx, i: int, live: bytes) -> bool:
    """The presented-person capture must show exactly one clear face;
    otherwise the officer is asked to retake it (never a mismatch). Also
    runs the existing face-manipulation heuristics as an advisory signal."""
    from app.services.deepfake.advanced_provider import AdvancedDeepfakeProvider
    from app.services.docverify.detection import decode_image, detect_faces

    lbgr, _ = decode_image(live)
    faces = [f for f in detect_faces(lbgr) if f[1] >= 0.5]
    if len(faces) != 1:
        ctx.add("face_verification", S.NOT_VERIFIED,
                ("More than one face in the live capture — retake with only the traveller in frame" if faces
                 else "No face found in the live capture — retake facing the camera"), i,
                live_faces=len(faces), flags=["retake_live_capture"])
        return False
    from app.core.config import get_settings
    if not get_settings().pramaan_mediapipe:
        # Liveness (blink/turn prompts + on-device anti-spoof) is reported by
        # the phone; the MediaPipe heuristic is not loaded on this instance.
        return True
    try:
        df = AdvancedDeepfakeProvider().analyze(live)
    except Exception:
        df = None
    if df is not None and df.score is not None:
        suspicious = df.score >= 0.6
        ctx.add("face_manipulation_indicators", S.REVIEW_REQUIRED if suspicious else S.PASS,
                (f"Live capture shows signs of a screen/print/synthetic face (heuristic score {df.score:.2f}) — check in person"
                 if suspicious else "No synthetic or replayed-face indicators in the live capture"), i, blocking=False,
                score=round(float(df.score), 3))
    return True


def _abs(rel: list[float] | None, shape: tuple[int, ...]) -> list[int] | None:
    if not rel:
        return None
    h, w = shape[:2]
    return [int(rel[0] * w), int(rel[1] * h), int(rel[2] * w), int(rel[3] * h)]


def _signature_checks(ctx: Ctx, doc: DocumentAnalysis, sig: dict[str, Any]) -> None:
    i = doc.document_index
    doc.security_features.append({"feature_name": "digital_signature_summary", **{k: v for k, v in sig.items()}})
    crypto = [s for s in sig["items"] if s["signature_kind"] == "CRYPTOGRAPHIC"]
    for s in crypto:
        region = next((r.bbox for r in doc.regions if r.id == s.get("region_id")), None)
        eid = ctx.ev("digital_signature", s["reason"], i, bbox=region, region_id=s.get("region_id"),
                     certificate_status=s["certificate_status"], document_integrity=s["document_integrity"])
        ctx.add("digital_signature", S(s["status"]), s["reason"].capitalize(), i,
                blocking=s["status"] in ("FAIL", "PASS", "REVIEW_REQUIRED"), strong=s["status"] == "FAIL",
                evidence=[eid], digital_signature_present=True,
                cryptographic_signature_verified=s["cryptographic_signature_verified"],
                certificate_status=s["certificate_status"], document_integrity=s["document_integrity"])
        if s.get("signed_fields"):
            # Signed data is authoritative for comparison with printed text.
            doc.codes = [c.model_copy(update={"fields": {**c.fields, "_signature_verified": str(s["cryptographic_signature_verified"])}})
                         if c.region_id == s.get("region_id") else c for c in doc.codes]
    visual = [s for s in sig["items"] if s["signature_kind"] == "VISUAL_SIGNATURE"]
    if visual and not crypto:
        ctx.add("digital_signature", S.NOT_APPLICABLE, visual[0]["reason"].capitalize(), i, blocking=False,
                digital_signature_present=False, cryptographic_signature_verified=False)


_EXPECTED_ASPECT = {"PASSPORT": 1.42, "VISA": 1.42, DocumentType.DRIVING_LICENCE.value: 1.586,
                    DocumentType.AADHAAR.value: 1.586, DocumentType.IDENTITY_DOCUMENT.value: 1.586}
OCR_CONFIDENCE_THRESHOLD = 0.75


def _capture_checks(ctx: Ctx, doc: DocumentAnalysis) -> None:
    """Document detected, fully in frame, plausible proportions, OCR
    confidence, and ICAO-valid MRZ country codes."""
    i = doc.document_index
    fam = _family(doc.document_type.document_type)
    docs = [r for r in doc.regions if r.label == RegionLabel.DOCUMENT]
    if doc.image_size and docs:
        w, h = doc.image_size
        box = max(docs, key=lambda r: (r.bbox[2] - r.bbox[0]) * (r.bbox[3] - r.bbox[1])).bbox
        eid = ctx.ev("document_detected", "document outline", i, bbox=box)
        ctx.add("document_detected", S.PASS, "Document located in the image", i, evidence=[eid], blocking=False)
        margin = 0.01
        touching = sum([box[0] <= margin * w, box[1] <= margin * h, box[2] >= (1 - margin) * w, box[3] >= (1 - margin) * h])
        if touching >= 2:
            ctx.add("document_framing", S.NOT_VERIFIED, "Document reaches the image border — make sure the whole "
                    "document is in the frame (it may be cropped)", i, blocking=False, evidence=[eid])
        expected = _EXPECTED_ASPECT.get(fam) or _EXPECTED_ASPECT.get(doc.document_type.document_type.value)
        bw, bh = box[2] - box[0], box[3] - box[1]
        if expected and touching == 0 and bh > 0:
            aspect = max(bw, bh) / max(1, min(bw, bh))
            ok = abs(aspect - expected) / expected <= 0.18
            ctx.add("document_proportions", S.PASS if ok else S.REVIEW_REQUIRED,
                    f"Document proportions {aspect:.2f} {'consistent with' if ok else 'differ from'} the expected "
                    f"{expected:.2f} for this document type", i, blocking=False, evidence=[eid])
    elif doc.image_size:
        ctx.add("document_detected", S.NOT_VERIFIED, "Document outline not located — framing could not be checked", i,
                blocking=False)
    if doc.ocr_lines:
        conf = doc.ocr_confidence
        ctx.add("ocr_confidence", S.PASS if conf >= OCR_CONFIDENCE_THRESHOLD else S.REVIEW_REQUIRED,
                f"Average text-reading confidence {conf:.0%}" + ("" if conf >= OCR_CONFIDENCE_THRESHOLD else
                " — below the 75% threshold; check the printed details by eye"), i, blocking=False,
                ocr_confidence=conf, lines=len(doc.ocr_lines), bounding_boxes=all(l.bbox for l in doc.ocr_lines))
    mrz = doc.mrz if doc.mrz and "format_error" not in doc.mrz else None
    if mrz:
        codes = reference.nationality_codes()
        bad = [f"{k.replace('_', ' ')} '{mrz[k]}'" for k in ("issuing_country", "nationality")
               if mrz.get(k) and mrz[k].replace("<", "") not in codes]
        ctx.add("nationality_code", S.PASS if not bad else S.REVIEW_REQUIRED,
                "MRZ country codes are valid ICAO codes" if not bad else "Not a valid ICAO country code: " + ", ".join(bad),
                i, strong=bool(bad) and (mrz.get("ocr_confidence") or 0) >= 0.93)


def _document_checks(ctx: Ctx, doc: DocumentAnalysis, image_based: bool) -> dict[str, Any]:
    """Checks that need no pixels (shared by image and extracted paths)."""
    i = doc.document_index
    dtr = doc.document_type
    dt = dtr.document_type
    fam = _family(dt)
    f = doc.fields
    reg_out: dict[str, Any] = {}

    if doc.quality:
        q = doc.quality
        if q["level"] == "POOR":
            ctx.add("image_quality", S.NOT_VERIFIED, "Image quality too low to verify reliably — " + "; ".join(q["issues"]), i)
        elif q["level"] == "MARGINAL":
            ctx.add("image_quality", S.REVIEW_REQUIRED, "Image quality requires manual review — " + "; ".join(q["issues"]), i,
                    blocking=False)
        else:
            ctx.add("image_quality", S.PASS, "Image is clear enough to read", i)

    _capture_checks(ctx, doc)
    if dt == DocumentType.DOCUMENT_TYPE_UNCERTAIN:
        ctx.add("document_type", S.NOT_VERIFIED, "Unsupported or unrecognised document — type could not be identified "
                f"with confidence (best guess confidence {dtr.confidence:.2f}); not forced", i, candidates=dtr.candidates,
                flags=["unsupported_document"])
    else:
        ctx.add("document_type", S.PASS, f"Identified as {dt.value.replace('_', ' ').title()}"
                + (f" ({dtr.country.title()})" if dtr.country else ""), i, confidence=dtr.confidence, basis=dtr.basis[:4])

    if doc.native_lines:
        native = [k for k in ("name_native", "date_of_birth_bs", "national_id_number", "citizenship_number")
                  if k in doc.fields]
        ctx.add("ocr_devanagari", S.PASS,
                f"{len(doc.native_lines)} Devanagari (Nepali/Hindi) text lines read"
                + (f"; details: {', '.join(k.replace('_', ' ') for k in native)}" if native else ""), i,
                blocking=False, advisory=True)
    if doc.electronic:
        e = doc.electronic
        ctx.add("electronic_document", S.OFFICIAL_VERIFICATION_REQUIRED,
                f"{e['label']} — {e['official_check']}", i, blocking=False,
                form=e["form"], markers=e["markers"])
    # --- OCR / key fields (MRZ can supply them)
    mrz = doc.mrz if doc.mrz and "format_error" not in doc.mrz else None
    mrz_fill = {"name": (mrz or {}).get("full_name"), "document_number": (mrz or {}).get("document_number"),
                "date_of_birth": (mrz or {}).get("date_of_birth_iso"), "date_of_expiry": (mrz or {}).get("date_of_expiry_iso")}
    keys = KEY_FIELDS.get(fam, KEY_FIELDS.get(dt.value, []))
    if keys:
        missing = [k for k in keys if k not in f and not (fam == "PASSPORT" and mrz_fill.get(k))]
        found = [k for k in keys if k not in missing]
        eids = [ctx.ev("ocr", f"{k.replace('_', ' ')} read ({f[k].confidence:.2f})", i, bbox=f[k].bbox) for k in found if k in f and f[k].bbox]
        if not missing:
            ctx.add("ocr", S.PASS, f"Key details read: {', '.join(k.replace('_', ' ') for k in found)}", i, evidence=eids,
                    ocr_confidence=doc.ocr_confidence)
        else:
            ctx.add("ocr", S.NOT_VERIFIED, f"Could not read: {', '.join(k.replace('_', ' ') for k in missing)}", i,
                    blocking=len(missing) * 2 >= len(keys), evidence=eids, ocr_confidence=doc.ocr_confidence)
    elif dt != DocumentType.IMMIGRATION_STAMP:
        ctx.add("ocr", S.PASS if doc.ocr_lines else S.NOT_VERIFIED,
                f"{len(doc.ocr_lines)} text lines extracted" if doc.ocr_lines else "No text could be extracted", i,
                blocking=not doc.ocr_lines)

    # --- document number format
    tmpl = _template(doc, ctx.on)
    num_key = {"VISA": "visa_number", DocumentType.BHUTAN_ENTRY_PERMIT.value: "permit_number"}.get(fam, "document_number")
    pattern = (tmpl or {}).get("field_patterns", {}).get(num_key)
    number = f.get(num_key) or (FieldValue(value=mrz_fill["document_number"], confidence=0.99, source="mrz")
                                 if num_key == "document_number" and mrz_fill.get("document_number") else None)
    if pattern and number:
        ok = bool(re.match(pattern, number.value))
        state_ok = True
        if dt == DocumentType.DRIVING_LICENCE and ok and dtr.country == "INDIA":
            state_ok = number.value[:2] in INDIAN_STATE_CODES
        eid = ctx.ev("field_format", f"{num_key.replace('_', ' ')} {number.value}", i, bbox=number.bbox)
        if ok and state_ok:
            ctx.add("field_format", S.PASS, f"{num_key.replace('_', ' ').capitalize()} follows the expected format", i, evidence=[eid])
        else:
            why = (f"state code {number.value[:2]!r} is not a recognised Indian state/UT code" if ok and not state_ok
                   else f"{number.value!r} does not follow the expected {dt.value.replace('_', ' ').lower()} number format")
            ctx.add("field_format", S.REVIEW_REQUIRED, why[0].upper() + why[1:], i, strong=number.confidence >= 0.9,
                    evidence=[eid])

    # --- validity + date logic
    exp = f.get("date_of_expiry").value if f.get("date_of_expiry") else mrz_fill.get("date_of_expiry")
    exp_bbox = f["date_of_expiry"].bbox if f.get("date_of_expiry") else (mrz or {}).get("bbox")
    vfrom = f.get("valid_from")
    if exp:
        eid = ctx.ev("document_validity", f"expiry {exp}", i, bbox=exp_bbox)
        if exp < ctx.on.isoformat():
            ctx.add("document_validity", S.FAIL, f"Document expired on {exp}", i, strong=True, evidence=[eid],
                    flags=["document_expired"])
        elif vfrom and vfrom.value > ctx.on.isoformat():
            ctx.add("document_validity", S.REVIEW_REQUIRED, f"Not valid until {vfrom.value}", i, evidence=[eid])
        else:
            days = (date.fromisoformat(exp) - ctx.on).days
            ctx.add("document_validity", S.PASS, f"Valid until {exp}" + (f" (expires in {days} days)" if days < 30 else ""), i,
                    evidence=[eid])
    elif fam in ("PASSPORT", "VISA") or dt in (DocumentType.DRIVING_LICENCE, DocumentType.BHUTAN_ENTRY_PERMIT):
        ctx.add("document_validity", S.NOT_VERIFIED, "Expiry date could not be read", i, blocking=False)
    dob = f.get("date_of_birth").value if f.get("date_of_birth") else mrz_fill.get("date_of_birth")
    issue = f.get("date_of_issue").value if f.get("date_of_issue") else None
    problems = []
    if dob and dob > ctx.on.isoformat():
        problems.append(f"date of birth {dob} is in the future")
    if dob and issue and issue < dob:
        problems.append(f"issue date {issue} is before date of birth {dob}")
    if issue and exp and exp < issue:
        problems.append(f"expiry {exp} is before issue date {issue}")
    if dt == DocumentType.DRIVING_LICENCE and dob and issue:
        age_at_issue = (date.fromisoformat(issue) - date.fromisoformat(dob)).days / 365.25
        if age_at_issue < 16:
            problems.append(f"licence issued at age {age_at_issue:.0f}, below the minimum licensing age")
    if problems:
        ctx.add("date_logic", S.REVIEW_REQUIRED, "; ".join(problems).capitalize(), i, strong=True)
    elif dob or issue:
        ctx.add("date_logic", S.PASS, "Dates are in a sensible order", i, blocking=False)

    # --- MRZ
    if doc.mrz or fam == "PASSPORT":
        if not doc.mrz:
            ctx.add("mrz_structure", S.NOT_VERIFIED, "Machine-readable zone could not be read", i)
        elif "format_error" in doc.mrz:
            ctx.add("mrz_structure", S.REVIEW_REQUIRED, f"Machine-readable zone is malformed: {doc.mrz['format_error']}", i,
                    evidence=[ctx.ev("mrz_structure", doc.mrz["format_error"], i, bbox=doc.mrz.get("bbox"))])
        else:
            m = doc.mrz
            eid = ctx.ev("mrz", f"{m['format']} machine-readable zone", i, bbox=m.get("bbox"), region_id=f"d{i}-mrz")
            ctx.add("mrz_structure", S.PASS, f"{m['format']} machine-readable zone found and well-formed", i, evidence=[eid])
            if m["all_checks_valid"]:
                ctx.add("mrz_check_digits", S.PASS, "All MRZ check digits correct", i, evidence=[eid])
            else:
                failed = [c for c in m["check_digits"] if not c["valid"]]
                confident = (m.get("ocr_confidence") or 0) >= 0.93
                ctx.add("mrz_check_digits", S.FAIL if confident else S.REVIEW_REQUIRED,
                        "; ".join(describe_failed_check(c) for c in failed) +
                        ("" if confident else " (MRZ was read with low confidence — may be a misread; check by eye)"),
                        i, strong=confident, evidence=[eid], failed_fields=[c["field"] for c in failed],
                        flags=["mrz_check_digit_failure"])

    # --- QR / barcode
    expected_qr = any(ft.get("feature_name") in ("qr_code", "secure_qr") for ft in (tmpl or {}).get("features", [])) \
        or "QR_CODE" in (tmpl or {}).get("layout_anchors", {})
    decoded = [c for c in doc.codes if c.decoded]
    if doc.codes:
        region_ids = {c.region_id for c in doc.codes}
        eids = [ctx.ev("machine_readable_code", f"{r.label.value.lower().replace('_', ' ')} ({r.meta.get('symbology')})",
                       i, bbox=r.bbox, region_id=r.id) for r in doc.regions if r.id in region_ids]
        if decoded:
            ctx.add("machine_readable_code", S.PASS,
                    f"{len(decoded)} code(s) decoded ({', '.join(sorted({c.symbology for c in decoded}))})", i,
                    evidence=eids, kinds=sorted({c.payload_kind for c in decoded}))
        else:
            # Located but unreadable (damaged, covered, too small): its data
            # cannot be verified — NOT_VERIFIED, never a finding of fraud. It
            # blocks only when the template expects a code or the trained
            # detector confirmed one (OpenCV alone sometimes "finds" a QR in a
            # signature scribble or guilloche).
            confirmed = expected_qr or any(r.source.startswith("yolo") for r in doc.regions
                                           if r.id in region_ids or r.label in (RegionLabel.QR_CODE, RegionLabel.BARCODE))
            ctx.add("machine_readable_code", S.NOT_VERIFIED, "A QR/barcode is present but could not be read — its data "
                    "could not be verified (damaged, covered or too small); recapture closer if possible", i,
                    blocking=confirmed, evidence=eids, flags=["machine_readable_unreadable"])
    elif expected_qr and image_based:
        # Advisory: QR detectors miss small or blurred codes on camera photos,
        # and older document versions carry no QR at all.
        good_image = (doc.quality or {}).get("level") == "GOOD"
        ctx.add("machine_readable_code", S.REVIEW_REQUIRED if good_image else S.NOT_VERIFIED,
                "No QR code found where this document's template expects one — check whether this version "
                "carries one (on many licences and cards it is printed on the back)" + ("" if good_image else " (image quality may be the cause)"), i, blocking=False,
                evidence=[ctx.ev("machine_readable_code", "expected QR region",
                                 i, bbox=_abs((tmpl or {}).get("layout_anchors", {}).get("QR_CODE"), (doc.image_size[1], doc.image_size[0])) if doc.image_size else None)],
                flags=["qr_missing"])

    # --- document-type specific
    if dt == DocumentType.AADHAAR:
        num = f.get("aadhaar_number")
        if num:
            valid = validate_verhoeff(num.value)
            eid = ctx.ev("aadhaar_number", "Aadhaar number region", i, bbox=num.bbox)
            if valid:
                ctx.add("aadhaar_number", S.PASS, "Aadhaar number passes its Verhoeff checksum", i, evidence=[eid])
            else:
                ctx.add("aadhaar_number", S.FAIL if num.confidence >= 0.9 else S.REVIEW_REQUIRED,
                        "Aadhaar number fails its Verhoeff checksum" + ("" if num.confidence >= 0.9 else " (may be an OCR misread)"),
                        i, strong=num.confidence >= 0.9, evidence=[eid])
            # Minimum necessary data: only the last 4 digits are ever kept.
            f["aadhaar_number"] = num.model_copy(update={"value": "XXXX XXXX " + num.value[-4:], "raw": None})
        secure = any(c.payload_kind == "SIGNED_SECURE_QR" for c in doc.codes)
        res = registries.AadhaarOfficialVerifier().verify(secure)
        ctx.add("aadhaar_official", S.OFFICIAL_VERIFICATION_REQUIRED, res["reason"], i)
    if fam == "PASSPORT":
        ctx.add("epassport_chip", S.NOT_VERIFIED, registries.EPassportChipVerifier().verify()["reason"].capitalize(), i,
                blocking=False)

    # --- registries
    reg: dict[str, Any] | None = None
    if dt == DocumentType.DRIVING_LICENCE and f.get("document_number"):
        reg = (ctx.dl_registry or registries.DrivingLicenceRegistry(offline=ctx.offline)).verify_driving_licence(f["document_number"].value)
        record = {k: reg.get(k) for k in ("name", "dob", "expiry_date", "status")} if reg.get("record_found") else None
        reg_out = {"record": record, "raw": reg}
    elif fam == "PASSPORT" and (mrz_fill.get("document_number") or f.get("document_number")):
        # Check-digit-validated MRZ values are the most reliable machine
        # reading of the document; printed OCR is the fallback.
        trusted = mrz_fill if mrz and mrz.get("all_checks_valid") else {}
        def pick(key: str) -> str | None:
            return trusted.get(key) or (f[key].value if f.get(key) else mrz_fill.get(key))
        reg = registries.lookup_passport(ctx.db, pick("document_number"), pick("name"), pick("date_of_birth"),
                                         (mrz or {}).get("nationality"), offline=ctx.offline)
        reg_out = {"record": None, "raw": reg}
    elif fam == "VISA" and f.get("visa_number"):
        reg = (ctx.travel_registry or registries.TravelAuthorisationRegistry(offline=ctx.offline)).lookup("VISA", f["visa_number"].value)
        reg_out = {"record": {k: reg.get(k) for k in ("name", "valid_until", "status")} if reg.get("record_found") else None, "raw": reg}
        if reg.get("record_found") and f.get("passport_number"):
            reg_out["record"]["passport_number"] = reg.get("passport_number")
    elif dt == DocumentType.BHUTAN_ENTRY_PERMIT and f.get("permit_number"):
        reg = (ctx.travel_registry or registries.TravelAuthorisationRegistry(offline=ctx.offline)).lookup("PERMIT", f["permit_number"].value)
        reg_out = {"record": {k: reg.get(k) for k in ("name", "valid_until", "status")} if reg.get("record_found") else None, "raw": reg}
    # Local test registry built from the sample dataset (only when populated;
    # consulted when the mock registries have no record for this number).
    number_for_lookup = ((mrz_fill.get("document_number") if mrz and mrz.get("all_checks_valid") else None)
                         or next((f[k].value for k in ("document_number", "visa_number", "permit_number") if f.get(k)), None))
    unmatched = reg is None or reg.get("status") in ("NO_RECORD", "REGISTRY_NOT_AVAILABLE") or reg.get("record_found") is False
    ds = registries.lookup_dataset_registry(ctx.db, number_for_lookup, offline=ctx.offline) if unmatched else None
    if ds is not None:
        rec = ds["record"]
        reg_out = {"record": {"name": rec["name"], "dob": rec["dob"], "expiry_date": rec["expiry_date"],
                              "nationality": rec["nationality"]}, "raw": {k: v for k, v in ds.items() if k != "record"}}
        reg = {"status": "DATASET_CONFLICT" if ds["status"] == "CONFLICT" else "DATASET_FOUND",
               "reason": ds.get("reason", ""), "record_found": True}
        if rec.get("face_embedding"):
            ctx.registry_face_embeddings[i] = np.asarray(json.loads(rec["face_embedding"]))
    if reg is not None:
        st = reg.get("status")
        if st == "DATASET_FOUND":
            ctx.add("registry", S.PASS, "Record found in the local test registry (built from sample images — "
                    "not a government database)", i)
        elif st == "DATASET_CONFLICT":
            ctx.add("registry", S.REVIEW_REQUIRED, f"Conflicting registry records: {reg['reason']}", i, strong=True,
                    flags=["conflicting_registry_records"])
        elif st == "REGISTRY_NOT_AVAILABLE":
            ctx.add("registry", S.REGISTRY_NOT_AVAILABLE, reg["reason"].capitalize(), i)
        elif st == "NO_RECORD" or (reg.get("record_found") is False):
            ctx.add("registry", S.REVIEW_REQUIRED, "Not found in the reference registry (mock) — identity could not "
                    "be confirmed; verify with the traveller before clearing", i, flags=["unregistered_document"])
        elif st in ("MISMATCH",):
            ctx.add("registry", S.REVIEW_REQUIRED, f"Registry record differs: {reg.get('reason')}", i, strong=True,
                    flags=["registry_mismatch"])
        elif st in ("EXPIRED", "REVOKED", "SUSPENDED"):
            ctx.add("registry", S.REVIEW_REQUIRED, f"Registry (mock) lists this document as {st}", i, strong=True,
                    flags=[f"registry_status_{st.lower()}"])
        else:
            ctx.add("registry", S.PASS, "Record found in the reference registry (mock data)", i)
        if reg.get("watchlist"):
            ctx.add("registry", S.REVIEW_REQUIRED, "Document number is on the (mock) watchlist: " +
                    ", ".join(w["reason"] for w in reg["watchlist"]), i, strong=True, flags=["watchlist_hit"])
    elif dt in (DocumentType.IDENTITY_DOCUMENT, DocumentType.VOTER_ID, DocumentType.OTHER_TRAVEL_DOCUMENT):
        ctx.add("registry", S.REGISTRY_NOT_AVAILABLE, "No authorised registry is configured for this document type", i,
                blocking=False)

    # Document photo vs the registry's reference photo (when the registry has one)
    if i in ctx.registry_face_embeddings:
        if i in ctx.doc_face_embeddings:
            sim = float(np.dot(ctx.doc_face_embeddings[i], ctx.registry_face_embeddings[i]))
            match = sim >= 0.5  # same threshold as the face provider
            ctx.add("reference_photo_match", S.PASS if match else S.REVIEW_REQUIRED,
                    (f"Document photo matches the registry reference photo (similarity {sim:.2f})" if match else
                     f"Document photo does not match the registry reference photo (similarity {sim:.2f}) — compare in person"),
                    i, strong=not match, similarity_score=round(sim, 3), flags=[] if match else ["photo_differs_from_registry"])
        else:
            ctx.add("reference_photo_match", S.NOT_VERIFIED, "A registry reference photo exists but no face could be "
                    "read from the document photo", i, blocking=False)

    # --- stamps
    if doc.stamps or dt == DocumentType.IMMIGRATION_STAMP:
        primary = dt == DocumentType.IMMIGRATION_STAMP
        if not doc.stamps:
            ctx.add("stamp_detection", S.NOT_VERIFIED, "No stamp region could be detected", i)
        for s in doc.stamps:
            eid = ctx.ev("stamp_detection", f"{s.stamp_type.value.replace('_', ' ').lower()} "
                         f"({s.identification.replace('_', ' ').lower()})", i, bbox=s.bbox, region_id=s.region_id,
                         country=s.country, checkpoint=s.checkpoint, direction=s.direction, date=s.date)
            ctx.add("stamp_detection", S.PASS, f"Stamp detected ({s.stamp_type.value.replace('_', ' ').lower()})", i,
                    evidence=[eid], stamp=s.model_dump(exclude={"ocr_text", "forensic_indicators"}))
            if s.identification == "IDENTIFIED":
                ctx.add("stamp_identification", S.PASS, "Stamp text read: " + ", ".join(
                    x for x in (s.country, s.checkpoint, s.direction, s.date) if x), i, evidence=[eid])
            elif s.stamp_type.value == "UNKNOWN_STAMP":
                ctx.add("stamp_identification", S.REVIEW_REQUIRED, "Stamp could not be identified from its text — "
                        "examine it manually", i, evidence=[eid], flags=["unknown_stamp"])
            else:
                ctx.add("stamp_identification", S.NOT_VERIFIED, "Stamp partially identified — could not read: "
                        + ", ".join(s.missing_fields), i, blocking=primary, evidence=[eid],
                        identification="PARTIALLY_IDENTIFIED")
            ctx.add("authority_identification", S.PASS if s.authority else S.NOT_VERIFIED,
                    f"Authority identified: {s.authority.title()}" if s.authority else "Issuing authority not readable",
                    i, blocking=False)
            if s.checkpoint:
                ctx.add("checkpoint_match", S.PASS, f"Checkpoint {s.checkpoint.title()} found in the official "
                        f"checkpoint reference ({(s.checkpoint_type or '').replace('_', ' ').lower()})", i, evidence=[eid],
                        checkpoint_id=s.checkpoint_id)
            else:
                ctx.add("checkpoint_match", S.NOT_VERIFIED, "Checkpoint name not found in the stamp text", i, blocking=False)
            ref_status = {"MATCH": S.PASS, "MISMATCH": S.REVIEW_REQUIRED}.get(s.reference_match, S.REFERENCE_NOT_AVAILABLE)
            ctx.add("stamp_reference", ref_status, "; ".join(n for n in s.notes if "reference" in n)[:300].capitalize()
                    or "No authoritative visual reference for this stamp", i,
                    blocking=ref_status == S.REVIEW_REQUIRED, evidence=[eid], reference_match=s.reference_match,
                    flags=["stamp_reference_mismatch"] if ref_status == S.REVIEW_REQUIRED else [])
    return reg_out


# ============================================================ public entry points

def _consistency_checks(ctx: Ctx, docs: list[DocumentAnalysis], eng: consistency.ConsistencyEngine) -> None:
    groups = {"printed_vs_mrz": "mrz_consistency", "printed_vs_machine_readable": "qr_consistency",
              "document_vs_registry": "registry_consistency", "passport_vs_visa": "cross_document",
              "passport_vs_permit": "cross_document", "document_vs_document": "cross_document",
              "stamp_vs_visa_validity": "stamp_consistency", "stamp_vs_checkpoint_reference": "stamp_consistency",
              "stamp_vs_verification_date": "stamp_consistency"}
    by_check: dict[tuple[str, int | None], list[dict]] = {}
    for row in eng.rows:
        name = groups.get(row["comparison"])
        if name:
            by_check.setdefault((name, row["document_index"]), []).append(row)
    for (name, i), rows in by_check.items():
        bad = [r for r in rows if r["result"] == "INCONSISTENCY_DETECTED"]
        soft = [r for r in rows if r["result"] in ("POSSIBLE_OCR_CONFUSION", "PARTIAL_MATCH")]
        eids = [ctx.ev(name, r["explanation"], i, bbox=r.get("bbox"), comparison_id=r["id"]) for r in bad + soft]
        flags = [f"{r['field']}_mismatch" if name != "qr_consistency" else "qr_data_mismatch" for r in bad]
        if bad:
            ctx.add(name, S.REVIEW_REQUIRED, "; ".join(r["explanation"] for r in bad).capitalize(), i,
                    strong=any(r["strong"] for r in bad), evidence=eids, flags=sorted(set(flags)),
                    comparisons=[r["id"] for r in rows])
        elif soft:
            ctx.add(name, S.REVIEW_REQUIRED, "; ".join(r["explanation"] for r in soft).capitalize(), i,
                    evidence=eids, comparisons=[r["id"] for r in rows])
        else:
            ctx.add(name, S.PASS, f"{len(rows)} comparison(s) consistent", i, comparisons=[r["id"] for r in rows])


def _border_label(route: str | None, checkpoint_type: str | None, source: str | None) -> str:
    names = {"INDIA_NEPAL": "India–Nepal", "INDIA_BHUTAN": "India–Bhutan"}
    parts = [names.get(route or "", "")]
    if checkpoint_type:
        parts.append(checkpoint_type.replace("_", " ").lower())
    label = " ".join(p for p in parts if p).strip()
    if not label:
        return "Not determined — choose the crossing"
    return label[0].upper() + label[1:] + (f" ({source})" if source else "")


def _finish(ctx: Ctx, docs: list[DocumentAnalysis], registry_results: dict[int, dict], *, border_route: str | None,
            direction: str | None, declared_nationality: str | None, pipeline_info: dict[str, Any],
            vlm_image: bytes | None, connectivity: str,
            post_checkpoint: dict[str, Any] | None = None) -> VerificationOutcome:
    # Crossing: chosen by the officer, else the border of the officer's own
    # post (e.g. Raxaul -> India-Nepal), so the treaty rules apply by default.
    route_source = "selected by the officer" if border_route else None
    if not border_route and post_checkpoint and post_checkpoint.get("border"):
        border_route = post_checkpoint["border"]
        route_source = "from the officer's post"
    eng = consistency.run(docs, registry_results, ctx.on)
    _consistency_checks(ctx, docs, eng)
    rule_checks, rule_info = border_rules.evaluate(border_route, docs, on=ctx.on, direction=direction,
                                                   declared_nationality=declared_nationality)
    ctx.checks.extend(rule_checks)

    # On a POOR image, pixel-derived REVIEW findings (non-deterministic ones)
    # are unreliable: downgrade them to NOT_VERIFIED rather than let a blurred
    # photo read as a suspicious document.
    poor = {d.document_index for d in docs if (d.quality or {}).get("level") == "POOR"}
    for c in ctx.checks:
        if c.document_index in poor and c.status == S.REVIEW_REQUIRED and not c.strong_evidence:
            c.status = S.NOT_VERIFIED
            c.summary = "Not assessable at this image quality — " + c.summary[0].lower() + c.summary[1:]
    status = decision.overall_status(ctx.checks)
    score, level, breakdown = decision.risk(ctx.checks)
    primary = next((d for d in docs if d.document_type.document_type != DocumentType.DOCUMENT_TYPE_UNCERTAIN), docs[0] if docs else None)
    stamps = [s for d in docs for s in d.stamps]
    checkpoint = next((s for s in stamps if s.checkpoint), None)
    facts = {"Country": (primary.document_type.country or "Not identified").title() if primary else "Not identified",
             "Document": (primary.document_type.document_type.value.replace("_", " ").title() if primary else "None"),
             "Checkpoint": checkpoint.checkpoint.title() + " (from stamp)" if checkpoint else
                           (post_checkpoint["checkpoint_name"].title() + " (your post)" if post_checkpoint else "Not determined"),
             "Border Type": _border_label(border_route, checkpoint.checkpoint_type if checkpoint else
                                         (post_checkpoint or {}).get("checkpoint_type"), route_source)}
    if len(docs) > 1:
        facts["Documents"] = str(len(docs))
    e_docs = [d.electronic for d in docs if d.electronic]
    if e_docs:
        facts["Form"] = "Electronic — " + e_docs[0]["label"]
    summary, explanation = decision.officer_summary(status, facts, ctx.checks, ctx.offline)

    worst: dict[str, CheckStatus] = {}
    rank = {s: i for i, s in enumerate([S.FAIL, S.REVIEW_REQUIRED, S.NOT_VERIFIED, S.OFFICIAL_VERIFICATION_REQUIRED,
                                        S.REGISTRY_NOT_AVAILABLE, S.REFERENCE_NOT_AVAILABLE, S.PASS, S.NOT_APPLICABLE])}
    for c in ctx.checks:
        if c.name not in worst or rank[c.status] < rank[worst[c.name]]:
            worst[c.name] = c.status
    flags = sorted({fl for c in ctx.checks if c.status in (S.FAIL, S.REVIEW_REQUIRED) for fl in c.details.get("flags", [])})

    advisory = None
    if pipeline_info.get("vlm_enabled"):
        lines = [f"{c.name}: {c.status.value} — {c.summary}" for c in ctx.checks if c.status != S.NOT_APPLICABLE]
        advisory = vlm.explain(lines, vlm_image)
    for d in docs:  # never ship raw OCR line dumps for identity docs beyond what's needed
        d.ocr_lines = [l for l in d.ocr_lines][:200]
    return VerificationOutcome(
        overall_status=status,
        country=primary.document_type.country if primary else None,
        document_type=primary.document_type.document_type.value if primary else DocumentType.DOCUMENT_TYPE_UNCERTAIN.value,
        checkpoint_type=checkpoint.checkpoint_type if checkpoint else None,
        border_route=border_route, confidence=decision.evidence_confidence(ctx.checks), explanation=explanation,
        risk_score=score, risk_level=level, risk_breakdown=breakdown,
        checks={k: v.value for k, v in worst.items()}, check_details=ctx.checks, flags=flags,
        advisories=[c.summary for c in ctx.checks if not c.blocking and c.status in (S.REVIEW_REQUIRED, S.NOT_VERIFIED)],
        evidence=ctx.evidence, documents=docs, cross_document=eng.rows, border_rules=rule_info,
        officer_summary=summary, connectivity=connectivity, pipeline=pipeline_info, advisory_explanation=advisory,
        suggested_reasons=decision.suggested_reasons(status, ctx.checks),
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def _pipeline_info(image_based: bool) -> dict[str, Any]:
    from app.core.config import get_settings
    s = get_settings()
    return {
        "mode": "server_image_analysis" if image_based else "device_extracted_data",
        "region_detector": get_region_detector().name if image_based else "on-device (reported by app)",
        "ocr": ENGINE_NAME if image_based else "on-device ML Kit (reported by app)",
        "ocr_devanagari": (DEVANAGARI_ENGINE if devanagari_available() else "not installed — Nepali/Hindi text not read")
        if image_based else "not run",
        "face": "InsightFace buffalo_sc (SCRFD detector + ArcFace-family embedding)",
        "machine_readable": "OpenCV QRCodeDetector + barcode.BarcodeDetector",
        "mrz": "ICAO 9303 parser (TD1/TD2/TD3/MRV-A/MRV-B) with recomputed check digits",
        "forensics": "region-vs-surroundings consensus (sharpness, noise, error level, JPEG grid, duplicates, metadata)",
        "signatures": "cryptography (Ed25519) against configured trust store; PDF/PAdES needs pyhanko",
        "vlm_enabled": bool(s.pramaan_vlm_base_url and s.pramaan_vlm_model),
        "reference_data_version": reference_dataset_hash(),
    }


def reference_dataset_hash() -> str:
    """Content hash of reference_data/ so each result records exactly which
    reference version it was checked against."""
    root = reference.reference_root()
    h = hashlib.sha256()
    for p in sorted(root.rglob("*.json")):
        h.update(p.relative_to(root).as_posix().encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def _norm_value(v: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", v.upper())


def _merge_device_fields(ctx: Ctx, doc: DocumentAnalysis, lines: list[OcrLine]) -> None:
    """The phone's own OCR fills only fields the server could not read
    (source "device", confidence discounted); where both read a field and
    disagree, an advisory check names the fields. The server's reading is
    never overwritten."""
    device = extract_fields(lines, doc.document_type.document_type)
    filled, differ, agree = [], [], []
    for key, fv in device.items():
        own = doc.fields.get(key)
        if own is None:
            doc.fields[key] = fv.model_copy(update={"source": "device", "confidence": round(fv.confidence * 0.9, 3)})
            filled.append(key)
        elif _norm_value(own.value) == _norm_value(fv.value):
            agree.append(key)
        else:
            differ.append(key)
    label = lambda keys: ", ".join(k.replace("_", " ") for k in keys)  # noqa: E731
    if differ:
        ctx.add("device_ocr_agreement", S.REVIEW_REQUIRED,
                f"Phone and server read different values for: {label(differ)} — check against the document",
                doc.document_index, blocking=False, differ=differ, agree=agree, filled=filled)
    elif agree or filled:
        ctx.add("device_ocr_agreement", S.PASS,
                (f"Phone and server readings agree ({label(agree)})" if agree else "Phone reading used") +
                (f"; read only on the phone: {label(filled)}" if filled else ""),
                doc.document_index, blocking=False, differ=[], agree=agree, filled=filled)


def verify_images(images: list[bytes], *, db: Any = None, border_route: str | None = None,
                  direction: str | None = None, declared_nationality: str | None = None,
                  travel_date: date | None = None, live_face: bytes | None = None,
                  reference_face: bytes | None = None, expected_type: DocumentType | None = None,
                  offline: bool = False, dl_registry: registries.DrivingLicenceRegistry | None = None,
                  travel_registry: registries.TravelAuthorisationRegistry | None = None,
                  prelocated: dict[int, list[Region]] | None = None,
                  quality_overrides: dict[int, dict[str, Any]] | None = None,
                  mode: str = "server_image_analysis",
                  device_lines: dict[int, list[OcrLine]] | None = None,
                  post_checkpoint: dict[str, Any] | None = None,
                  liveness: dict[str, Any] | None = None) -> VerificationOutcome:
    t0 = time.time()
    ctx = Ctx(on=travel_date or date.today(), db=db, offline=offline, dl_registry=dl_registry,
              travel_registry=travel_registry, liveness=liveness)
    docs: list[DocumentAnalysis] = []
    registry_results: dict[int, dict] = {}
    for idx, img in enumerate(images):
        raw_codes: dict[str, str] = {}
        doc, bgr, rgb = analyze_image(img, idx, on=ctx.on, expected_type=expected_type, raw_codes=raw_codes,
                                      prelocated=(prelocated or {}).get(idx),
                                      quality_override=(quality_overrides or {}).get(idx))
        docs.append(doc)
        if device_lines and device_lines.get(idx):
            _merge_device_fields(ctx, doc, device_lines[idx])
        if expected_type and doc.document_type.document_type not in (expected_type, DocumentType.DOCUMENT_TYPE_UNCERTAIN):
            ctx.add("document_type", S.REVIEW_REQUIRED,
                    f"Submitted as {expected_type.value.replace('_', ' ').title()} but identified as "
                    f"{doc.document_type.document_type.value.replace('_', ' ').title()}", idx)
        _image_checks(ctx, doc, bgr, rgb, img, live_face if idx == 0 else None, reference_face if idx == 0 else None,
                      raw_codes)
        registry_results[idx] = _document_checks(ctx, doc, image_based=True)
    info = _pipeline_info(True) | {"processing_seconds": round(time.time() - t0, 2), "mode": mode}
    if prelocated is not None:
        info["region_detector"] = "on-device detector (region crops only; full image never uploaded)"
    return _finish(ctx, docs, registry_results, border_route=border_route, direction=direction,
                   declared_nationality=declared_nationality, pipeline_info=info,
                   vlm_image=images[0] if images else None, connectivity="OFFLINE" if offline else "ONLINE",
                   post_checkpoint=post_checkpoint)


def verify_extracted(payload: dict[str, Any], *, db: Any = None) -> VerificationOutcome:
    """Device path: only extracted data arrives (no images). See
    app/schemas/docverify.py ExtractedVerificationRequest for the shape."""
    t0 = time.time()
    on = date.fromisoformat(payload["travel_date"]) if payload.get("travel_date") else date.today()
    ctx = Ctx(on=on, db=db, offline=False)
    docs: list[DocumentAnalysis] = []
    registry_results: dict[int, dict] = {}
    for idx, d in enumerate(payload.get("documents", [])):
        lines = [OcrLine(text=l["text"], confidence=l.get("confidence", 0.8), bbox=l.get("bbox") or [0, 0, 0, 0])
                 for l in d.get("ocr_lines", [])]
        mrz_info = None
        if d.get("mrz_lines"):
            try:
                mrz_info = parse_mrz(d["mrz_lines"])
            except MRZFormatError as exc:
                mrz_info = {"format_error": str(exc)}
            mrz_info.update(bbox=d.get("mrz_bbox"), ocr_confidence=d.get("mrz_confidence", 0.9))
        codes: list[MachineReadableCode] = []
        raw_codes: dict[str, str] = {}
        regions: list[Region] = []
        for c_idx, c in enumerate(d.get("codes", [])):
            rid = f"d{idx}-code-{c_idx + 1}"
            raw = c.get("raw_text")
            kind, cf = parse_payload(raw) if raw else (c.get("payload_kind", "UNREADABLE"), {})
            if raw:
                raw_codes[rid] = raw
            codes.append(MachineReadableCode(region_id=rid, symbology=c.get("symbology", "QR_CODE"), decoded=bool(raw) or
                                             kind == "SIGNED_SECURE_QR", payload_kind=kind, fields=cf,
                                             raw_length=len(raw or "")))
            if c.get("bbox"):
                regions.append(Region(id=rid, label=RegionLabel.QR_CODE if "QR" in c.get("symbology", "QR") else RegionLabel.BARCODE,
                                      bbox=c["bbox"], confidence=1.0, source="device"))
        if d.get("photo_bbox"):
            regions.append(Region(id=f"d{idx}-photo-1", label=RegionLabel.PHOTOGRAPH, bbox=d["photo_bbox"],
                                  confidence=0.9, source="device"))
        stamps = []
        for s_idx, st in enumerate(d.get("stamps", [])):
            r = Region(id=f"d{idx}-stamp-{s_idx + 1}", label=RegionLabel.STAMP, bbox=st.get("bbox") or [0, 0, 0, 0],
                       confidence=st.get("confidence", 0.6), source="device",
                       meta={"detector_label": st.get("detector_label")})
            res = identify_stamp(st.get("text", ""), r, st.get("confidence", 0.6))
            if res:
                res.reference_match, notes = compare_visual_reference(res)
                res.notes.extend(notes)
                stamps.append(res)
                regions.append(r)
        text = "\n".join(l.text for l in lines)
        if d.get("document_type"):
            try:
                dtr = DocumentTypeResult(document_type=DocumentType(d["document_type"]), country=d.get("country"),
                                         confidence=d.get("type_confidence", 0.8), basis=["reported by device"])
            except ValueError:
                dtr = doc_type.classify(text, mrz_info if mrz_info and "format_error" not in mrz_info else None, regions)
        else:
            dtr = doc_type.classify(text, mrz_info if mrz_info and "format_error" not in mrz_info else None, regions,
                                    identified_stamps=sum(1 for s in stamps if s.identification != "UNIDENTIFIED"))
        fields = extract_fields(lines, dtr.document_type) if lines else {}
        for k, v in (d.get("fields") or {}).items():
            if isinstance(v, dict) and v.get("value"):
                value = v["value"]
                if k.startswith("date") or k == "valid_from":
                    value = find_dates(value)[0][0] if find_dates(value) else value
                fields[k] = FieldValue(value=value, confidence=v.get("confidence", 0.8), source="device", bbox=v.get("bbox"))
        doc = DocumentAnalysis(document_index=idx, image_size=d.get("image_size"), document_type=dtr, regions=regions,
                               ocr_lines=lines, ocr_confidence=mean_confidence(lines), fields=fields, mrz=mrz_info,
                               codes=codes, stamps=stamps, quality=d.get("quality"))
        docs.append(doc)
        _signature_checks(ctx, doc, signatures.assess(codes, raw_codes, False, on))
        if d.get("photo_bbox") and d.get("image_size"):
            w, h = d["image_size"]
            tmpl = _template(doc, on)
            exp = (tmpl or {}).get("layout_anchors", {}).get("PHOTOGRAPH")
            ph = assess_photo(np.zeros((h, w, 3), np.uint8), regions, exp)
            doc.photo = ph
            if ph["signals"]:
                ctx.add("photo", S.REVIEW_REQUIRED, "; ".join(s["reason"] for s in ph["signals"]).capitalize(), idx)
            else:
                ctx.add("photo", S.PASS, "Photo position consistent with template", idx)
        ctx.add("tampering_analysis", S.NOT_VERIFIED, "Image forensics is not run on the server for device captures "
                "(images never leave the device)", idx, blocking=False)
        registry_results[idx] = _document_checks(ctx, doc, image_based=False)
    info = _pipeline_info(False) | {"processing_seconds": round(time.time() - t0, 2),
                                    "captured_offline": bool(payload.get("captured_offline")),
                                    "device_checks": payload.get("device_checks")}
    return _finish(ctx, docs, registry_results, border_route=payload.get("border_route"),
                   direction=payload.get("direction"), declared_nationality=payload.get("declared_nationality"),
                   pipeline_info=info, vlm_image=None, connectivity="ONLINE")


# ============================================================ device region crops

_CROP_LABELS = {"photograph": RegionLabel.PHOTOGRAPH, "mrz": RegionLabel.MRZ, "qr_code": RegionLabel.QR_CODE,
                "barcode": RegionLabel.BARCODE, "stamp": RegionLabel.STAMP,
                "yellow_gold_feature": RegionLabel.SECURITY_FEATURE}
MAX_CROP_COVERAGE = 0.9


class CropCoverageError(ValueError):
    pass


def canvas_from_crops(image_size: list[int], crops: list[dict[str, Any]], index: int,
                      device_detector: str | None) -> tuple[bytes, list[Region], list[str], np.ndarray]:
    """Rebuild a sparse, original-size canvas from the device's region crops.
    Areas the device did not send stay neutral grey. Rejects submissions
    whose crops together cover (nearly) the whole document — the contract is
    regions only, never the full image."""
    import base64
    w, h = image_size
    canvas = np.full((h, w, 3), 200, np.uint8)
    covered = np.zeros((h, w), bool)
    regions: list[Region] = []
    hashes: list[str] = []
    for k, c in enumerate(crops):
        raw = base64.b64decode(c["image_b64"], validate=True)
        hashes.append(hashlib.sha256(raw).hexdigest())
        arr = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        if arr is None:
            raise ValueError(f"region {k} is not a decodable image")
        x0, y0, x1, y1 = (int(v) for v in c["crop_bbox"])
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
        if x1 - x0 < 4 or y1 - y0 < 4:
            continue
        canvas[y0:y1, x0:x1] = cv2.resize(arr, (x1 - x0, y1 - y0))
        covered[y0:y1, x0:x1] = True
        label = _CROP_LABELS.get(c["label"])
        if label is not None:
            meta: dict[str, Any] = {"detector_label": "STAMP" if label == RegionLabel.STAMP else
                                    ("YELLOW_GOLD_FEATURE" if c["label"] == "yellow_gold_feature" else None)}
            regions.append(Region(id=f"d{index}-dev-{k}", label=label, bbox=[int(v) for v in c["bbox"]],
                                  confidence=float(c.get("confidence", 0.5)),
                                  source=f"device:{device_detector or 'on-device detector'}", meta=meta))
    if covered.mean() > MAX_CROP_COVERAGE:
        raise CropCoverageError(f"region crops cover {covered.mean():.0%} of the document; send regions, not the full image")
    ok, png = cv2.imencode(".png", canvas)
    return png.tobytes(), regions, hashes, canvas


def _crop_quality(canvas: np.ndarray, regions: list[Region]) -> dict[str, Any]:
    """Quality is judged on the crops that were sent, not the blank canvas."""
    text_like = [r for r in regions if r.label in (RegionLabel.MRZ, RegionLabel.PHOTOGRAPH, RegionLabel.STAMP)]
    if not text_like:
        return {"level": "GOOD", "issues": [], "note": "no reference region for quality — assumed adequate"}
    r = max(text_like, key=lambda r: (r.bbox[2] - r.bbox[0]) * (r.bbox[3] - r.bbox[1]))
    x0, y0, x1, y1 = (max(0, v) for v in r.bbox)
    q = _quality(cv2.cvtColor(canvas[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY))
    # a crop is small by construction; resolution alone is not a quality issue here
    q["issues"] = [i for i in q["issues"] if not i.startswith("resolution")]
    if q["level"] == "POOR" and q["sharpness"] >= 12 and q["brightness"] >= 30:
        q["level"] = "MARGINAL" if q["issues"] else "GOOD"
    q["measured_on"] = r.label.value.lower()
    return q


def verify_region_crops(payload: dict[str, Any], *, db: Any = None) -> tuple[VerificationOutcome, list[str]]:
    import base64
    images: list[bytes] = []
    prelocated: dict[int, list[Region]] = {}
    qualities: dict[int, dict[str, Any]] = {}
    hashes: list[str] = []
    for idx, d in enumerate(payload["documents"]):
        png, regions, h, canvas = canvas_from_crops(d["image_size"], d["regions"], idx, d.get("device_detector"))
        images.append(png)
        prelocated[idx] = regions
        qualities[idx] = d.get("quality") or _crop_quality(canvas, regions)
        hashes.extend(h)
    live = base64.b64decode(payload["live_face_b64"]) if payload.get("live_face_b64") else None
    td = payload.get("travel_date")
    device_lines: dict[int, list[OcrLine]] = {}
    for t in payload.get("device_text") or []:
        device_lines.setdefault(int(t.get("document_index", 0)), []).append(
            OcrLine(text=str(t["text"]).strip(), confidence=float(t.get("confidence", 0.8)), bbox=list(t["bbox"])))
    expected = None
    if payload.get("expected_document_type"):
        try:
            expected = DocumentType(payload["expected_document_type"])
        except ValueError:
            expected = None
    outcome = verify_images(images, db=db, border_route=payload.get("border_route"), direction=payload.get("direction"),
                            declared_nationality=payload.get("declared_nationality"),
                            travel_date=date.fromisoformat(str(td)) if td else None, live_face=live,
                            expected_type=expected, prelocated=prelocated, quality_overrides=qualities,
                            mode="device_region_crops", device_lines=device_lines or None,
                            post_checkpoint=payload.get("post_checkpoint"), liveness=payload.get("liveness"))
    return outcome, hashes
