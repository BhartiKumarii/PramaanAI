"""End-to-end wiring check: Android app <-> FastAPI server <-> web console.

1. Static: every API path the Android app (Retrofit interfaces) and the web
   console (frontend/src/api/*.ts, pages) call exists in the server's OpenAPI.
2. Live, against a running server (default http://127.0.0.1:8000):
   phone officer verifies region crops (opening a case) -> uploads evidence
   images -> sends to admin -> admin (web) lists and opens the case, the
   document verification and the images -> records a decision -> the phone
   sees the admin's response.

Run: .venv/bin/python -m scripts.wiring_check [--base URL] [--officer U] [--admin U] [--password P]
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OK, BAD = "PASS", "FAIL"
results: list[tuple[str, str, str]] = []


def record(name: str, ok: bool, detail: str = "") -> bool:
    results.append((OK if ok else BAD, name, detail))
    print(f"[{OK if ok else BAD}] {name}{' — ' + detail if detail else ''}", flush=True)
    return ok


def http(method: str, url: str, token: str | None = None, body=None, files=None, timeout=240):
    headers = {}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if files is not None:
        boundary = uuid.uuid4().hex
        parts = []
        for name, (fname, content, ctype) in files.items():
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{fname}\"\r\n"
                         f"Content-Type: {ctype}\r\n\r\n".encode() + content + b"\r\n")
        data = b"".join(parts) + f"--{boundary}--\r\n".encode()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            ctype = r.headers.get("Content-Type", "")
            return r.status, (json.loads(raw) if "json" in ctype else raw)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")[:300]


# ------------------------------------------------------------------ static

def _norm(path: str) -> str:
    path = path.split("?")[0].rstrip("/") or "/"
    return re.sub(r"\{[^}]+\}|\$\{[^}]+\}|:[a-zA-Z_]+", "{}", path)


def static_check() -> None:
    sys.path.insert(0, str(ROOT))
    from app.main import app
    server = {(_norm(p), m.upper()) for p, ops in app.openapi()["paths"].items() for m in ops}
    server_paths = {p for p, _ in server}

    android = []
    for f in (ROOT / "android/app/src/main/java").rglob("*.kt"):
        for m in re.finditer(r'@(GET|POST|PUT|PATCH|DELETE)\("([^"]+)"\)', f.read_text()):
            android.append((m.group(1), "/" + m.group(2).lstrip("/"), f.name))
    missing = [(m, p, f) for m, p, f in android if (_norm(p), m) not in server]
    record(f"Android: {len(android)} API calls exist on the server", not missing,
           "; ".join(f"{m} {p} ({f})" for m, p, f in missing))

    web = []
    for f in list((ROOT / "frontend/src").rglob("*.ts")) + list((ROOT / "frontend/src").rglob("*.tsx")):
        text = f.read_text()
        for m in re.finditer(r"apiClient\.(get|post|put|patch|delete)(?:<[^>]*>)?\(\s*[`'\"]([^`'\"]+)[`'\"]", text):
            web.append((m.group(1).upper(), m.group(2), f.name))
        for m in re.finditer(r"\$\{baseURL\}(/[^`'\"]+)[`'\"]", text):
            web.append(("GET", m.group(1), f.name))
    def exists(method: str, path: str) -> bool:
        n = _norm(path)
        if (n, method) in server:
            return True
        # a trailing template segment (".../${type}") is filled in at run time:
        # accept it when some server route extends the fixed prefix
        if path.rstrip("/").split("/")[-1].startswith("${"):
            prefix = n.rsplit("/", 1)[0] + "/"
            return any(sp.startswith(prefix) and sm == method for sp, sm in server)
        # a base path the caller extends (e.g. `${base}/document`)
        return any(sp.startswith(n + "/") for sp in server_paths)
    missing = [(m, p, f) for m, p, f in web if not exists(m, p)]
    record(f"Web console: {len(web)} API calls exist on the server", not missing,
           "; ".join(f"{m} {p} ({f})" for m, p, f in missing))


# ------------------------------------------------------------------ live

def live_check(base: str, officer: str, admin: str, password: str) -> None:
    status, body = http("GET", f"{base}/health")
    if not record("Server health", status == 200, str(body)[:60]):
        return
    status, cps = http("GET", f"{base}/checkpoints")
    record("Checkpoints list (login screen)", status == 200 and isinstance(cps, list) and len(cps) > 0, f"{len(cps) if isinstance(cps, list) else cps}")

    status, tok = http("POST", f"{base}/auth/login", body={"username": officer, "password": password})
    if not record(f"Officer login ({officer})", status == 200, "" if status == 200 else str(tok)):
        return
    ot = tok["access_token"]
    status, tok = http("POST", f"{base}/auth/login", body={"username": admin, "password": password})
    if not record(f"Admin login ({admin})", status == 200, "" if status == 200 else str(tok)):
        return
    at = tok["access_token"]

    # the phone's request: region crops of a synthetic DL + a live face crop
    sys.path.insert(0, str(ROOT))
    import cv2
    from app.services.docverify.detection import decode_image
    from app.services.docverify.ocr import ocr_image
    syn = ROOT / "data/synthetic/docverify"
    data = (syn / "GEN-001_passport.jpg").read_bytes()
    bgr, rgb = decode_image(data)
    h, w = bgr.shape[:2]
    crops = []
    for line in ocr_image(rgb)[:16]:
        x0, y0, x1, y1 = line.bbox
        x0, y0, x1, y1 = max(0, x0 - 6), max(0, y0 - 6), min(w, x1 + 6), min(h, y1 + 6)
        ok, jpg = cv2.imencode(".jpg", bgr[y0:y1, x0:x1])
        crops.append({"label": "text", "bbox": line.bbox, "crop_bbox": [x0, y0, x1, y1], "confidence": 0.9,
                      "image_b64": base64.b64encode(jpg.tobytes()).decode()})
    live = (syn / "TST-021_live_same_person.jpg").read_bytes()
    req = {"documents": [{"image_size": [w, h], "regions": crops, "device_detector": "wiring-check"}],
           "client_request_id": f"wiring-{uuid.uuid4().hex[:12]}", "live_face_b64": base64.b64encode(live).decode(),
           "open_case": True, "device_text": [{"document_index": 0, "text": "SYNTHETIC SPECIMEN", "bbox": [0, 0, 50, 10],
                                              "confidence": 0.9}]}
    status, out = http("POST", f"{base}/api/v1/verify/regions", ot, body=req)
    if not record("Phone: verify region crops (opens a case)", status == 200 and isinstance(out, dict) and out.get("id"),
                  f"status {status}" if status != 200 else f"{out.get('overall_status')} risk {out.get('risk_score')}"):
        return
    vid = out["id"]
    case = out.get("case") or {}
    record("Case opened with number and evidence record", bool(case.get("case_number") and case.get("screening_verification_id")),
           f"{case.get('case_number')} {case.get('status')}")
    record("Automatic reasons returned", bool((out.get("suggested_reasons") or {}).get("send")))
    record("Identity graph returned", out.get("identity") is not None)
    facts = (out.get("officer_summary") or {}).get("facts", {})
    record("Checkpoint/border in result", "Checkpoint" in facts and "Border Type" in facts, f"{facts.get('Checkpoint')} / {facts.get('Border Type')}")

    status, again = http("POST", f"{base}/api/v1/verify/regions", ot, body=req)
    record("Phone: offline-sync retry is idempotent (same record, same case)",
           status == 200 and again.get("id") == vid and (again.get("case") or {}).get("case_id") == case.get("case_id"))

    sid = case.get("screening_verification_id")
    status, up = http("POST", f"{base}/images/{sid}/upload", ot, files={
        "document_front": ("document_front.jpg", data, "image/jpeg"), "selfie": ("selfie.jpg", live, "image/jpeg")})
    record("Phone: evidence images uploaded to the case", status == 201, str(up)[:80])

    status, lst = http("GET", f"{base}/api/v1/verification?mine=true&limit=20", ot)
    item = next((i for i in lst if i["id"] == vid), None) if status == 200 else None
    record("Phone: Review/History list shows the case", bool(item and item.get("case_number")),
           f"{item.get('case_status') if item else lst}")

    status, _ = http("POST", f"{base}/api/v1/verification/{vid}/officer-action", ot,
                     body={"action": "SEND_TO_OFFICER", "reason": out["suggested_reasons"]["send"]})
    record("Phone: Send to admin", status == 200)

    status, cases = http("GET", f"{base}/cases", at)
    record("Web: admin case list includes the sent case", status == 200 and any(c["id"] == case["case_id"] for c in cases))
    status, detail = http("GET", f"{base}/cases/{case['case_id']}", at)
    record("Web: case detail opens", status == 200 and detail.get("status") == "SENT", f"{detail.get('status') if status == 200 else detail}")
    status, env = http("GET", f"{base}/api/v1/verification/by-case/{case['case_id']}", at)
    record("Web: document verification behind the case", status == 200 and env["result"]["id"] == vid)
    for kind in ("document", "selfie"):
        status, img = http("GET", f"{base}/images/{sid}/{kind}", at)
        record(f"Web: evidence image '{kind}' loads", status == 200 and isinstance(img, bytes) and len(img) > 1000)

    status, _ = http("POST", f"{base}/cases/{case['case_id']}/decision", at,
                     body={"decision": "SECONDARY_REVIEW", "reason": "Wiring check — compare the expiry date on the page"})
    record("Web: admin records a decision", status == 200)
    status, env = http("GET", f"{base}/api/v1/verification/{vid}", ot)
    dec = ((env.get("result") or {}).get("case") or {}).get("decisions", []) if status == 200 else []
    record("Phone: sees the admin's response", any(d.get("role") == "REVIEWER" for d in dec),
           dec[-1]["reason"] if dec else str(env)[:80])
    status, lst = http("GET", f"{base}/api/v1/verification?mine=true&limit=20", ot)
    item = next((i for i in lst if i["id"] == vid), None) if status == 200 else None
    record("Phone: notification flag (admin responded)", bool(item and item.get("reviewer_responded")))
    status, chain = http("GET", f"{base}/api/v1/verification/chain/verify", at)
    record("Audit hash chain intact", status == 200 and chain.get("chain_valid") is True,
           f"{chain.get('records_checked')} records" if status == 200 else str(chain)[:80])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--officer", default="raxaul_officer")
    ap.add_argument("--admin", default="it_admin")
    ap.add_argument("--password", default="BorderShield123")
    ap.add_argument("--static-only", action="store_true")
    a = ap.parse_args()
    static_check()
    if not a.static_only:
        live_check(a.base.rstrip("/"), a.officer, a.admin, a.password)
    failed = [r for r in results if r[0] == BAD]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
