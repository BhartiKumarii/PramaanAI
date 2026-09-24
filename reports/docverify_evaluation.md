# Document-verification evaluation

Generated 2026-09-24T03:04:23+00:00. **Synthetic results are measured on documents this project generated itself, with layouts matching its own templates — they are optimistic and are not evidence of real-world accuracy.**

## Synthetic suite

| Module | n | Accuracy | Precision | Recall | F1 | FPR | FNR |
|---|---|---|---|---|---|---|---|
| Complete pipeline (attention required) | 46 | 0.891 | 0.939 | 0.912 | 0.925 | 0.167 | 0.088 |
| Validation | 25 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 |
| Tampering | 46 | 0.935 | 0.5 | 0.333 | 0.4 | 0.023 | 0.667 |
| Face (end-to-end cases) | 3 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 |
| Face (all synthetic pairs) | 78 | 0.538 | 1.0 | 0.455 | 0.625 | 0.0 | 0.545 |

- OCR field accuracy (synthetic): 18/18 = 1.0
- Document-type accuracy (synthetic): 0.963
- Overall status matches expectation: 0.891
- Expected check-level outcomes: 53/56

| Case | Expected | Got | Risk | OK |
|---|---|---|---|---|
| GEN-001 Genuine synthetic Indian passport (matching mock registry record) | PASS | PASS | 0 | yes |
| GEN-002 Genuine synthetic Nepal visa with passport and Kakarbhitta arrival sta | PASS | PASS | 5 | yes |
| GEN-003 Genuine synthetic Indian driving licence (signed QR, yellow/gold visua | PASS | PASS | 5 | yes |
| GEN-004 Genuine synthetic Bhutan entry permit (signed QR, mock registry ISSUED | PASS | PASS | 10 | yes |
| GEN-005 Synthetic Aadhaar-like card: must route to official verification, neve | OFFICIAL_VERIFICATION_REQUIRED/REVIEW_REQUIRED | REVIEW_REQUIRED | 17 | yes |
| TST-001 OCR/MRZ mismatch: printed passport number differs from MRZ | REVIEW_REQUIRED/FAIL | REVIEW_REQUIRED | 20 | yes |
| TST-002 Passport/visa mismatch: visa quotes a different passport number | REVIEW_REQUIRED | REVIEW_REQUIRED | 25 | yes |
| TST-003 DOB mismatch: printed DOB differs from the (mock) registry record | REVIEW_REQUIRED | REVIEW_REQUIRED | 25 | yes |
| TST-004 Expired document | REVIEW_REQUIRED/FAIL | REVIEW_REQUIRED | 35 | yes |
| TST-005 QR/OCR mismatch: unsigned QR DOB differs from printed DOB | REVIEW_REQUIRED | REVIEW_REQUIRED | 25 | yes |
| TST-006 Missing QR on a template version that carries one | REVIEW_REQUIRED | PASS | 5 | NO |
| TST-007 Stamp detection: Nepal immigration arrival stamp, Kakarbhitta | PASS | NOT_VERIFIED | 6 | NO |
| TST-008 Unknown stamp: impression with no identifiable authority, checkpoint o | REVIEW_REQUIRED/NOT_VERIFIED | REVIEW_REQUIRED | 18 | yes |
| TST-009 Land-border checkpoint match: Birgunj (India–Nepal) arrival stamp | PASS | PASS | 0 | yes |
| TST-010 Checkpoint mismatch: stamp says NEPAL immigration but names an Indian  | REVIEW_REQUIRED | REVIEW_REQUIRED | 20 | yes |
| TST-011 Synthetic photo replacement: portrait swapped with a re-compressed, no | REVIEW_REQUIRED | PASS | 0 | NO |
| TST-012 Image manipulation: DOB text region overwritten with a pasted, re-comp | REVIEW_REQUIRED | PASS | 5 | NO |
| TST-013 Registry unavailable: genuine licence, DL registry disabled | REGISTRY_NOT_AVAILABLE | REGISTRY_NOT_AVAILABLE | 5 | yes |
| TST-014 Poor-quality image: blurred, dark, low resolution | NOT_VERIFIED | NOT_VERIFIED | 24 | yes |
| TST-015 Offline verification: genuine passport verified with no connectivity | REGISTRY_NOT_AVAILABLE | REGISTRY_NOT_AVAILABLE | 0 | yes |
| TST-016 Name mismatch: printed surname differs from MRZ | REVIEW_REQUIRED | REVIEW_REQUIRED | 20 | yes |
| TST-017 Expiry mismatch: printed expiry differs from MRZ | REVIEW_REQUIRED | REVIEW_REQUIRED | 20 | yes |
| TST-018 MRZ mismatch: DOB check digit does not validate | REVIEW_REQUIRED/FAIL | REVIEW_REQUIRED | 12 | yes |
| TST-019 Photo-position anomaly: portrait printed where the template expects te | REVIEW_REQUIRED | REVIEW_REQUIRED | 17 | yes |
| TST-020 Face mismatch: presented person differs from the passport photo | REVIEW_REQUIRED | REVIEW_REQUIRED | 12 | yes |
| TST-021 Face match control: presented person is the passport holder (different | PASS | PASS | 0 | yes |
| TST-022 Stamp-reference mismatch: Kakarbhitta arrival stamp with geometry unli | REVIEW_REQUIRED | REVIEW_REQUIRED | 18 | yes |
| TST-023 Stamp image-forensics anomaly: stamp pasted as a re-compressed patch a | REVIEW_REQUIRED | REVIEW_REQUIRED | 24 | yes |
| TST-024 Digital-signature failure: signed QR data altered after signing | REVIEW_REQUIRED/FAIL | REVIEW_REQUIRED | 60 | yes |
| TST-025 Unregistered document: well-formed licence with no record in the mock  | NOT_VERIFIED | NOT_VERIFIED | 11 | yes |
| TST-026 Multiple simultaneous inconsistencies: expired + MRZ check digit + DOB | FAIL/REVIEW_REQUIRED | REVIEW_REQUIRED | 87 | yes |
| TST-027 India–Nepal treaty national: Indian passport, no visa/stamp — must NOT | PASS | PASS | 0 | yes |
| TST-028 India–Nepal third-country national without the required Nepal visa | REVIEW_REQUIRED | REVIEW_REQUIRED | 24 | yes |
| TST-029 India–Bhutan (post-2022 rules): Indian passport, no physical stamp — m | PASS | PASS | 0 | yes |
| TST-030 Modified nationality: document says NEPALI, the (mock) registry record | REVIEW_REQUIRED | REVIEW_REQUIRED | 20 | yes |
| TST-031 Damaged/unreadable QR: part of the code is covered | NOT_VERIFIED/REVIEW_REQUIRED | NOT_VERIFIED | 11 | yes |
| TST-032 Missing MRZ on a passport data page | NOT_VERIFIED/REVIEW_REQUIRED | NOT_VERIFIED | 6 | yes |
| TST-033 Missing photo: licence with an empty photo area | REVIEW_REQUIRED/NOT_VERIFIED | REVIEW_REQUIRED | 17 | yes |
| TST-034 Low-quality live face capture: blurred, dark, tiny — retake, not a mis | NOT_VERIFIED | NOT_VERIFIED | 6 | yes |
| TST-035 Stamp date inconsistency: entry stamped before the visa's validity beg | REVIEW_REQUIRED | REVIEW_REQUIRED | 25 | yes |
| TST-036 Unexpected checkpoint: foreigner stamped at a post not designated for  | REVIEW_REQUIRED | REVIEW_REQUIRED | 17 | yes |
| TST-037 Indian immigration marking (Raxaul) identified from text + checkpoint  | PASS | NOT_VERIFIED | 6 | NO |
| TST-038 Bhutan immigration marking (Phuentsholing) identified from text + chec | PASS | PASS | 0 | yes |
| TST-039 Live face matches the document, but the authorised reference photo sho | REVIEW_REQUIRED | REVIEW_REQUIRED | 12 | yes |
| TST-040 Cropped document: right side and part of the MRZ outside the frame | NOT_VERIFIED/REVIEW_REQUIRED | REVIEW_REQUIRED | 12 | yes |
| TST-041 Visual signature only: an image of a signature is not treated as a dig | PASS | PASS | 0 | yes |

## Robustness (synthetic documents under different capture conditions)

Document type correct in 100% of variants; processing time mean 4.69s, max 12.1s (server CPU).

| Subject | Condition | Status | Type ok | Det. conf | OCR conf | Face | Stamps id | Quality | Rot. | s |
|---|---|---|---|---|---|---|---|---|---|---|
| passport | clear | REGISTRY_NOT_AVAILABLE | yes | 0.982 | 0.9758 | yes | 0 | PASS |  | 6.56 |
| passport | low_resolution | REVIEW_REQUIRED | yes | 0.98 | 0.9072 | yes | 0 | PASS |  | 5.9 |
| passport | blur | REVIEW_REQUIRED | yes | 0.966 | 0.9647 | yes | 0 | REVIEW_REQUIRED |  | 3.79 |
| passport | rotation_5deg | REGISTRY_NOT_AVAILABLE | yes | 0.98 | 0.9668 | yes | 0 | PASS |  | 8.04 |
| passport | rotation_90deg | REVIEW_REQUIRED | yes | 0.982 | 0.9739 | yes | 0 | PASS | 90 | 12.1 |
| passport | rotation_180deg | REVIEW_REQUIRED | yes | 0.752 | 0.9748 | no | 0 | PASS |  | 3.55 |
| passport | dark | REVIEW_REQUIRED | yes | 0.978 | 0.9658 | yes | 0 | PASS |  | 3.25 |
| passport | bright | REGISTRY_NOT_AVAILABLE | yes | 0.954 | 0.9814 | yes | 0 | REVIEW_REQUIRED |  | 3.69 |
| passport | shadow | REVIEW_REQUIRED | yes | 0.984 | 0.9723 | yes | 0 | PASS |  | 3.73 |
| passport | glare | REGISTRY_NOT_AVAILABLE | yes | 0.98 | 0.978 | yes | 0 | PASS |  | 4.38 |
| passport | low_quality_camera | REVIEW_REQUIRED | yes | 0.859 | 0.9725 | yes | 0 | PASS |  | 4.61 |
| driving_licence | clear | PASS | yes | 0.962 | 0.9486 | yes | 0 | REVIEW_REQUIRED |  | 2.56 |
| driving_licence | low_resolution | NOT_VERIFIED | yes | 0.968 | 0.8958 | yes | 0 | REVIEW_REQUIRED |  | 3.48 |
| driving_licence | blur | NOT_VERIFIED | yes | 0.961 | 0.9831 | yes | 0 | NOT_VERIFIED |  | 2.91 |
| driving_licence | rotation_5deg | PASS | yes | 0.967 | 0.9455 | yes | 0 | REVIEW_REQUIRED |  | 2.9 |
| driving_licence | rotation_90deg | REVIEW_REQUIRED | yes | 0.508 | 0.9543 | yes | 0 | REVIEW_REQUIRED |  | 8.51 |
| driving_licence | rotation_180deg | REVIEW_REQUIRED | yes | 0.852 | 0.9453 | yes | 0 | REVIEW_REQUIRED |  | 2.14 |
| driving_licence | dark | PASS | yes | 0.957 | 0.9492 | yes | 0 | PASS |  | 1.95 |
| driving_licence | bright | PASS | yes | 0.964 | 0.9606 | yes | 0 | REVIEW_REQUIRED |  | 1.86 |
| driving_licence | shadow | PASS | yes | 0.954 | 0.9509 | yes | 0 | PASS |  | 1.87 |
| driving_licence | glare | PASS | yes | 0.964 | 0.9463 | yes | 0 | REVIEW_REQUIRED |  | 2.12 |
| driving_licence | low_quality_camera | PASS | yes | 0.917 | 0.9554 | yes | 0 | PASS |  | 2.21 |
| stamp_page | clear | NOT_VERIFIED | yes | 0.918 | 0.9912 | no | 1 | PASS |  | 4.69 |
| stamp_page | low_resolution | NOT_VERIFIED | yes | 0.944 | 0.9903 | no | 1 | PASS |  | 6.42 |
| stamp_page | blur | NOT_VERIFIED | yes | 0.878 | 0.9932 | no | 1 | NOT_VERIFIED | 180 | 9.49 |
| stamp_page | rotation_5deg | PASS | yes | 0.946 | 0.9683 | no | 1 | PASS |  | 6.26 |
| stamp_page | rotation_90deg | NOT_VERIFIED | yes | 0.92 | 0.9911 | no | 1 | PASS | 90 | 8.5 |
| stamp_page | rotation_180deg | NOT_VERIFIED | yes | 0.777 | 0.9913 | no | 1 | PASS |  | 7.88 |
| stamp_page | dark | PASS | yes | 0.964 | 0.9708 | no | 1 | PASS |  | 3.4 |
| stamp_page | bright | REVIEW_REQUIRED | yes | 0.94 | 0.9907 | no | 1 | REVIEW_REQUIRED |  | 4.65 |
| stamp_page | shadow | PASS | yes | 0.94 | 0.974 | no | 1 | PASS |  | 3.46 |
| stamp_page | glare | REVIEW_REQUIRED | yes | 0.944 | 0.9914 | no | 1 | PASS |  | 5.61 |
| stamp_page | low_quality_camera | PASS | yes | 0.948 | 0.9834 | yes | 1 | PASS |  | 5.23 |
| stamp_page | faded_stamp | REVIEW_REQUIRED | yes | 0.939 | 0.9736 | no | 1 | PASS |  | 3.36 |
| stamp_page | overlapping_rotated_stamps | PASS | yes | 0.792 | 0.9717 | no | 1 | PASS |  | 2.97 |

## Region detection on 21 held-out REAL images (IoU >= 0.5)

| Class | classical P / R | yolo11n P / R |
|---|---|---|
| barcode | None / 0.0 | None / 0.0 |
| document | None / 0.0 | 0.909 / 1.0 |
| mrz | 1.0 / 0.6 | 1.0 / 1.0 |
| photograph | 1.0 / 0.778 | 0.842 / 0.889 |
| qr_code | 0.333 / 0.25 | 0.5 / 0.75 |
| stamp | 0.222 / 0.308 | 0.8 / 0.615 |
| yellow_gold_feature | 0.833 / 0.714 | 1.0 / 1.0 |
| **overall** | 0.614 / 0.397 | 0.855 / 0.868 |

## Real dataset (data/dataset_1, not committed)

Labels: Claude (visual inspection of thumbnails) — PENDING USER CONFIRMATION. n = 57 (screenshots and duplicates excluded).

- Document-type accuracy: **0.877**
- Passport OCR vs the document's own validated MRZ: 12/18 = 0.667
- Overall status distribution: {'NOT_VERIFIED': 28, 'PASS': 6, 'REGISTRY_NOT_AVAILABLE': 1, 'REVIEW_REQUIRED': 22}

| Expected type | n | correct |
|---|---|---|
| AADHAAR | 1 | 1 |
| BHUTAN_ENTRY_PERMIT | 3 | 3 |
| DOCUMENT_TYPE_UNCERTAIN | 2 | 2 |
| DRIVING_LICENCE | 16 | 11 |
| FOREIGN_PASSPORT | 6 | 6 |
| IDENTITY_DOCUMENT | 6 | 6 |
| IMMIGRATION_STAMP | 1 | 1 |
| INDIAN_PASSPORT | 5 | 3 |
| INDIAN_VISA | 2 | 2 |
| NEPAL_VISA | 10 | 10 |
| OTHER_TRAVEL_DOCUMENT | 5 | 5 |

Misclassified:

- IMG_20260922_115655.jpg: expected INDIAN_PASSPORT, got FOREIGN_PASSPORT
- IMG_20260922_202625.jpg: expected DRIVING_LICENCE, got DOCUMENT_TYPE_UNCERTAIN
- IMG_20260922_202748.jpg: expected DRIVING_LICENCE, got DOCUMENT_TYPE_UNCERTAIN
- IMG_20260922_202808.jpg: expected DRIVING_LICENCE, got DOCUMENT_TYPE_UNCERTAIN
- IMG_20260922_203247.jpg: expected DRIVING_LICENCE, got DOCUMENT_TYPE_UNCERTAIN
- bhutan_passport.jpeg: expected DRIVING_LICENCE, got DOCUMENT_TYPE_UNCERTAIN
- passport_text_legibility_enhanced.jpg: expected INDIAN_PASSPORT, got DOCUMENT_TYPE_UNCERTAIN
