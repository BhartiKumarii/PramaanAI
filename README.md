# PramaanAI — Backend (Phase 1 complete)

Privacy-preserving AI-powered identity/travel-document screening backend.
**Hackathon prototype — not a production border-security system.** No real
government database access; all "database" and "blockchain" integrations
here are explicitly mock/local implementations.

## Status

All nine Phase 1 modules are implemented, wired, and verified end-to-end
against the live Docker/Postgres stack (real images through, real
computed results out — see each module's test file for what "verified"
means concretely):

- `POST /auth/login`, `GET /health` — JWT/Argon2 auth, RBAC scaffolding
- `POST /documents/ocr` — real Tesseract OCR field extraction
- `POST /documents/validate` — real ICAO 9303 MRZ checksum, real Verhoeff
  (Aadhaar) checksum, real front/back cross-validation
- `POST /documents/tampering` — real Error Level Analysis (Pillow only),
  returns a bounding box of the highest-anomaly region
- `POST /documents/deepfake` — **honestly returns `NOT_IMPLEMENTED`**, not
  a faked pass (see "Known gaps" below for why)
- `POST /face/verify` — real HOG-style embedding + real cosine similarity
  (classical CV, not a deep model — see "Known gaps")
- `POST /registry/seed`, `POST /registry/lookup` — real SQL lookup against
  `mock_central_registry`, exact (document number) and fuzzy (name) match,
  tagged distinctly, never collapsed into one flag
- `POST /identity/check` — real pairwise face-embedding comparison +
  NetworkX connected-component analysis for multi-identity clusters
- `POST /documents/screen` — orchestrates every module above, fuses them
  via `app/services/risk/engine.py` (weighted: checksum 0.20, forensics
  0.20, deepfake 0.15, blacklist 0.20, face match 0.15, identity graph
  0.10 — renormalized when a signal is absent; hard overrides for a
  HIGH-severity EXACT blacklist hit, a multi-identity cluster, or a severe
  front/back mismatch), then HMAC-signs and persists the result
- `GET /verification/{id}` — re-verifies the HMAC signature on every read;
  a tampered row is flagged (`signature_valid: false`), never trusted
- `GET /verification/{id}/audit`, `POST /verification/{id}/dispute`,
  `POST /verification/{id}/clear` — full lifecycle audit trail; disputes
  require a reason and are logged, never a silent clear
- `POST /blockchain/verify` — a local mock hash-chained ledger (explicitly
  not a real/distributed blockchain), recomputes chain integrity on demand

No endpoint anywhere accepts a manually-set risk score — `RiskResult` is
only ever constructed inside the risk engine.

### Known gaps (disclosed honestly, not faked)

- **Deepfake detection**: not implemented. A real classifier needs
  torch/transformers (the same multi-GB CUDA footprint that already ruled
  out PaddleOCR/EasyOCR here) or a downloaded model from an unverified
  source. The endpoint says so explicitly rather than returning a fake pass.
- **Face verification** uses a classical HOG-over-Sobel-gradients
  descriptor + cosine similarity, not a deep embedding model — `dlib`/
  `face_recognition` needs `cmake`, unavailable in this sandbox with no
  passwordless sudo. Real and deterministic, but meaningfully less
  accurate than a modern face-recognition network.
- **Forensics (ELA)** runs hot on any text-dense, untampered document
  (JPEG compression naturally produces more error around text/edges than
  blank margins) — a known limitation of single-pass ELA, not a bug.
- **Liveness detection** is not built — it's inherently tied to a
  multi-frame challenge-response flow with no client to drive it yet.

## Run with Docker (recommended)

```bash
docker compose up --build
```

This starts Postgres + the API. `.env` (gitignored, already generated for
local dev) supplies `JWT_SECRET_KEY` / `ENCRYPTION_KEY`; compose overrides
`DATABASE_URL` to point at the `db` service.

Apply migrations and seed a user once the containers are up:

```bash
docker compose exec app alembic upgrade head
docker compose exec app python -m scripts.seed_admin officer1 'Str0ngPass!'
```

Then:

```bash
curl -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username": "officer1", "password": "Str0ngPass!"}'

curl http://localhost:8000/health
```

Swagger UI: http://localhost:8000/docs

## Run locally without Docker

Requires a local Postgres reachable at the `DATABASE_URL` in `.env` (or edit
it to point elsewhere).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
python -m scripts.seed_admin officer1 'Str0ngPass!'
uvicorn app.main:app --reload
```

## Tests

Tests run against an in-memory SQLite DB with test-only secrets set in
`tests/conftest.py` — no Postgres or `.env` required.

```bash
pip install -r requirements-dev.txt
pytest
```

## Security notes (dev-mode caveats, read before extending)

- `ENCRYPTION_KEY` / `JWT_SECRET_KEY` come from env vars in dev; production
  should source them from a KMS/HSM instead (`app/core/encryption.py`'s
  `_load_key()` is the single place to swap).
- Raw document/face images are never persisted by default — the pipeline
  (once built) is expected to process in-memory buffers and discard them.
- `app/utils/logging.py` installs a best-effort PII redaction filter, but
  it's a safety net, not a substitute for not logging PII in the first
  place.
- TLS termination is out of scope for this prototype; production deployment
  must sit behind HTTPS.

## Remaining (not yet built)

- `GET /officers`, `POST /officers` — basic CRUD, admin-only in intent
- Liveness detection (needs a client driving a real challenge-response flow)
- A real deepfake classifier, if a viable lightweight/local option turns up

Phase 2 (Android) starts only after Phase 1 is complete and documented, on
your explicit "START ANDROID".
