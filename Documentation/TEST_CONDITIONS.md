# PramaanAI — verification checklist and test-condition coverage

Legend — **A**: automated test (pytest / JUnit / synthetic evaluation case) ·
**E**: measured in `scripts/docverify/evaluate.py` (report in
`reports/docverify_evaluation.md`) · **P**: partially covered (limits stated) ·
**X**: not possible in this build (needs hardware, physical specimens or an
authorised service). Synthetic case ids refer to
`data/synthetic/docverify/ground_truth.json`.

## 1. OCR extraction

| Check | Where | Status |
|---|---|---|
| Document detected | `document_detected` (YOLO11n `document` class) | A, E (held-out real P/R) |
| Image sufficiently clear | `image_quality` (sharpness, brightness, clipping, glare, resolution) | A (TST-014), E (robustness) |
| Required text regions detected | `ocr` key-field check per document type | A |
| Name / number / nationality / DOB / gender / issue / expiry | `fields.py` label extraction; MRZ values when check digits pass | A (GEN-001 fields), E (OCR field accuracy; real passports vs validated MRZ) |
| Visa number / type / entry-validity | `fields.py` (`visa_number`, `visa_type`, `valid_from`, `date_of_expiry`, `entries`, `duration`) | A (GEN-002) |
| MRZ detected | `mrz_structure` | A |
| OCR confidence above threshold | `ocr_confidence` (75%) | A |
| OCR bounding boxes available | every `OcrLine`/`FieldValue` has `bbox`; `ocr_confidence.details.bounding_boxes` | A |

## 2. Document validation

| Check | Where | Status |
|---|---|---|
| Document-number format | `field_format` (template regex; Indian DL state code) | A |
| Nationality code valid | `nationality_code` (ISO 3166-1 alpha-3 + ICAO Doc 9303 codes) | A |
| Date formats valid / DOB / issue / expiry valid | `fields.normalize_date` + `date_logic` | A |
| Visa number format | `field_format` for visas | A |
| Required fields present | `ocr` | A |
| Issue > DOB, expiry > issue | `date_logic` | A |
| Not expired | `document_validity` | A (TST-004) |
| MRZ structure / check digits | `mrz_structure`, `mrz_check_digits` | A (TST-018, TST-032, TST-040) |
| MRZ ↔ visual number / DOB / expiry / nationality / name | `mrz_consistency` | A (TST-001, TST-016, TST-017) |
| Registry: exists / name / DOB / number / nationality | `registry`, `registry_consistency` | A (GEN-001, TST-003, TST-030) |
| Not reported lost/stolen, not blacklisted | watchlist (EXACT document-number hits) in `registry` | P (mock watchlist only) |
| Conflicting registry records | `registry` → `conflicting_registry_records` | A (unit test) |

## 3. Tampering / forgery

| Check | Where | Status |
|---|---|---|
| Text region abnormal compression / noise / sharpness | text fields vs the document's other text fields, ≥3 methods must agree | A (TST-012), E |
| Character edges / font / spacing inconsistency | not implemented as a separate model | X/P (covered only indirectly by sharpness/noise peers) |
| Erased/replaced text, copy-paste | peer comparison + exact-duplicate search | P |
| Photo region exists / boundaries / compression-noise consistency | `photo`, photo forensics (≥2 methods; sharper/noisier only) | P (TST-011 — see evaluation for current result) |
| Face region plausible for template | `photo` (position/size vs template), `document_proportions` | A (TST-019) |
| Stamp detected / location / geometry vs reference | `stamp_detection`, `stamp_reference` | A (TST-007, TST-022) |
| Stamp copy-paste duplication / ink-image consistency | `stamp_forensics` (duplicates always; ≥3 methods) | A (TST-023) |
| Stamp text readable | `stamp_identification`, `authority_identification` | A |
| EXIF / editing-software metadata | `forensics.metadata_indicators` (missing metadata is never a finding) | P |
| Compression checked / aspect ratio | forensics error-level + JPEG grid; `document_proportions` | A |
| Multiple signals combined | consensus rule + decision engine | A |

## 4. Face verification

| Check | Where | Status |
|---|---|---|
| Face in document photo, exactly one, large, clear, landmarks | `photo`, `document_face_quality` (5 landmarks, size, blur, contrast) | A |
| Live face detected / exactly one | `_live_capture_checks` → retake | A (unit test, TST-034) |
| Embedding + similarity + threshold | InsightFace provider (threshold 0.5) | A (TST-020/021), E (78 synthetic pairs) |
| Poor quality → inconclusive, not mismatch | `LOW_QUALITY` → NOT_VERIFIED | A (TST-034) |
| Live vs authorised reference photo | `verify_faces` reference pairs; registry reference photo (`reference_photo_match`) | A (TST-039) |
| Synthetic/manipulated-face indicators | `face_manipulation_indicators` (existing heuristic provider, advisory) | P (heuristic, not a trained detector) |

