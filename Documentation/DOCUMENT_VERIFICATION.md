# Modular document verification (`/api/v1`)

Decision-support pipeline for SSB officers at India–Nepal and India–Bhutan land
borders. **It never declares a document fake or genuine.** Every check returns
one of `PASS · REVIEW_REQUIRED · NOT_VERIFIED · REGISTRY_NOT_AVAILABLE ·
OFFICIAL_VERIFICATION_REQUIRED · REFERENCE_NOT_AVAILABLE · NOT_APPLICABLE ·
FAIL`, with the evidence (image regions, compared values) and a plain-language
reason. The authorised officer records the decision.

The existing screening pipeline (`/documents/screen`, cases, dashboard) is
unchanged; this is an additional, modular path.

## Architecture

```
Android app                                  FastAPI backend (app/services/docverify)
 CameraX / gallery                            ┌────────────────────────────────────────────┐
 YOLO11n (ONNX Runtime, on device) ──────┐    │ canvas from region crops (never full image) │
   document · photograph · mrz · qr_code │    │ PP-OCR (PaddleOCR weights, ONNX runtime)    │
   barcode · stamp · yellow_gold_feature │    │ MRZ: TD1/TD2/TD3/MRV-A/MRV-B + check digits │
 ML Kit text blocks (printed fields)     ├──► │ QR/barcode: OpenCV decoders                 │
 padded region crops (≤85% of frame)     │    │ document type (MRZ + text + regions)        │
 offline: encrypted queue + WorkManager  │    │ fields, photo/face (InsightFace)            │
   + on-device MRZ check digits / QR ────┘    │ layout templates, security features         │
                                              │   incl. yellow/gold VISUAL feature          │
Web dashboard (Document Verification page)    │ stamps → checkpoint reference               │
 uploads 1–4 images → /api/v1/verify/document │ region forensics (consensus of methods)     │
                                              │ digital signatures (cryptography)           │
                                              │ registries (mock) / official adapters       │
                                              │ consistency engine · border rules           │
                                              │ decision engine + risk score + summary      │
                                              └──────────────┬─────────────────────────────┘
                                                             ▼
                                   document_verifications (hash-chained, HMAC-signed)
                                   document_verification_checks · audit_events
```

| Stage | Implementation | File |
|---|---|---|
| Region detection | YOLO11n trained here (`models/yolo/pramaan_regions_yolo11n.pt`); classical OpenCV fallback | `detection.py` |
| OCR | Existing PP-OCR engine (PaddleOCR det+rec weights via RapidOCR/ONNX); page + upscaled region OCR, bbox + confidence per line | `ocr.py` |
| Fields | Label-anchored, spacing/noise tolerant, typed validators; Aadhaar numbers masked to last 4 | `fields.py` |
| MRZ | ICAO 9303 TD1/TD2/TD3/MRV-A/MRV-B, field-class OCR correction (reported), recomputed check digits | `mrz.py` |
| Machine-readable codes | OpenCV `QRCodeDetector` (multi/single, 3 image variants), `barcode.BarcodeDetector`, re-decode on detector crops | `machine_readable.py` |
| Document type | MRZ code + keywords + regions; `DOCUMENT_TYPE_UNCERTAIN` below 0.55 | `doc_type.py` |
| Photo / face | Face-in-photo, position/size vs template, multiple faces; InsightFace match (MATCH / NO_MATCH / LOW_QUALITY / NOT_VERIFIED) | `photo.py` |
| Layout + security | Template anchors, guilloche/hologram indicators, UV/microprint = NOT_VERIFIED, electronic chip = never read | `security_features.py` |
| Yellow/gold feature | Colour+shape+position+size+orientation+texture vs DL template → `VISUAL_SECURITY_FEATURE` evidence, never a verdict | `security_features.py` |
| Stamps | Detected region → OCR → type/authority/country/direction/date → official checkpoint reference; geometry vs visual reference (`REFERENCE_NOT_AVAILABLE` for real stamps) | `stamps.py` |
| Forensics | Region vs surroundings: sharpness, noise, error level, JPEG grid, duplicates, metadata; flagged only when ≥2 methods agree (≥3 for ink: text, stamps); ink regions measured on paper only; per-family method applicability | `forensics.py` |
| Signatures | Visual signature ≠ cryptographic signature; Ed25519 verification vs trust store; PDF/PAdES → NOT_VERIFIED without pyhanko + roots; UIDAI Secure QR → official only | `signatures.py` |
| Registries | Mock DL / visa / permit registries, existing mock citizen registry + watchlist; Aadhaar + ePassport = official adapters (not configured) | `registries.py` |
| Consistency | OCR↔MRZ, OCR↔QR, OCR↔registry, passport↔visa/permit, doc↔doc, stamp↔visa validity, stamp↔checkpoint, expiry↔date | `consistency.py` |
| Border rules | Separate, versioned, date-aware India–Nepal / India–Bhutan configs | `border_rules.py` |
| Decision | Status precedence; FAIL only with ≥2 independent strong failures; explained 0–100 risk score | `decision.py` |
| VLM (optional) | OpenAI-compatible endpoint (Qwen-VL/Gemini); advisory text only | `vlm.py` |

