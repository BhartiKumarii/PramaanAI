"""Build the LOCAL test-fixture registry from the project's sample images.

    .venv/bin/python -m scripts.docverify.build_dataset_registry [--zip /home/bharti/Dataset_1.zip]

For every usable image in data/dataset_1 (labels.json: screenshots and
duplicates excluded) it runs the verification pipeline's own extraction —
YOLO11n regions, PP-OCR, MRZ parsing, field extraction — and stores:

  * the document's fields, preferring check-digit-validated MRZ values
    (record_status MRZ_VALIDATED) over OCR (OCR_UNREVIEWED, with confidence);
  * a face crop of the document photograph (data/dataset_1/faces/, gitignored)
    and its ArcFace-family embedding (InsightFace);
  * portrait-only images as FACE_ONLY records, linked to the most similar
    document face only as a suggestion (similarity recorded, never asserted).

Aadhaar numbers: last 4 digits + SHA-256 only. Everything is labelled
REAL_SAMPLE_TEST_FIXTURE and must never be deployed or committed. Writes
data/dataset_1/registry_export.json for manual review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import zipfile
from datetime import date
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
logging.disable(logging.WARNING)

from app.db.session import SessionLocal  # noqa: E402
import app.models  # noqa: E402,F401
from app.models.document_verification import DatasetRegistryRecord  # noqa: E402
from app.services.docverify.consistency import norm_number  # noqa: E402
from app.services.docverify.detection import detect_faces  # noqa: E402
from app.services.docverify.pipeline import analyze_image  # noqa: E402
from app.services.docverify.types import RegionLabel  # noqa: E402

DATA = ROOT / "data/dataset_1"
FACES = DATA / "faces"
LINK_THRESHOLD = 0.5  # same as the face provider's match threshold


def embed(face_bgr: np.ndarray) -> list[float] | None:
    from app.services.face.mobilefacenet_provider import _get_insightface_app
    app = _get_insightface_app()
    if app is None or face_bgr.size == 0:
        return None
    padded = cv2.copyMakeBorder(face_bgr, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    found = app.get(padded) or app.get(cv2.resize(padded, None, fx=2, fy=2))
    return [round(float(v), 6) for v in max(found, key=lambda f: f.det_score).normed_embedding] if found else None


MIN_FACE_PX = 40
MIN_FACE_SCORE = 0.6


def face_crop(bgr: np.ndarray, regions) -> np.ndarray | None:
    """Best face across ALL photograph regions: the strongest detection wins.
    The faint "ghost" portrait printed on many passports/ID cards is detected
    with a lower score than the main photo, and tiny emblems are rejected by
    the minimum size/score."""
    h, w = bgr.shape[:2]
    photos = [r.bbox for r in regions if r.label == RegionLabel.PHOTOGRAPH] or [[0, 0, w, h]]
    best = None  # (score, area, crop)
    for bx in photos:
        x0, y0, x1, y1 = max(0, bx[0]), max(0, bx[1]), min(w, bx[2]), min(h, bx[3])
        area = bgr[y0:y1, x0:x1]
        if area.size == 0:
            continue
        for (fx0, fy0, fx1, fy1), score, _ in detect_faces(area):
            fw, fh = fx1 - fx0, fy1 - fy0
            if min(fw, fh) < MIN_FACE_PX or score < MIN_FACE_SCORE:
                continue
            cx0, cy0 = max(0, fx0 - int(0.3 * fw)), max(0, fy0 - int(0.35 * fh))
            cx1, cy1 = min(area.shape[1], fx1 + int(0.3 * fw)), min(area.shape[0], fy1 + int(0.3 * fh))
            key = (round(score, 2), fw * fh)
            if best is None or key > best[:2]:
                best = (key[0], key[1], area[cy0:cy1, cx0:cx1])
    return best[2] if best else None


def fields_for(doc) -> tuple[dict, dict, str]:
    """Best value per field with provenance; MRZ wins when its check digits pass."""
    values: dict[str, str] = {}
    prov: dict[str, dict] = {}
    for k, fv in doc.fields.items():
        values[k] = fv.value
        prov[k] = {"source": "ocr", "confidence": round(fv.confidence, 3)}
    mrz = doc.mrz if doc.mrz and "format_error" not in doc.mrz else None
    status = "OCR_UNREVIEWED"
    if mrz and mrz.get("all_checks_valid"):
        status = "MRZ_VALIDATED"
        for k, v in (("document_number", mrz.get("document_number")), ("name", mrz.get("full_name")),
                     ("date_of_birth", mrz.get("date_of_birth_iso")), ("date_of_expiry", mrz.get("date_of_expiry_iso")),
                     ("nationality", mrz.get("nationality")), ("sex", mrz.get("sex"))):
            if v:
                values[k] = v
                prov[k] = {"source": "mrz", "check_digits": "valid"}
    return values, prov, status


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", default="/home/bharti/Dataset_1.zip")
    args = ap.parse_args()
    if not (DATA / "Dataset").exists() and Path(args.zip).exists():
        with zipfile.ZipFile(args.zip) as z:
            z.extractall(DATA)
    labels = json.loads((DATA / "labels.json").read_text())
    FACES.mkdir(parents=True, exist_ok=True)
    db = SessionLocal()
    db.query(DatasetRegistryRecord).delete()  # rebuild from scratch (idempotent)
    db.commit()

    records: list[DatasetRegistryRecord] = []
    embeddings: dict[str, np.ndarray] = {}
    for r in labels["records"]:
        if r["exclude"]:
            continue
        path = DATA / "Dataset" / r["file"]
        doc, bgr, _ = analyze_image(path.read_bytes(), 0, on=date.today())
        portrait = "portrait" in (r.get("note") or "")
        values, prov, status = fields_for(doc)
        extra = {k: v for k, v in values.items() if k not in
                 ("document_number", "name", "date_of_birth", "nationality", "sex", "date_of_issue", "date_of_expiry")}
        number = values.get("document_number") or values.get("visa_number") or values.get("permit_number")
        if r["document_type"] == "AADHAAR" and values.get("aadhaar_number"):
            # never store a full Aadhaar number (already masked by the pipeline)
            extra["aadhaar_number"] = values["aadhaar_number"]
            number = None
        rec = DatasetRegistryRecord(
            source_file=r["file"], source_sha256=r["sha256"],
            document_type="PORTRAIT" if portrait else r["document_type"], country=r.get("country"),
            document_number=norm_number(number) if number else None,
            document_number_sha256=hashlib.sha256(norm_number(number).encode()).hexdigest() if number else None,
            full_name=values.get("name"), date_of_birth=values.get("date_of_birth"),
            nationality=values.get("nationality"), sex=values.get("sex"), date_of_issue=values.get("date_of_issue"),
            date_of_expiry=values.get("date_of_expiry"), extra_fields_json=json.dumps(extra, ensure_ascii=False),
            field_provenance_json=json.dumps(prov), record_status="FACE_ONLY" if portrait else status,
        )
        face = bgr if portrait else face_crop(bgr, doc.regions)
        if face is not None and face.size:
            if portrait:
                found = detect_faces(bgr)
                if found:
                    fx0, fy0, fx1, fy1 = max(found, key=lambda f: f[1])[0]
                    face = bgr[max(0, fy0 - 40):fy1 + 40, max(0, fx0 - 40):fx1 + 40]
            emb = embed(face)
            fname = f"{r['sha256'][:16]}.jpg"
            cv2.imwrite(str(FACES / fname), face, [cv2.IMWRITE_JPEG_QUALITY, 92])
            rec.face_image_path = str((FACES / fname).relative_to(ROOT))
            if emb:
                rec.face_embedding_json = json.dumps(emb)
                embeddings[r["sha256"]] = np.asarray(emb)
        records.append(rec)
        print(f"{rec.document_type:24s} {rec.record_status:15s} face={'yes' if rec.face_image_path else 'no ':3s} "
              f"emb={'yes' if rec.face_embedding_json else 'no'}  {r['file'][:40]}", flush=True)

    db.add_all(records)
    db.commit()
    # Portrait -> most similar document face: a suggestion with its score only.
    docs = [x for x in records if x.document_type != "PORTRAIT" and x.source_sha256 in embeddings]
    for p in [x for x in records if x.document_type == "PORTRAIT" and x.source_sha256 in embeddings]:
        best = max(docs, key=lambda d: float(np.dot(embeddings[p.source_sha256], embeddings[d.source_sha256])), default=None)
        if best is not None:
            sim = float(np.dot(embeddings[p.source_sha256], embeddings[best.source_sha256]))
            if sim >= LINK_THRESHOLD:
                p.linked_record_id, p.link_similarity = best.id, round(sim, 3)
    db.commit()

    export = [{c.name: getattr(x, c.name) for c in DatasetRegistryRecord.__table__.columns
               if c.name not in ("face_embedding_json",)} for x in records]
    for e in export:
        e["id"] = str(e["id"])
        e["linked_record_id"] = str(e["linked_record_id"]) if e["linked_record_id"] else None
        e["created_at"] = None
    (DATA / "registry_export.json").write_text(json.dumps(
        {"data_classification": "REAL_SAMPLE_TEST_FIXTURE — local only, never commit or deploy", "records": export},
        indent=1, ensure_ascii=False))
    from collections import Counter
    print("records:", len(records), dict(Counter(x.record_status for x in records)),
          "faces:", sum(1 for x in records if x.face_image_path),
          "embeddings:", sum(1 for x in records if x.face_embedding_json),
          "portrait links:", sum(1 for x in records if x.linked_record_id))
    db.close()


if __name__ == "__main__":
    main()