## 5. The 60 test conditions

| # | Condition | Coverage |
|---|---|---|
| 1–5 | Genuine passport / visa / Aadhaar-type / DL / permit | A: GEN-001…GEN-005 |
| 6 | Digitally altered | A: TST-012, TST-023 |
| 7 | Physically tampered | X: needs physical specimens |
| 8 | Replaced photograph | A: TST-011 |
| 9–12 | Modified name / DOB / number / nationality | A: TST-016, TST-003, TST-001, TST-030 |
| 13–14 | Modified expiry / expired | A: TST-017, TST-004 |
| 15 | Unregistered number | A: TST-025 |
| 16–18 | OCR↔DB / OCR↔MRZ / OCR↔QR mismatch | A: TST-003, TST-001, TST-005 |
| 19–20 | Valid / damaged QR | A: GEN-003, TST-031 |
| 21–22 | Missing MRZ / invalid check digit | A: TST-032, TST-018 |
| 23–25 | Correct / moved / missing photo | A: GEN-001, TST-019, TST-033 |
| 26–28 | Face match / mismatch / low-quality live | A: TST-021, TST-020, TST-034 |
| 29–30 | Genuine / unknown stamp | A: TST-007, TST-008 |
| 31–33 | Stamp text / checkpoint / date inconsistency | A: TST-010, TST-035 |
| 34–35 | Multiple / overlapping-faded stamps | E: robustness (`overlapping_rotated_stamps`, `faded_stamp`) |
| 36–38 | Indian / Nepal / Bhutan markings | A: TST-037, TST-007, TST-038 |
| 39–40 | Land-border checkpoint / unexpected checkpoint | A: TST-009, TST-036 |
| 41 | Missing expected marking | A: TST-027, TST-029 (treaty rules: not flagged) |
| 42–44 | Security feature present / missing / DL yellow-gold | A: GEN-003, unit tests |
| 45 | Abnormal layout | A: TST-019 |
| 46–47 | Digital signature / visual signature only | A: GEN-003, TST-024, TST-041 |
| 48–50 | Record exists / missing / conflicting | A: GEN-001, TST-025, unit test |
| 51–52 | Live vs reference match / mismatch | A: TST-021, TST-039 |
| 53 | Multiple faces in live image | A: unit test |
| 54–58 | Blur / rotation / lighting / glare / cropped | E: robustness; A: rotation + glare unit tests, TST-040 |
| 59 | Clear high-resolution | E: robustness `clear` |
| 60 | Unsupported document | A: real dataset portraits → "Unsupported or unrecognised document" |

## 6. Security

| Condition | Test |
|---|---|
| Invalid / expired JWT, deactivated account | `test_docverify_security.py` |
| Wrong RBAC role (forged role claim) | `test_field_officer_cannot_make_reviewer_decisions`, `test_cases.py` |
| Invalid request, malformed / oversized / unsupported file | `test_docverify_security.py`, `test_docverify_api.py` |
| Duplicate request (idempotency) | `test_idempotent_retry_returns_the_same_record` |
| Audit-log creation | `test_audit_event_is_written_for_every_verification` |
| Hash-chain integrity + tamper detection | `test_extracted_path_persists_with_valid_chain…`, `test_tampering_with_a_stored_record_breaks_the_chain`, `test_concurrent_appends_keep_the_chain_intact` |
| Password hashing (Argon2) | `test_passwords_are_stored_as_argon2_hashes` |
| Sensitive-data restrictions | `test_sensitive_data_is_minimised` (Aadhaar masked, no biometric vectors, summary-only listing) |
| HTTPS | P: deployment (Render terminates TLS; HSTS header set by the app) — not testable in unit tests |

## 7. Offline (Android)

| Condition | Coverage |
|---|---|
| Online → normal verification; server busy (503) → saved, retried | implemented in `DocVerifyRepository`; P (needs a device/emulator run) |
| Offline → encrypted local save (Android Keystore AES-GCM) + WorkManager sync | implemented; P (device run) |
| Duplicate queued request | A (server idempotency test); device reuses `client_request_id` |
| On-device MRZ check digits | A: `MrzCheckTest` (JUnit, 4 tests incl. ICAO worked example) |
| No full image leaves the phone | A: server rejects crops covering >90% (`test_region_crops_covering_whole_document_are_rejected`) |
