"""Evaluate the document-verification pipeline.

  1. Synthetic suite (data/synthetic/docverify/ground_truth.json): runs every
     case end to end against an in-memory SQLite DB seeded with the synthetic
     citizen-registry records, then reports per-module and whole-pipeline
     metrics against the ground-truth labels.
  2. Face module over ALL pairs of drawn synthetic faces (same-person vs
     different-person), at the provider's match threshold.
  3. Real dataset (data/dataset_1, optional): document-type accuracy against
     labels.json, and OCR accuracy for passport fields using each document's
     own check-digit-validated MRZ as the reference.

Binary convention for pipeline metrics: positive = "officer attention
required" (ground truth), predicted positive = overall_status != PASS.

    .venv/bin/python -m scripts.docverify.evaluate [--skip-real]

Writes reports/docverify_evaluation.json and .md.
"""
from __future__ import annotations

import argparse
import threading
from concurrent.futures import ThreadPoolExecutor
import json
import logging
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
logging.disable(logging.WARNING)

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.models  # noqa: E402,F401
from app.db.base import Base  # noqa: E402
from app.models.citizen_registry import MockCitizenRegistryEntry  # noqa: E402
from app.services.docverify import registries  # noqa: E402
from app.services.docverify.consistency import compare_values  # noqa: E402
from app.services.docverify.pipeline import verify_images  # noqa: E402

SYN = ROOT / "data/synthetic/docverify"
REAL = ROOT / "data/dataset_1"
REPORTS = ROOT / "reports"


def binary_metrics(pairs: list[tuple[bool, bool]]) -> dict:
    tp = sum(1 for t, p in pairs if t and p)
    tn = sum(1 for t, p in pairs if not t and not p)
    fp = sum(1 for t, p in pairs if not t and p)
    fn = sum(1 for t, p in pairs if t and not p)
    n = len(pairs)
    prec = tp / (tp + fp) if tp + fp else None
    rec = tp / (tp + fn) if tp + fn else None
    f1 = 2 * prec * rec / (prec + rec) if prec and rec else (0.0 if prec is not None and rec is not None else None)
    r = lambda v: round(v, 3) if v is not None else None  # noqa: E731
    return {"n": n, "tp": tp, "tn": tn, "fp": fp, "fn": fn, "accuracy": r((tp + tn) / n) if n else None,
            "precision": r(prec), "recall": r(rec), "f1": r(f1),
            "false_positive_rate": r(fp / (fp + tn)) if fp + tn else None,
            "false_negative_rate": r(fn / (fn + tp)) if fn + tp else None}


def seeded_db(seed: list[dict]):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    for r in seed:
        db.add(MockCitizenRegistryEntry(**r))
    db.commit()
    return db


def _verify_case(case: dict, seed: list[dict], local: threading.local):
    """Run one synthetic case. Each worker thread gets its own seeded
    in-memory registry (a SQLAlchemy session is not shared across threads)."""
    if getattr(local, "db", None) is None:
        local.db = seeded_db(seed)
    opts = case["options"]
    images = [(SYN / f).read_bytes() for f in case["images"]]
    live = (SYN / opts["live_face"]).read_bytes() if opts.get("live_face") else None
    ref = (SYN / opts["reference_face"]).read_bytes() if opts.get("reference_face") else None
    dl_reg = registries.DrivingLicenceRegistry(mode=opts.get("dl_registry_mode", "mock"), offline=bool(opts.get("offline")))
    t0 = time.time()
    out = verify_images(images, db=local.db, border_route=opts.get("border_route"), direction=opts.get("direction"),
                        travel_date=date.fromisoformat(opts["travel_date"]), live_face=live, reference_face=ref,
                        offline=bool(opts.get("offline")), dl_registry=dl_reg)
    return out, round(time.time() - t0, 2)