## API

All endpoints require a JWT (`OFFICER` or `REVIEWER`). Uploads: JPEG/PNG/WEBP,
≤10 MB, ≤40 MP, 1–4 images. Images and crops sent for verification are
processed in memory and not stored by the verify endpoints (only SHA-256
hashes). Evidence images are stored separately, and only when the app uploads
them to an opened case (see *Cases, evidence and admin review* below).

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/verify/document` | 1–4 images (multipart `files`), optional `live_face`, `reference_face`, `border_route`, `direction`, `declared_nationality`, `travel_date` |
| POST | `/api/v1/verify/passport` · `/visa` · `/driving-licence` · `/aadhaar` · `/stamp` | Single image (`file`); DL/Aadhaar also flag a type mismatch |
| POST | `/api/v1/verify/regions` | **Device path**: JSON region crops from on-device YOLO (rejected if crops cover >90% of the frame) |
| POST | `/api/v1/verify/extracted` | Device path: extracted data only (fields, MRZ text, decoded codes, stamp text) |
| POST | `/api/v1/verify/face` | Document photo vs presented person / authorised reference (no embeddings returned) |
| GET | `/api/v1/checkpoints?country=&border=` | Official-source checkpoint reference + dataset version |
| GET | `/api/v1/reference/rules/{INDIA_NEPAL\|INDIA_BHUTAN}` | Border-rule configuration |
| GET | `/api/v1/verification?limit=&mine=` | Recent verifications (summary only) |
| GET | `/api/v1/verification/{id}` | Stored result + integrity (`hash_valid`, `signature_valid`) |
| POST | `/api/v1/verification/{id}/officer-action` | `CLEARED` · `SEND_TO_OFFICER` (shown as "Send to admin") · `REFERRED_FOR_SECONDARY_INSPECTION` · `RECAPTURE_REQUESTED` · `OFFICIAL_VERIFICATION_REQUESTED` (reason required unless CLEARED) |
| GET | `/api/v1/verification/by-case/{case_id}` | The verification linked to a case (used by the web case review) |
| GET | `/api/v1/verification/chain/verify` | Walk the local tamper-evident hash chain |
| GET | `/api/v1/status` | Instance load (running / waiting / limits), active region detector, reference-data version |

Response (abridged):

```json
{
  "id": "…", "overall_status": "REVIEW_REQUIRED", "document_type": "INDIAN_PASSPORT", "country": "INDIA",
  "confidence": 0.86, "explanation": "Expiry date on printed text (2033-05-09) differs from MRZ (2031-05-09)",
  "risk_score": 20, "risk_level": "LOW", "risk_breakdown": [{"check": "mrz_consistency", "points": 20, "reason": "…"}],
  "checks": {"ocr": "PASS", "mrz_check_digits": "PASS", "mrz_consistency": "REVIEW_REQUIRED", "registry": "PASS",
             "photo": "PASS", "tampering_analysis": "PASS", "epassport_chip": "NOT_VERIFIED"},
  "check_details": [{"name": "…", "status": "…", "summary": "…", "blocking": true, "evidence_ids": ["ev-3"]}],
  "evidence": [{"id": "ev-3", "check": "mrz_consistency", "description": "…", "bbox": [x0, y0, x1, y1]}],
  "flags": ["date_of_expiry_mismatch"],
  "officer_summary": {"headline": "REVIEW REQUIRED", "facts": {"Country": "India", "…": "…"},
                      "lines": [{"icon": "ok", "text": "Text extracted"}, {"icon": "warn", "text": "…"}]},
  "data_notice": "Registry lookups in this build use FICTIONAL mock data only …"
}
```

## Device ↔ server contract and scaling

* **Lightweight phone, heavy server.** The app runs only YOLO11n (10.6 MB ONNX,
  ONNX Runtime) to locate regions and ML Kit to find printed-text blocks, then
  sends **one HTTPS request** (`POST /api/v1/verify/regions`) carrying every
  padded crop of the capture. PaddleOCR, MRZ, QR/barcode, stamps, face,
  forensics, registries and the decision engine all run on the server, which
  returns one structured result (extracted data, per-check status, issues,
  evidence boxes, confidence, final status).
* **Concurrency.** Endpoints are async; each pipeline runs in a worker thread
  under a capacity limiter (`PRAMAAN_MAX_CONCURRENT_VERIFICATIONS`, default
  half the cores, max 4) with a bounded wait queue
  (`PRAMAAN_MAX_QUEUED_VERIFICATIONS`, default 16). When saturated the API
  answers **503 + Retry-After** instead of degrading everyone; the Android app
  then keeps the capture in its encrypted queue and WorkManager retries.
  OCR engines and YOLO models are per-thread; the shared MediaPipe detector is
  serialised. Each PP-OCR engine uses `PRAMAAN_OCR_THREADS` ONNX Runtime
  threads (default 0 = half the cores, max 4). RapidOCR's own default of every
  core oversubscribed the CPU and was ~2x slower with identical output.
* **Horizontal scaling.** No per-request state is kept in memory and the
  verify endpoints do not store images, so more `uvicorn` workers (`PRAMAAN_WORKERS` in
  `docker-entrypoint.sh`, ~1–1.5 GB RAM each) or more instances behind a load
  balancer scale it out. `GET /api/v1/status` reports per-instance load.
* **Idempotency.** `client_request_id` (the offline queue item id) makes
  retries safe: a repeated request returns the stored result, never a
  duplicate record.
* **Chain under concurrency.** `sequence` is unique; a writer that loses the
  race rolls back and re-appends on the new head (also retries SQLite
  "database is locked"), so concurrent workers/instances keep one unbroken
  chain (tested with 6 parallel requests on a pooled file database).

## Database (migration `0017`)

* `document_verifications` — one row per run (unique `sequence`, unique nullable `client_request_id`): source (`SERVER_IMAGE`/`DEVICE_REGIONS`/`DEVICE_EXTRACTED`), statuses, risk, masked result JSON (no raw OCR dump, no images), input SHA-256s, reference-data version, offline/sync flags, officer action, `prev_hash` → `record_hash` chain + HMAC signature.
* `document_verification_checks` — one row per check with its evidence (queryable).
* `reference_data_snapshots` — manifest (file hashes, data classification) of each reference-data version a result was checked against.
* Audit: `audit_events` rows `DOCVERIFY_CREATED` / `DOCVERIFY_VIEWED` / `DOCVERIFY_OFFICER_ACTION`.

The hash chain is a **local** tamper-evident log, not a blockchain.

## Cases, evidence and admin review (migrations `0019`–`0021`)

* `POST /verify/regions` with `open_case: true` (the app's default) also opens
  a case: a `cases` row, a `CREATED` audit event, and the identity links
  (face-embedding cluster, same document number seen under another name).
  `document_verifications` gains `case_id`, `screening_verification_id` and
  `identity_json` (migration `0020`).
* The result carries `suggested_reasons` (`clear` / `send`) that are written
  from the checks. The officer can edit them before deciding.
* **Clear** → `record_decision CLEAR`. **Send to admin** (`SEND_TO_OFFICER`)
  → a note, the case set to `SENT`, and a `SENT` audit event. The admin answers
  from the web console, and the answer shows in the app under Review and
  Notifications. A second decision on a closed case returns `409`.
* **Evidence images.** After verifying, the app uploads the document image
  and the live face crop to `POST /images/{screening_verification_id}/upload`
  (`document_front`, `selfie`). This lets the admin and the officer's
  Review/History see the original document with the problem boxes and the live
  photo. The region crops used for verification are still not stored.
* `post_checkpoint`: the officer's assigned post fills the border route when
  no stamp gives one. The facts show where the value came from ("from stamp" /
  "your post" / "Not determined — choose the crossing").
* SQLite-only fixes: `0019` makes `audit_events.verification_id` nullable
  (the `0009` alter was a no-op on SQLite). `0021` gives `stored_images` a
  working `now()` default.

## Reference data (`reference_data/`)

```
india/{passport,visa,driving_licence,aadhaar}/templates.json   layout + feature descriptors
india/checkpoints/{india_nepal_border,india_bhutan_border,stamps}.json
nepal/{passport,visa}/templates.json, nepal/checkpoints/, nepal/immigration_stamps/
bhutan/{passport,visa,permits}/templates.json, bhutan/checkpoints/, bhutan/immigration/
rules/india_nepal.json, rules/india_bhutan.json                 versioned, date-aware
mock_registries/{driving_licence,travel_authorisations}.json    FICTIONAL
synthetic_references/stamp_visual_references.json               SYNTHETIC test geometry
trust/synthetic_issuers.json                                    SYNTHETIC test signer key
```

Template feature record: `country, document_type, version, validity_period,
official_reference, layout_anchors, features[{feature_name, expected_region
[x0,y0,x1,y1 relative], verification_method, expected_text_patterns,
visually_checkable}], field_patterns`. Checkpoint record: `checkpoint_id,
country, checkpoint_name, aliases, border_country, checkpoint_type, region,
authority, foreigner_immigration_point, paired_checkpoint_id, active_from,
active_to, reference_source[{title,url,retrieved}]` — sources are the Consulate
General of India Birgunj list, Nepal Department of Immigration and Consulate
General of India Phuentsholing. Unknown dates are `null`, never guessed. No
security artwork is stored.

## Training data (YOLO11 region detector)

* Real images: `data/dataset_1/Dataset` (not committed — personal data),
  `labels.json` (document type/country), `boxes.json` (`{file: [{cls, box:[x0,y0,x1,y1] relative}]}`).
* Built dataset: `data/yolo/docverify/{images,labels}/{train,val}` in YOLO txt
  format (`class cx cy w h`, normalised), `dataset.yaml`, `split.json`.
  Train = real (≈70%, split by SHA-256) + 300 domain-randomised synthetic
  documents; **val = held-out real images only**.
* Classes: `document, photograph, mrz, qr_code, barcode, stamp, yellow_gold_feature`.

## Configuration

See `.env.example`: `PRAMAAN_REFERENCE_DATA_DIR`, `PRAMAAN_YOLO_WEIGHTS`
(empty → trained weights if present; `none` → classical), `PRAMAAN_YOLO_CONF`,
`PRAMAAN_DL_REGISTRY_MODE` / `PRAMAAN_TRAVEL_REGISTRY_MODE` (`mock`|`disabled`),
`PRAMAAN_VLM_*`. Server-side YOLO needs `requirements-yolo.txt` (CPU torch +
ultralytics); without it the classical detector is used and every result says so.

## Run and test

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pip install -r requirements-yolo.txt --extra-index-url https://download.pytorch.org/whl/cpu  # optional
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload            # API + /docs
(cd frontend && npm install && npm run dev)         # console → Document Verification
(cd android && ./gradlew :app:assembleDebug)        # app → More → Document verification

# tests
.venv/bin/python -m pytest tests/test_docverify_services.py tests/test_docverify_api.py -q

# synthetic test set + evaluation (writes reports/docverify_evaluation.{json,md})
.venv/bin/python -m scripts.docverify.generate_synthetic_testset
.venv/bin/python -m scripts.docverify.evaluate

# YOLO: build dataset, train (CPU), export ONNX for Android
.venv/bin/python -m scripts.docverify.yolo.build_dataset --synthetic 300
.venv/bin/python -m scripts.docverify.yolo.train --epochs 60
.venv/bin/python -m scripts.docverify.yolo.export

# forensic threshold calibration on presumed-genuine real captures
.venv/bin/python -m scripts.docverify.calibrate_forensics
```

## Needs authorised external services before real deployment

* Real registries (passport, visa, permit, driving licence) — only mock adapters exist.
* UIDAI Aadhaar Secure QR verification — always `OFFICIAL_VERIFICATION_REQUIRED`.
* ePassport chip reading + ICAO PKD trust chain — always `NOT_VERIFIED`.
* Issuer certificates for digital signatures (only a synthetic test key is configured); PAdES needs `pyhanko`.
* Authoritative stamp artwork/geometry references — real stamps return `REFERENCE_NOT_AVAILABLE`.
* Re-validation of checkpoint and border-rule data against current official notifications.
