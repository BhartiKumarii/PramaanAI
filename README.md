<h1 align="center">PramaanAI</h1>

<p align="center">
  <strong>AI-Based Fake Identity & Document Screening System</strong><br>
  Smart India Hackathon 2026 | Problem Statement ID: 26188<br>
  Ministry of Home Affairs / Sashastra Seema Bal (SSB) — Police II Division
</p>

<p align="center">
  <a href="https://pramaanai-703j.onrender.com">Live Website</a> &bull;
  <a href="https://github.com/BhartiKumarii/PramaanAI/releases/latest">Download APK</a> &bull;
  <a href="#screenshots">Screenshots</a>
</p>

---

## Quick Start — Try It Now

> **Demo Credentials (works on both website and Android app)**
>
> | Use | Username | Password |
> |-----|----------|----------|
> | Web console — admin (answers cases sent from the app) | `it_admin` | `BorderShield123` |
> | Android app — field officer (post: Raxaul, India–Nepal) | `raxaul_officer` | `BorderShield123` |
>
> **Live Dashboard:** [pramaanai-703j.onrender.com](https://pramaanai-703j.onrender.com)
> **API Docs:** [bordershield-pramaan-api.onrender.com/docs](https://bordershield-pramaan-api.onrender.com/docs)
> **Android APK:** [Download from Releases](https://github.com/BhartiKumarii/PramaanAI/releases/latest)
>
> *Note: Render free tier spins down after inactivity — first load may take 30-60 seconds.*

### Judge's Quick Start

1. **Android App** — Download the [APK](https://github.com/BhartiKumarii/PramaanAI/releases/latest), install on an Android device (8.0+), log in with `raxaul_officer` / `BorderShield123`. Tap **Verify document**, photograph a document, take a live photo, and read the result. Then choose **Clear** or **Send to admin**. The guided tour includes a practice verification that uses a synthetic sample.

2. **Web Dashboard** — Open [pramaanai-703j.onrender.com](https://pramaanai-703j.onrender.com), log in with `it_admin` / `BorderShield123`. Open the case you sent. It shows the document with the problem areas marked, the live photo, the extracted fields and the identity links. Write a response, and the officer sees it in the app.

3. **API** — Visit [bordershield-pramaan-api.onrender.com/docs](https://bordershield-pramaan-api.onrender.com/docs) for the full Swagger UI. Authenticate via `POST /auth/login`.

| Resource | Link |
|----------|------|
| Live Website | [pramaanai-703j.onrender.com](https://pramaanai-703j.onrender.com) |
| GitHub Repository | [github.com/BhartiKumarii/PramaanAI](https://github.com/BhartiKumarii/PramaanAI) |
| Demo APK | [Download from Releases](https://github.com/BhartiKumarii/PramaanAI/releases/latest) |
| Prototype Video | [ADD VIDEO LINK] |
| Project Report | [Documentation/PramaanAI-Report.pdf](Documentation/PramaanAI-Report.pdf) |
| Presentation | [Documentation/PramaanAI-Presentation.pdf](Documentation/PramaanAI-Presentation.pdf) |
| API Documentation | [bordershield-pramaan-api.onrender.com/docs](https://bordershield-pramaan-api.onrender.com/docs) |

---

## Project Overview

PramaanAI is an AI-powered document verification and identity screening system designed for SSB officers patrolling India's open land borders with Nepal (1,751 km) and Bhutan (699 km). These borders operate under treaty-based free movement — most crossers carry no passport. The real fraud risk is concentrated in impersonation and document tampering, not universal scanning.

PramaanAI assists officers in the field with on-device intelligence: real-time OCR, MRZ validation, document tampering analysis, face verification, and server-backed registry checks — all accessible from a single Android app that works online, on weak connections, or completely offline.

**This is a hackathon prototype.** All registry data is synthetic/mock. No real government database is accessed. The system assists officer decisions — it never declares guilt, denies entry, or asserts criminality.

---

## Problem Statement

**PS ID:** 26188  
**Organization:** Ministry of Home Affairs / Sashastra Seema Bal (SSB)  
**Category:** Software  
**Theme:** Miscellaneous

SSB guards India's two open, treaty-based land borders via Border Out Posts and mobile patrols, not fixed immigration desks. Officers need a portable, intelligent tool that can verify identity documents in the field — even without reliable internet connectivity — and flag potential fraud for human review.

---

## Proposed Solution

A three-component system:

1. **Android App** — Field tool for SSB officers. Captures documents, runs on-device verification (OCR, MRZ, tampering detection, face matching), caches results offline, syncs when connectivity returns.

2. **FastAPI Backend** — Central verification server. Runs OCR, MRZ, QR, stamp, face, forensics and registry checks on the region crops sent by the phone, and returns explainable results. All traffic is encrypted in transit.

3. **Web Dashboard** — Combined operational console for case management, alerts, identity network visualization, audit logs, analytics, and system administration.

---

## Key Features

### Android app
- **Verify document**, a single guided flow: capture (camera or gallery) → review the regions and text found on the phone → choose the crossing → live photo (front/back camera, flip, gallery for testing, or skip) → result
- **On-device region detection**: YOLO11n (ONNX) locates the photo, MRZ, QR/barcode, stamps and text blocks. Only those crops are sent, in one HTTPS request.
- **On-device text and MRZ**: ML Kit text recognition, with ICAO 9303 check digits verified on the phone before anything is sent
- **Understandable results**:
  - headline and plain-language reasons
  - the document with each problem boxed
  - extracted fields with their source (server OCR / MRZ / QR / phone / Devanagari)
  - document photo next to the live photo, with the similarity score
  - identity graph (same face under another name, same document number seen before)
  - risk breakdown
- **Decision stays with the officer**: **Clear**, or **Send to admin**, with a reason written automatically from the checks and editable before sending. The admin's answer appears in the app.
- **Review, History and Notifications**:
  - Review: cases waiting on you or on the admin
  - History: everything, grouped by day, with search
  - Notifications: admin responses plus high/medium/low risk alerts
  - "Filter by" dropdowns (result, risk, document, period)
  - each record keeps the original document, the problem locations, the live photo and the extracted fields
- **Evidence**: the document image and live face crop are attached to the case for the admin. On the phone they are stored encrypted (Android Keystore) and deleted automatically after the retention period.
- **Offline**: encrypted queue with automatic sync (WorkManager); retries are idempotent. Connection state (Online / Weak / Offline) is checked live.
- **Dashboard, Analytics and Officer profile**: today's KPIs, a 7/30-day activity chart, risk distribution, common reasons for attention, and results by document type, country and time of day
- **Guided tour + practice verification**: walks through every step on a synthetic sample. Nothing is sent or stored.
- **Settings**:
  - language and default crossing
  - live-photo prompt, image retention and admin-response polling
  - which alert levels to show, auto-lock time, and a connection test
- **7 UI languages**: English, Hindi, Nepali, Bengali, Assamese and Punjabi are fully translated (~890 strings). Dzongkha is partial and falls back to English.

### Document Support
| Country | Documents |
|---------|-----------|
| India | Aadhaar (with Verhoeff checksum), PAN Card, Passport, Driving Licence, Voter ID (EPIC), Inner Line Permit |
| Nepal | Passport (MRZ), Citizenship Certificate, Driving Licence, Tourist Visa, Visa on Arrival |
| Bhutan | Passport (MRZ), Citizen Identity Card (CID), Driving Licence (RSTA), Visa |

### Server-Side Verification
- **OCR**: PP-OCR (PaddleOCR weights on ONNX Runtime) for Latin text, plus a PP-OCRv5 **Devanagari** recogniser for Nepali/Hindi.
  - Devanagari fields (name, national ID / citizenship number, sex, date of birth) are kept separately and never compared against the registry.
  - Nepali dates stay in Bikram Sambat.
- **MRZ / QR / stamps**: ICAO 9303 parser with recomputed check digits, QR/barcode decoding and cross-check, and immigration stamps identified against official checkpoint reference data
- **Face**: InsightFace (SCRFD detector plus an ArcFace-family embedding). Document photo vs. live photo gives Match / Possible match (review) / No match; no face found is inconclusive, never "no match". A second portrait (ghost image) on passports, licences and visas is treated as normal.
- **Crossing rules**: India–Nepal / India–Bhutan rules are evaluated. The crossing comes from the stamp, the officer's post, or the officer's choice.
- **Registry Lookup** — Exact (document number) and fuzzy (name) matching against mock registry
- **Risk Scoring** — Weighted fusion of checksum, forensics, deepfake, blacklist, face match, and identity signals
- **Identity Graph** — NetworkX connected-component analysis for multi-identity cluster detection
- **Cross-field Validation** — MRZ vs. printed fields, front vs. back consistency
- **HMAC-signed Records** — Every verification result is cryptographically signed; tampering is detected on read
- **Full Audit Trail** — Every action (screen, clear, dispute, decision) is logged with officer ID and timestamp
- **Hash-chained records**: every verification is appended to a local tamper-evident hash chain (not a blockchain)

### Web Dashboard
- **Case review with document evidence**:
  - the original document with the problem areas marked (click a finding to highlight it)
  - document photo vs. live photo
  - extracted fields with their source, and the identity links
  - the officer's message and suggested response wording
- **Case Management** — Submit, review, decide (Clear / Secondary Review / Hold-Refer)
- **Real-time Alerts** — Document review required, risk assessment, duplicates, incomplete records
- **Identity Network** — Visual graph of identity clusters and relationships
- **Person Search** — Search across all screened individuals
- **Document Intelligence** — Document type analytics, country distribution, classification insights
- **Checkpoint Management** — Border checkpoint monitoring and status
- **Registry Management** — View and manage mock central registry entries
- **Audit Logs** — Complete audit trail with filtering
- **Analytics & Reports** — Risk trends, screening volume, officer activity
- **RBAC** — Server-enforced roles: Officer (app) and Reviewer (web admin, decides cases)

---

## System Architecture

```
+--------------------+        +----------------------+       +------------------+
|    Android App     |  TLS   |    FastAPI Backend   |       |  Web Dashboard   |
|  (Officer, field)  |------->|   (Central Server)   |<------|  (Admin console) |
|                    | region |                      |       |                  |
| - YOLO11n regions  | crops +| - PP-OCR + Devanagari|       | - React + TS     |
| - ML Kit text/MRZ  | phone  | - MRZ / QR / stamps  |       | - Case review w/ |
| - Live photo       | text   | - Face (InsightFace) |       |   document boxes |
| - Clear / Send to  |        | - Forensics          |       | - Admin response |
|   admin            |        | - Registry (mock)    |       | - Identity graph |
| - Review/History/  |        | - Crossing rules     |       | - Alerts, audit  |
|   Notifications    |        | - Decision engine    |       | - Analytics      |
| - Encrypted offline|        | - Hash-chained audit |       | - RBAC           |
|   queue + sync     |        | - PostgreSQL         |       |                  |
+--------------------+        +----------------------+       +------------------+
```

**Privacy by design:**
- Verification sends only the detected region crops and the text read on the phone, never the full frame. The verify endpoints process them in memory and store only hashes.
- After verification, the document image and the live face crop are attached to the case as evidence, so the admin can review them.
- Stored results drop raw OCR text, and Aadhaar numbers are masked.

---

## End-to-End Workflow

| Stage | Process | Output |
|-------|---------|--------|
| 1. Capture | Document front, back (optional), and live selfie | Raw images |
| 2. On-device processing | OCR, MRZ parsing, quality checks, face detection, tampering analysis | Structured fields + evidence |
| 3. Local cache check | Check for previously verified record | Cache hit / miss |
| 4. Connectivity check | Live health check — online, weak, or offline | Routing decision |
| 5a. Online | Send region crops + on-device text securely (never the full frame for verification); the document image and live face are then attached to the case as evidence | Verification request + case |
| 5b. Offline | Encrypt and queue case locally | Pending case |
| 6. Server verification | Registry match, identity graph, face comparison, risk scoring | Structured result |
| 7. Explainable result | Verified / Review Required / Flagged with reasons | Officer evidence |
| 8. Officer decision | Clear, or Send to admin with an auto-written, editable reason; the admin answers from the web console | Case decision |
| 9. Synchronization | Pending cases sync when connectivity returns | Centralized record |

The system assists decisions — it never blocks entry, declares guilt, or overrides the officer.

---

## Web Dashboard

The dashboard provides a unified operational view:

- **Landing Page** — Professional public-facing page explaining PramaanAI
- **Dashboard Home** — Real-time statistics, risk distribution, recent activity
- **Cases** — Full case lifecycle: pending, submitted, cleared, disputed
- **Alerts** — Prioritized notifications requiring attention
- **Identity Network** — Visual cluster graph of related identities
- **Document Intelligence** — Classification analytics and document type distribution
- **Checkpoints** — Border post status and monitoring
- **Registry** — Mock central registry with search
- **Audit Logs** — Complete action history with filtering
- **Reports** — Analytics and trend visualization

---

## Technology Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | Python, FastAPI, Pydantic, SQLAlchemy, PostgreSQL, Alembic, JWT/Argon2, PP-OCR (RapidOCR / ONNX Runtime) incl. Devanagari, InsightFace, OpenCV, NetworkX |
| **Android** | Kotlin, Jetpack Compose, CameraX, ONNX Runtime (YOLO11n), ML Kit (Text Recognition, Face Detection, Barcode Scanning), Retrofit, WorkManager, Android Keystore, Material 3 |
| **Frontend** | React 19, TypeScript, Vite, Tailwind CSS, Axios, Recharts |
| **Infrastructure** | Docker Compose, Render (backend + DB), GitHub Releases (APK) |

---

## Security & Privacy

- Verification requests carry region crops and on-device text only, never the full frame. Evidence images are attached to a case only after verification, for admin review.
- All network communication over TLS
- JWT authentication with Argon2 password hashing
- Server-enforced RBAC (Officer / Reviewer)
- HMAC-signed verification records — tampering detected on read
- On-device encryption for offline queue (Android Keystore)
- PII redaction filter on server logs
- No real government database access — all registry data is explicitly synthetic/mock
- No facial emotion, skin temperature, nationality, religion, or ethnicity used as risk signals

---

## Supported Documents & Test Cases

The `ID_DOCUMENT_DATASET/` directory contains sample documents for testing:

| Country | Document Types | Test Images |
|---------|---------------|-------------|
| India | Aadhaar, PAN, Passport, Driving Licence, Voter ID, ILP | 15+ samples |
| Nepal | Passport, Citizenship Certificate, Driving Licence, Visa | 20+ samples |
| Bhutan | Passport, CID, Driving Licence, Visa | 7+ samples |

### Verification Checks Performed

| Check | Status Values | Description |
|-------|--------------|-------------|
| Image quality | PASS / WARNING | Blur, glare, lighting, shadow detection |
| Document type detection | PASS / WARNING | Pattern-based classification (40+ signals) |
| Document type mismatch | WARNING | Selected vs. detected type comparison |
| Critical field extraction | PASS / WARNING | Name, DOB extraction completeness |
| Document number extraction | PASS / WARNING | ID/passport/DL number detection |
| MRZ check digits (5 fields) | PASS / FAIL | ICAO 9303 checksum validation |
| MRZ vs. printed consistency | PASS / WARNING | Cross-field comparison |
| Document expiry | PASS / WARNING / FAIL | Date validity check |
| QR/barcode scan | PASS / NOT_AVAILABLE | Code detection and cross-check |
| Face detection (selfie) | PASS / FAIL / WARNING | Single face verification |
| Face on document | PASS / WARNING | Photo presence on document |
| Document integrity check | PASS / WARNING / FAIL | Alteration detection |
| Photo authenticity check | PASS / WARNING / FAIL | Selfie genuineness check |
| Registry verification | PASS / FAIL / NOT_AVAILABLE | Registry lookup and risk scoring |

---

## Screenshots

### Web Dashboard

| Landing Page | Dashboard | Cases |
|:---:|:---:|:---:|
| ![Landing](Screenshots/Dashboard/00-landing.png) | ![Dashboard](Screenshots/Dashboard/01-dashboard.png) | ![Cases](Screenshots/Dashboard/02-cases.png) |

| Alerts | Person Search | Identity Network |
|:---:|:---:|:---:|
| ![Alerts](Screenshots/Dashboard/03-alerts.png) | ![Search](Screenshots/Dashboard/04-person-search.png) | ![Identity](Screenshots/Dashboard/05-identity-network.png) |

| Document Intelligence | Checkpoints | Registry |
|:---:|:---:|:---:|
| ![DocIntel](Screenshots/Dashboard/06-document-intelligence.png) | ![Checkpoints](Screenshots/Dashboard/07-checkpoints.png) | ![Registry](Screenshots/Dashboard/08-registry.png) |

| Audit Logs | Reports | Case Detail |
|:---:|:---:|:---:|
| ![AuditLogs](Screenshots/Dashboard/09-audit-logs.png) | ![Reports](Screenshots/Dashboard/10-reports.png) | ![CaseDetail](Screenshots/Dashboard/11-case-detail.png) |

### Mobile App

*Add screenshots of the Android app to `Screenshots/Mobile/` — document capture, field review, verification evidence, screening result.*

---

## Limitations

- **Mock Data Only** — Registry lookups use synthetic data. No real government database is connected.
- **Handwriting** — Handwritten entries (e.g. dates written on visa stamps) are not read reliably. Measured: 0/7 with the current OCR, 1/7 even on hand-placed crops. The officer reads them from the document image. See `Documentation/DOCUMENT_VERIFICATION.md`.
- **Document scripts** — Latin and Devanagari text is read. Bengali, Gurmukhi and Dzongkha (Tibetan script) document text is not.
- **Face Matching** — A general-purpose face model; not a certified biometric system. Borderline scores are sent for officer review.
- **Forensics** — Region-level image-manipulation indicators. Some synthetic manipulations are still missed (see the evaluation report).
- **Dzongkha UI** — Partially translated; untranslated screens show English.
- **Offline Mode** — Full local extraction works, but risk scoring and registry lookup require server connectivity.
- **Render Free Tier** — Backend and database on Render's free tier may experience cold-start delays and resource limits.

---

## Future Scope

- Integration with real government databases (UIDAI, Passport Seva, immigration systems) via approved APIs
- Production-grade deep learning models for face recognition and deepfake detection
- Multi-frame liveness detection with challenge-response
- Edge deployment for Border Out Posts with limited connectivity
- Handwritten-field reading: labelled handwriting boxes plus a recogniser fine-tuned on border forms
- Complete Dzongkha UI, and Bengali/Gurmukhi/Dzongkha document text
- Biometric integration (fingerprint, iris) where hardware is available
- Real-time inter-checkpoint communication network
- Progressive Web App for the dashboard

---

## Team AlphaX

[ADD TEAM MEMBER DETAILS]

---

## Running Locally

### Backend

```bash
# Docker (recommended)
docker compose up --build
docker compose exec app alembic upgrade head
# demo accounts (raxaul_officer, it_admin, …) are seeded on start by docker-entrypoint.sh

# Without Docker
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Android

Open `android/` in Android Studio. Build and run on a device with camera access. The app uses the Render server by default. To point it at a local server, build with `./gradlew assembleDebug -Ppramaan.apiUrl=http://<your-ip>:8000/`.

---

## License

This project is a hackathon prototype developed for Smart India Hackathon 2026. 

---

<p align="center">
  <strong>PramaanAI</strong> — Empowering SSB officers with intelligent document verification at India's borders.
</p>

## Modular document verification (`/api/v1`)

Evidence-based verification of passports, visas, permits, driving licences,
Aadhaar-type cards and immigration stamps for the India–Nepal and
India–Bhutan borders. The Android app runs a small on-device YOLO11n model
to locate regions and sends only those crops, in one HTTPS request; OCR,
MRZ, QR/barcode, stamps, face, forensics, registry comparison and the final
decision run on the server. Results are PASS / REVIEW_REQUIRED / NOT_VERIFIED
/ … with named reasons and evidence boxes — never "fake" or "real".

* Architecture, API, data formats, scaling: [`Documentation/DOCUMENT_VERIFICATION.md`](Documentation/DOCUMENT_VERIFICATION.md)
* Checklist and test-condition coverage: [`Documentation/TEST_CONDITIONS.md`](Documentation/TEST_CONDITIONS.md)
* Latest evaluation: `reports/docverify_evaluation.md`, `reports/yolo_region_detector.json`