def run_synthetic(workers: int = 1) -> dict:
    gt = json.loads((SYN / "ground_truth.json").read_text())
    seed = gt["registry_seed"]["citizen_registry"]
    local = threading.local()
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        results = list(pool.map(lambda c: _verify_case(c, seed, local), gt["cases"]))
    rows, pipe = [], []
    ocr_hits = ocr_total = 0
    doc_type_hits = doc_type_total = 0
    tamper_pairs, validation_pairs, check_hits, check_total = [], [], 0, 0
    face_rows = []
    for case, (out, secs) in zip(gt["cases"], results):
        truth = case["ground_truth"]
        predicted_attention = out.overall_status.value != "PASS"
        pipe.append((truth["attention_required"], predicted_attention))
        overall_ok = out.overall_status.value in truth["expected_overall"]

        # document type
        for i, expected in enumerate(truth.get("document_types", [])):
            if i < len(out.documents):
                doc_type_total += 1
                got = out.documents[i].document_type.document_type.value
                doc_type_hits += int(got == expected)
        # OCR fields
        for idx, fields in truth.get("fields", {}).items():
            doc = out.documents[int(idx)]
            for key, want in fields.items():
                ocr_total += 1
                got = doc.fields.get(key)
                if got and compare_values(key, got.value, want) == "CONSISTENT":
                    ocr_hits += 1
                elif got and got.value.replace(" ", "").upper() == want.replace(" ", "").upper():
                    ocr_hits += 1
        # expected checks (validation / module-level)
        statuses = {}
        for c in out.check_details:
            statuses.setdefault(c.name, []).append(c.status.value)
        check_detail = {}
        for name, allowed in truth.get("expected_checks", {}).items():
            check_total += 1
            got = statuses.get(name, ["(not run)"])
            ok = any(g in allowed for g in got)
            check_hits += int(ok)
            check_detail[name] = {"expected": allowed, "got": got, "ok": ok}
        # tampering module: case-level
        if truth.get("tampered") is not None:
            tamper_detected = any(c.name in ("tampering_analysis", "stamp_forensics") and c.status.value == "REVIEW_REQUIRED"
                                  and c.blocking for c in out.check_details)
            tamper_pairs.append((truth["tampered"], tamper_detected))
        # validation module: cases whose expected checks are deterministic validation checks
        val_checks = {"mrz_check_digits", "mrz_consistency", "document_validity", "qr_consistency", "cross_document",
                      "registry_consistency", "digital_signature", "stamp_consistency", "visa_requirement"}
        if any(k in val_checks for k in truth.get("expected_checks", {})) or not truth["attention_required"]:
            flagged = any(c.name in val_checks and c.status.value in ("REVIEW_REQUIRED", "FAIL") for c in out.check_details)
            should = any(k in val_checks and any(s in ("REVIEW_REQUIRED", "FAIL") for s in v)
                         for k, v in truth.get("expected_checks", {}).items())
            validation_pairs.append((should, flagged))
        if truth.get("face_same") is not None:
            fv = next((c for c in out.check_details if c.name == "face_verification"), None)
            face_rows.append((not truth["face_same"], fv is not None and fv.status.value != "PASS"))
        rows.append({"case_id": case["case_id"], "description": case["description"], "seconds": secs,
                     "overall_status": out.overall_status.value, "expected_overall": truth["expected_overall"],
                     "overall_ok": overall_ok, "attention_required": truth["attention_required"],
                     "predicted_attention": predicted_attention, "risk_score": out.risk_score,
                     "document_types": [d.document_type.document_type.value for d in out.documents],
                     "flags": out.flags, "checks": check_detail})
    return {
        "cases": rows,
        "pipeline_attention": binary_metrics(pipe),
        "overall_status_exact_match": round(sum(r["overall_ok"] for r in rows) / len(rows), 3),
        "expected_check_accuracy": {"hits": check_hits, "total": check_total, "accuracy": round(check_hits / check_total, 3)},
        "document_type_accuracy": {"hits": doc_type_hits, "total": doc_type_total,
                                   "accuracy": round(doc_type_hits / doc_type_total, 3) if doc_type_total else None},
        "ocr_field_accuracy": {"hits": ocr_hits, "total": ocr_total, "accuracy": round(ocr_hits / ocr_total, 3) if ocr_total else None},
        "tampering": binary_metrics(tamper_pairs),
        "validation": binary_metrics(validation_pairs),
        "face_end_to_end": binary_metrics(face_rows),
    }


def run_face_pairs() -> dict:
    import io

    from app.services.face.mobilefacenet_provider import MobileFaceNetProvider
    from scripts.docverify.synthetic_faces import synthetic_face

    def png(img):
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return buf.getvalue()

    provider = MobileFaceNetProvider()
    seeds = range(12)
    base = {s: png(synthetic_face(s)) for s in seeds}
    pairs = []
    for s in seeds:  # same person, different capture
        r = provider.verify(base[s], png(synthetic_face(s, variant=1)))
        pairs.append((False, not r.match))  # positive = "no match" (attention)
    for a in seeds:
        for b in seeds:
            if a < b:
                r = provider.verify(base[a], base[b])
                pairs.append((True, not r.match))
    m = binary_metrics(pairs)
    m["note"] = ("12 drawn synthetic identities: 12 same-person pairs, 66 different-person pairs; positive = "
                 "'no match'. Drawn faces are NOT representative of real photographs.")
    return m


def run_real() -> dict | None:
    labels_path = REAL / "labels.json"
    if not labels_path.exists():
        return None
    labels = json.loads(labels_path.read_text())
    recs = [r for r in labels["records"] if not r["exclude"]]
    type_hits, rows = 0, []
    mrz_ref_hits = mrz_ref_total = 0
    for r in recs:
        out = verify_images([(REAL / "Dataset" / r["file"]).read_bytes()])
        doc = out.documents[0]
        got, country = doc.document_type.document_type.value, doc.document_type.country
        ok = got == r["document_type"] or got in r.get("acceptable_alternatives", [])
        type_hits += int(ok)
        rows.append({"file": r["file"], "expected": r["document_type"], "got": got, "ok": ok,
                     "expected_country": r["country"], "got_country": country, "overall_status": out.overall_status.value})
        m = doc.mrz
        if m and m.get("all_checks_valid"):
            ref = {"document_number": m["document_number"], "date_of_birth": m["date_of_birth_iso"],
                   "date_of_expiry": m["date_of_expiry_iso"]}
            for k, v in ref.items():
                if v:
                    mrz_ref_total += 1
                    fv = doc.fields.get(k)
                    mrz_ref_hits += int(bool(fv) and compare_values(k, fv.value, v) == "CONSISTENT")
    per_type: dict[str, dict] = {}
    for row in rows:
        t = per_type.setdefault(row["expected"], {"n": 0, "correct": 0})
        t["n"] += 1
        t["correct"] += int(row["ok"])
    return {"labels_status": labels["labelled_by"], "n": len(recs),
            "document_type_accuracy": round(type_hits / len(recs), 3), "per_type": per_type,
            "ocr_vs_validated_mrz": {"hits": mrz_ref_hits, "total": mrz_ref_total,
                                     "accuracy": round(mrz_ref_hits / mrz_ref_total, 3) if mrz_ref_total else None},
            "overall_status_distribution": {s: sum(1 for r in rows if r["overall_status"] == s)
                                            for s in sorted({r["overall_status"] for r in rows})},
            "rows": rows}


_REGION_CLASS = {"PHOTOGRAPH": "photograph", "MRZ": "mrz", "QR_CODE": "qr_code", "BARCODE": "barcode",
                 "STAMP": "stamp", "DOCUMENT": "document"}


def _iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def run_region_detection() -> dict | None:
    """Per-class region-detection precision/recall on the HELD-OUT REAL
    images (same split the YOLO model never trained on), comparing the
    classical detector and YOLO11n through the full pipeline code path."""
    split_file = ROOT / "data/yolo/docverify/split.json"
    boxes_file = REAL / "boxes.json"
    if not split_file.exists() or not boxes_file.exists():
        return None
    from app.services.docverify import detection, pipeline
    from app.services.docverify.detection import ClassicalRegionDetector, YoloRegionDetector

    split = json.loads(split_file.read_text())["real"]
    val_files = [v["file"] for v in split.values() if v["split"] == "val"]
    truth = json.loads(boxes_file.read_text())["boxes"]
    weights = detection.DEFAULT_WEIGHTS
    detectors = {"classical": ClassicalRegionDetector()}
    if weights.is_file():
        try:
            detectors["yolo11n"] = YoloRegionDetector(str(weights), 0.35)
        except ImportError:
            pass
    out: dict[str, dict] = {}
    original = pipeline.get_region_detector
    for name, det in detectors.items():
        pipeline.get_region_detector = lambda det=det: det
        stats: dict[str, dict[str, int]] = {}
        for f in val_files:
            data = (REAL / "Dataset" / f).read_bytes()
            doc, bgr, _ = pipeline.analyze_image(data, 0, on=date.today())
            h, w = bgr.shape[:2]
            preds = [(_REGION_CLASS.get(r.label.value) or ("yellow_gold_feature" if r.meta.get("detector_label") == "YELLOW_GOLD_FEATURE" else None),
                      [r.bbox[0] / w, r.bbox[1] / h, r.bbox[2] / w, r.bbox[3] / h]) for r in doc.regions]
            if name == "classical":  # the classical path finds the yellow/gold feature in the security-feature stage
                from app.services.docverify.security_features import detect_yellow_gold_feature
                yg = detect_yellow_gold_feature(bgr, None)
                if yg.get("detected"):
                    b = yg["bbox_xyxy"]
                    preds.append(("yellow_gold_feature", [b[0] / w, b[1] / h, b[2] / w, b[3] / h]))
            preds = [p for p in preds if p[0]]
            gts = [(b["cls"], b["box"]) for b in truth.get(f, [])]
            for cls in {c for c, _ in gts} | {c for c, _ in preds}:
                st = stats.setdefault(cls, {"tp": 0, "fp": 0, "fn": 0})
                g = [b for c, b in gts if c == cls]
                p = [b for c, b in preds if c == cls]
                used = set()
                for pb in p:
                    hit = next((i for i, gb in enumerate(g) if i not in used and _iou(pb, gb) >= 0.5), None)
                    if hit is None:
                        st["fp"] += 1
                    else:
                        used.add(hit)
                        st["tp"] += 1
                st["fn"] += len(g) - len(used)
        per_class = {}
        for cls, st in sorted(stats.items()):
            tp, fp, fn = st["tp"], st["fp"], st["fn"]
            per_class[cls] = {**st, "precision": round(tp / (tp + fp), 3) if tp + fp else None,
                              "recall": round(tp / (tp + fn), 3) if tp + fn else None}
        tot = {k: sum(v[k] for v in stats.values()) for k in ("tp", "fp", "fn")}
        out[name] = {"per_class": per_class,
                     "overall": {**tot, "precision": round(tot["tp"] / max(1, tot["tp"] + tot["fp"]), 3),
                                 "recall": round(tot["tp"] / max(1, tot["tp"] + tot["fn"]), 3)}}
    pipeline.get_region_detector = original
    return {"held_out_real_images": len(val_files), "iou_threshold": 0.5, "detectors": out}


def _variants(img):
    """Capture-condition variants of one clean synthetic document."""
    import io
    from PIL import Image, ImageEnhance, ImageFilter
    import numpy as np

    def jpeg(im, q):
        buf = io.BytesIO(); im.convert("RGB").save(buf, "JPEG", quality=q); return Image.open(io.BytesIO(buf.getvalue()))
    w, h = img.size
    arr = np.asarray(img.convert("RGB")).astype(np.float32)
    shadow = np.clip(arr * np.linspace(1.0, 0.45, w)[None, :, None], 0, 255).astype(np.uint8)
    glare = arr.copy()
    yy, xx = np.mgrid[0:h, 0:w]
    spot = np.exp(-(((xx - 0.6 * w) / (0.08 * w)) ** 2 + ((yy - 0.45 * h) / (0.08 * h)) ** 2))
    glare = np.clip(glare + 255 * spot[..., None] * 1.4, 0, 255).astype(np.uint8)
    noisy = np.clip(arr + np.random.default_rng(3).normal(0, 14, arr.shape), 0, 255).astype(np.uint8)
    return {
        "clear": img,
        "low_resolution": img.resize((w // 3, h // 3)).resize((w, h)),
        "blur": img.filter(ImageFilter.GaussianBlur(2.5)),
        "rotation_5deg": img.rotate(5, expand=True, fillcolor=(200, 200, 200)),
        "rotation_90deg": img.rotate(90, expand=True),
        "rotation_180deg": img.rotate(180),
        "dark": ImageEnhance.Brightness(img).enhance(0.45),
        "bright": ImageEnhance.Brightness(img).enhance(1.5),
        "shadow": Image.fromarray(shadow),
        "glare": Image.fromarray(glare),
        "low_quality_camera": jpeg(Image.fromarray(noisy), 35),
    }


def run_robustness() -> dict:
    """Same document under different capture conditions: does the pipeline
    still identify it, read it and locate its regions — and how confident
    and how fast is it? (Synthetic documents; indicative only.)"""
    import io
    import time
    from PIL import Image
    from app.services.docverify.types import RegionLabel

    gt = json.loads((SYN / "ground_truth.json").read_text())
    subjects = {"passport": ("GEN-001_passport.jpg", "INDIAN_PASSPORT"), "driving_licence": ("GEN-003_dl.jpg", "DRIVING_LICENCE"),
                "stamp_page": ("TST-007_stamp.jpg", "IMMIGRATION_STAMP")}
    rows = []
    for subject, (fname, expected_type) in subjects.items():
        base = Image.open(SYN / fname).convert("RGB")
        variants = _variants(base)
        if subject == "stamp_page":  # faded, overlapping and rotated stamps
            from scripts.docverify.generate_synthetic_testset import stamp, stamp_page
            faded = stamp(["NEPAL IMMIGRATION", "KAKARBHITTA", "ARRIVAL", "12 SEP 2026"], colour=(150, 160, 205))
            variants["faded_stamp"] = stamp_page([(faded, (260, 300))])
            a = stamp(["NEPAL IMMIGRATION", "KAKARBHITTA", "ARRIVAL", "12 SEP 2026"])
            b = stamp(["NEPAL IMMIGRATION", "BIRGUNJ", "DEPARTURE", "20 SEP 2026"], colour=(170, 30, 40)).rotate(25, expand=True)
            variants["overlapping_rotated_stamps"] = stamp_page([(a, (200, 300)), (b, (380, 420))])
        for name, im in variants.items():
            buf = io.BytesIO(); im.convert("RGB").save(buf, "JPEG", quality=92)
            t0 = time.time()
            out = verify_images([buf.getvalue()], travel_date=date.fromisoformat(gt["travel_date"]))
            secs = round(time.time() - t0, 2)
            doc = out.documents[0]
            det = [r.confidence for r in doc.regions if r.source.startswith("yolo")]
            quality = next((c for c in out.check_details if c.name == "image_quality"), None)
            rows.append({"subject": subject, "condition": name, "overall_status": out.overall_status.value,
                         "document_type_correct": doc.document_type.document_type.value == expected_type,
                         "detection_confidence_mean": round(sum(det) / len(det), 3) if det else None,
                         "regions": len(doc.regions), "ocr_confidence": doc.ocr_confidence,
                         "ocr_lines": len(doc.ocr_lines), "face_found": bool((doc.photo or {}).get("face_detected")),
                         "stamps_identified": sum(1 for st in doc.stamps if st.identification != "UNIDENTIFIED"),
                         "quality_flag": quality.status.value if quality else None,
                         "rotation_corrected": (doc.quality or {}).get("rotation_corrected_degrees"),
                         "processing_seconds": secs})
    times = [r["processing_seconds"] for r in rows]
    return {"rows": rows, "document_type_accuracy": round(sum(r["document_type_correct"] for r in rows) / len(rows), 3),
            "processing_seconds": {"mean": round(sum(times) / len(times), 2), "max": max(times)}}


def markdown(report: dict) -> str:
    s = report["synthetic"]
    L = ["# Document-verification evaluation", "",
         f"Generated {report['generated_at']}. **Synthetic results are measured on documents this project generated "
         "itself, with layouts matching its own templates — they are optimistic and are not evidence of real-world "
         "accuracy.**", "", "## Synthetic suite", "",
         "| Module | n | Accuracy | Precision | Recall | F1 | FPR | FNR |", "|---|---|---|---|---|---|---|---|"]
    for name, key in (("Complete pipeline (attention required)", "pipeline_attention"), ("Validation", "validation"),
                      ("Tampering", "tampering"), ("Face (end-to-end cases)", "face_end_to_end")):
        m = s[key]
        L.append(f"| {name} | {m['n']} | {m['accuracy']} | {m['precision']} | {m['recall']} | {m['f1']} | "
                 f"{m['false_positive_rate']} | {m['false_negative_rate']} |")
    f = report["face_pairs"]
    L.append(f"| Face (all synthetic pairs) | {f['n']} | {f['accuracy']} | {f['precision']} | {f['recall']} | {f['f1']} | "
             f"{f['false_positive_rate']} | {f['false_negative_rate']} |")
    L += ["", f"- OCR field accuracy (synthetic): {s['ocr_field_accuracy']['hits']}/{s['ocr_field_accuracy']['total']} = "
          f"{s['ocr_field_accuracy']['accuracy']}",
          f"- Document-type accuracy (synthetic): {s['document_type_accuracy']['accuracy']}",
          f"- Overall status matches expectation: {s['overall_status_exact_match']}",
          f"- Expected check-level outcomes: {s['expected_check_accuracy']['hits']}/{s['expected_check_accuracy']['total']}",
          "", "| Case | Expected | Got | Risk | OK |", "|---|---|---|---|---|"]
    for r in s["cases"]:
        L.append(f"| {r['case_id']} {r['description'][:70]} | {'/'.join(r['expected_overall'])} | {r['overall_status']} | "
                 f"{r['risk_score']} | {'yes' if r['overall_ok'] else 'NO'} |")
    rb = report.get("robustness")
    if rb:
        L += ["", "## Robustness (synthetic documents under different capture conditions)", "",
              f"Document type correct in {rb['document_type_accuracy']:.0%} of variants; processing time mean "
              f"{rb['processing_seconds']['mean']}s, max {rb['processing_seconds']['max']}s (server CPU).", "",
              "| Subject | Condition | Status | Type ok | Det. conf | OCR conf | Face | Stamps id | Quality | Rot. | s |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in rb["rows"]:
            L.append(f"| {r['subject']} | {r['condition']} | {r['overall_status']} | {'yes' if r['document_type_correct'] else 'no'} | "
                     f"{r['detection_confidence_mean']} | {r['ocr_confidence']} | {'yes' if r['face_found'] else 'no'} | "
                     f"{r['stamps_identified']} | {r['quality_flag']} | {r['rotation_corrected'] or ''} | {r['processing_seconds']} |")
    rd = report.get("region_detection")
    if rd:
        L += ["", f"## Region detection on {rd['held_out_real_images']} held-out REAL images (IoU >= 0.5)", "",
              "| Class | " + " | ".join(f"{d} P / R" for d in rd["detectors"]) + " |",
              "|---|" + "---|" * len(rd["detectors"])]
        classes = sorted({c for d in rd["detectors"].values() for c in d["per_class"]})
        for c in classes:
            cells = []
            for d in rd["detectors"].values():
                pc = d["per_class"].get(c)
                cells.append(f"{pc['precision']} / {pc['recall']}" if pc else "—")
            L.append(f"| {c} | " + " | ".join(cells) + " |")
        L.append("| **overall** | " + " | ".join(f"{d['overall']['precision']} / {d['overall']['recall']}"
                                                  for d in rd["detectors"].values()) + " |")
    real = report.get("real")
    if real:
        L += ["", "## Real dataset (data/dataset_1, not committed)", "",
              f"Labels: {real['labels_status']}. n = {real['n']} (screenshots and duplicates excluded).", "",
              f"- Document-type accuracy: **{real['document_type_accuracy']}**",
              f"- Passport OCR vs the document's own validated MRZ: {real['ocr_vs_validated_mrz']['hits']}/"
              f"{real['ocr_vs_validated_mrz']['total']} = {real['ocr_vs_validated_mrz']['accuracy']}",
              f"- Overall status distribution: {real['overall_status_distribution']}", "",
              "| Expected type | n | correct |", "|---|---|---|"]
        for t, v in sorted(real["per_type"].items()):
            L.append(f"| {t} | {v['n']} | {v['correct']} |")
        misses = [r for r in real["rows"] if not r["ok"]]
        if misses:
            L += ["", "Misclassified:", ""] + [f"- {r['file']}: expected {r['expected']}, got {r['got']}" for r in misses]
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-real", action="store_true")
    ap.add_argument("--workers", type=int, default=1,
                    help="synthetic cases verified in parallel (per-case timings then include contention)")
    args = ap.parse_args()
    from datetime import datetime, timezone
    report = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "synthetic": run_synthetic(args.workers), "face_pairs": run_face_pairs(),
              "robustness": run_robustness(),
              "region_detection": None if args.skip_real else run_region_detection(),
              "real": None if args.skip_real else run_real()}
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "docverify_evaluation.json").write_text(json.dumps(report, indent=2) + "\n")
    # The real-data table lists file names only (no personal data), but it is
    # still kept out of the committed markdown summary's detail rows.
    (REPORTS / "docverify_evaluation.md").write_text(markdown(report))
    print(markdown(report))


if __name__ == "__main__":
    main()
