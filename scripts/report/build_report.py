"""Build Documentation/PramaanAI-Report.pdf (SIH 2026 project report).

    .venv/bin/python scripts/report/build_report.py

Figures quoted here are the ones measured in this repository (reports/,
tests, device-path replay, memory profiling). Screenshots come from
Screenshots/Web/, captured on a server holding synthetic data only.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from reportlab.graphics.shapes import Drawing, Line, Rect, String, Polygon
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Documentation" / "PramaanAI-Report.pdf"
SHOTS = ROOT / "Screenshots" / "Web"

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
pdfmetrics.registerFont(TTFont("Body", str(FONT_DIR / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("Body-Bold", str(FONT_DIR / "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("Mono", str(FONT_DIR / "DejaVuSansMono.ttf")))

ACCENT = colors.HexColor("#15803d")
INK = colors.HexColor("#111827")
MUTED = colors.HexColor("#4b5563")
RULE = colors.HexColor("#d1d5db")
SOFT = colors.HexColor("#f3f4f6")

ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontName="Body-Bold", fontSize=17, leading=21, textColor=INK,
                    spaceBefore=6, spaceAfter=8)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Body-Bold", fontSize=12.5, leading=16, textColor=ACCENT,
                    spaceBefore=10, spaceAfter=4)
P = ParagraphStyle("P", parent=ss["BodyText"], fontName="Body", fontSize=9.6, leading=13.6, textColor=INK,
                   spaceAfter=5)
SMALL = ParagraphStyle("S", parent=P, fontSize=8.2, leading=11, textColor=MUTED)
BUL = ParagraphStyle("B", parent=P, leftIndent=12, bulletIndent=2, spaceAfter=2.5)
CELL = ParagraphStyle("C", parent=P, fontSize=8.4, leading=11, spaceAfter=0)
CELLB = ParagraphStyle("CB", parent=CELL, fontName="Body-Bold")
TITLE = ParagraphStyle("T", parent=H1, fontSize=30, leading=36, alignment=TA_CENTER, textColor=INK)
SUB = ParagraphStyle("Sub", parent=P, fontSize=12, leading=17, alignment=TA_CENTER, textColor=MUTED)


def p(text: str) -> Paragraph:
    return Paragraph(text, P)


def bullets(items: list[str]) -> list[Paragraph]:
    return [Paragraph(i, BUL, bulletText="•") for i in items]


def table(rows: list[list[str]], widths: list[float], header: bool = True) -> Table:
    data = [[Paragraph(c, CELLB if (header and r == 0) else CELL) for c in row] for r, row in enumerate(rows)]
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.4, RULE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
             ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), SOFT))
    t.setStyle(TableStyle(style))
    return t


def shot(name: str, width_mm: float, caption: str) -> KeepTogether:
    path = SHOTS / name
    from PIL import Image as PILImage
    w, h = PILImage.open(path).size
    wpt = width_mm * mm
    img = Image(str(path), width=wpt, height=wpt * h / w)
    return KeepTogether([img, Paragraph(caption, SMALL), Spacer(1, 6)])


def architecture() -> Drawing:
    d = Drawing(170 * mm, 78 * mm)
    W = 170 * mm

    def box(x, y, w, h, title, lines, fill):
        d.add(Rect(x, y, w, h, fillColor=fill, strokeColor=INK, strokeWidth=0.6, rx=4, ry=4))
        d.add(String(x + 6, y + h - 13, title, fontName="Body-Bold", fontSize=8.6, fillColor=INK))
        for i, t in enumerate(lines):
            d.add(String(x + 6, y + h - 26 - i * 10.2, t, fontName="Body", fontSize=7.2, fillColor=MUTED))

    def arrow(x1, y1, x2, y2, label=""):
        d.add(Line(x1, y1, x2, y2, strokeColor=ACCENT, strokeWidth=1.2))
        import math
        a = math.atan2(y2 - y1, x2 - x1)
        s = 5
        d.add(Polygon([x2, y2, x2 - s * math.cos(a - 0.45), y2 - s * math.sin(a - 0.45),
                       x2 - s * math.cos(a + 0.45), y2 - s * math.sin(a + 0.45)], fillColor=ACCENT, strokeColor=ACCENT))
        if label:
            d.add(String((x1 + x2) / 2, (y1 + y2) / 2 + 4, label, fontName="Body", fontSize=6.6,
                         fillColor=ACCENT, textAnchor="middle"))

    bw, bh = 47 * mm, 66 * mm
    y = 6 * mm
    box(0, y, bw, bh, "Android app (officer)", [
        "Capture: camera / gallery / PDF", "YOLO11n regions (on-device)", "ML Kit text + MRZ check digits",
        "Live photo + liveness prompts", "Anti-spoof model (on-device)", "Clear / Send to admin",
        "Encrypted offline queue + sync", "Review, History, Notifications"], colors.HexColor("#ecfdf5"))
    box(W / 2 - bw / 2, y, bw, bh, "FastAPI server (central)", [
        "PP-OCR Latin + Devanagari", "MRZ (ICAO 9303), QR, signatures", "Stamps vs checkpoint reference",
        "Face match (InsightFace)", "Region forensics", "Registry (mock, labelled)", "Crossing rules (Nepal/Bhutan)", "Audit hash chain",
        "Explainable decision"], colors.HexColor("#eff6ff"))
    box(W - bw, y, bw, bh, "Web console (admin)", [
        "Verification Desk", "Case review: document boxes,", "  live photo, fields, identity",
        "Auto-suggested action", "Identity intelligence", "Analytics, audit trail", "Server-enforced roles"],
        colors.HexColor("#fefce8"))
    arrow(bw, y + bh * 0.26, W / 2 - bw / 2, y + bh * 0.26, "crops + text")
    arrow(W / 2 - bw / 2, y + bh * 0.12, bw, y + bh * 0.12, "result")
    arrow(W - bw, y + bh * 0.26, W / 2 + bw / 2, y + bh * 0.26, "decision")
    arrow(W / 2 + bw / 2, y + bh * 0.12, W - bw, y + bh * 0.12, "cases")
    return d


def workflow() -> Table:
    steps = [
        ("1  Capture", "Officer photographs the document (or picks a photo / PDF)."),
        ("2  On the phone", "YOLO11n finds photo, MRZ, QR, stamps; ML Kit reads text; MRZ check digits verified."),
        ("3  Review + crossing", "Officer sees the regions and text; crossing comes from the post or is chosen."),
        ("4  Live photo", "Blink + head-turn prompts, anti-spoof score; or skip."),
        ("5  Connectivity", "Live health check: Online / Weak / Offline. Offline = encrypted queue, auto-sync."),
        ("6  Server checks", "OCR, MRZ, QR/signature, stamps, face, forensics, registry (mock), crossing rules."),
        ("7  Explainable result", "Status + named reasons + problem boxes on the document + identity links."),
        ("8  Officer decides", "Clear, or Send to admin with an auto-written, editable reason."),
        ("9  Admin responds", "Web console: evidence, suggested action; the answer returns to the phone."),
        ("10 Audit", "Every step is logged in a tamper-evident hash chain."),
    ]
    return table([["Step", "What happens"]] + [[a, b] for a, b in steps], [38, 132])


def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFont("Body", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 10 * mm, "PramaanAI — SIH 2026, PS 26188 (MHA / SSB)")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build() -> None:
    story: list = []
    # ---------------------------------------------------------------- cover
    story += [Spacer(1, 50 * mm), Paragraph("PramaanAI", TITLE), Spacer(1, 4),
              Paragraph("Evidence-based document and identity verification for SSB officers "
                        "at the India–Nepal and India–Bhutan borders", SUB),
              Spacer(1, 14),
              Paragraph("Smart India Hackathon 2026 · Problem Statement 26188<br/>"
                        "Ministry of Home Affairs / Sashastra Seema Bal (SSB), Police II Division", SUB),
              Spacer(1, 30),
              Paragraph("Android app · FastAPI server · Web console", SUB),
              Spacer(1, 60),
              Paragraph(f"Project report · {date.today().strftime('%d %B %Y')}<br/>"
                        "Live console: pramaanai-703j.onrender.com · API: bordershield-pramaan-api.onrender.com<br/>"
                        "Source: github.com/BhartiKumarii/PramaanAI", SMALL),
              Spacer(1, 8),
              Paragraph("All registry data in this build is synthetic (mock). No government database is accessed. "
                        "The system assists the officer; it never declares guilt or denies entry.", SMALL),
              PageBreak()]

    # ---------------------------------------------------------------- 1 problem
    story += [Paragraph("1. The problem", H1),
              p("SSB guards two open, treaty-based land borders: India–Nepal (1,751 km) and India–Bhutan (699 km). "
                "Indian and Nepali citizens cross under treaty right, often with no passport at all, through Border "
                "Out Posts and patrols rather than fixed immigration desks. The fraud risk is concentrated in "
                "<b>impersonation</b> (someone else's document) and <b>fraudulent or altered documents</b> — not in "
                "universal scanning of every crosser."),
              Paragraph("What makes it hard in the field", H2)]
    story += bullets([
        "<b>Many document types, three countries:</b> passports, visas and visa stamps, entry permits, driving "
        "licences, Aadhaar, citizenship certificates, immigration stamps — in English, Hindi and Nepali (Devanagari) "
        "and Dzongkha.",
        "<b>Unreliable connectivity:</b> a post may be online, on a weak link, or offline at any moment. A tool that "
        "stops without a connection is not used.",
        "<b>No per-post infrastructure:</b> no public evidence of computers or servers at every post — the officer "
        "has a phone.",
        "<b>Checks are manual and inconsistent:</b> MRZ check digits, expiry dates, stamp/checkpoint consistency and "
        "photo comparison are slow to do by eye and easy to miss under pressure.",
        "<b>Decisions must stay with the officer</b> and be explainable afterwards — a bare risk number is not "
        "acceptable evidence.",
        "<b>Privacy:</b> identity documents and faces are sensitive personal data.",
    ])

    # ---------------------------------------------------------------- 2 solution
    story += [Paragraph("2. Proposed solution and how it addresses the problem", H1),
              p("<b>One Android app + one FastAPI server + one web console.</b> The officer photographs the "
                "document and takes a live photo; the phone does the fast, private work (finding regions, reading "
                "text, validating the MRZ, liveness); the server runs the heavy checks and returns an explainable "
                "result; the officer decides — Clear, or Send to admin — and an admin answers from the web console."),
              table([
                  ["Problem", "How PramaanAI addresses it"],
                  ["Impersonation", "Live photo compared with the document photo (InsightFace); liveness prompts "
                                    "(blink, head turn) and an on-device anti-spoof model; identity graph shows the "
                                    "same face under another name, or the same document number under another name."],
                  ["Altered / fraudulent documents", "MRZ check digits (ICAO 9303) and MRZ-vs-printed consistency; "
                                                     "QR / digital-signature checks; region-level image forensics; "
                                                     "stamp checked against the official checkpoint reference; "
                                                     "date logic; registry comparison (mock)."],
                  ["Many document types and scripts", "Region detection (YOLO11n) + PP-OCR for Latin text and a "
                                                      "Devanagari recogniser for Nepali/Hindi; document type from "
                                                      "MRZ, keywords and regions; e-Visa, e-Aadhaar, DigiLocker and "
                                                      "online permits recognised; PDFs accepted."],
                  ["Connectivity", "Live Online / Weak / Offline check; offline captures are encrypted "
                                   "(Android Keystore) and verified automatically when the link returns; retries "
                                   "are idempotent."],
                  ["Explainability", "Every result names the check and the reason, marks the exact place on the "
                                     "document, and writes a suggested reason for the officer's decision."],
                  ["Officer decides", "The system never denies entry or declares guilt: Clear or Send to admin; "
                                      "the admin sees a suggested action and confirms it."],
                  ["Privacy", "Only region crops and phone-read text are sent for verification — never the full "
                              "frame; evidence images are attached to a case only for admin review; Aadhaar "
                              "numbers masked; raw OCR text not stored."],
              ], [42, 128]),
              Spacer(1, 6)]

    # ---------------------------------------------------------------- 3 innovation
    story += [Paragraph("3. Innovation and uniqueness", H1)]
    story += bullets([
        "<b>Border-specific rules engine:</b> India–Nepal treaty nationals need no visa or stamp; India–Bhutan "
        "post-2022 rules; designated crossings for third-country nationals — the result is judged against the "
        "crossing, not a generic checklist. The crossing comes from the stamp, the officer's post, or the officer.",
        "<b>Explainable, evidence-first results:</b> named reasons, problem boxes on the original document, "
        "field sources (server OCR / MRZ / QR / phone / Devanagari), and a risk breakdown — never a mystery score.",
        "<b>Split intelligence for weak links:</b> a 10.6 MB YOLO11n model on the phone sends only crops in one "
        "request; everything works offline and syncs later.",
        "<b>Two-sided liveness:</b> active prompts (blink, head turn — the same tracked face must complete both) "
        "plus a passive anti-spoof model, both on the phone; the server reports them as evidence.",
        "<b>Devanagari document reading</b> with Nepali dates kept in Bikram Sambat — never mis-read as Gregorian.",
        "<b>Closed loop with the admin:</b> Send to admin carries the evidence; the admin sees an automatically "
        "suggested action (Clear / Re-capture / Manual review) and the answer returns to the officer's phone.",
        "<b>Honest by design:</b> mock data is labelled everywhere; checks that cannot run say so "
        "(e.g. e-Visa must be confirmed on the official portal) instead of faking a confident answer.",
    ])

    # ---------------------------------------------------------------- 4 architecture / tech
    story += [PageBreak(), Paragraph("4. Technical approach", H1), architecture(),
              Paragraph("Figure 1 — Architecture: the phone sends crops and text; the server returns an explainable "
                        "result; the web console answers cases.", SMALL),
              Paragraph("Technology stack", H2),
              table([
                  ["Layer", "Technologies"],
                  ["Android app", "Kotlin, Jetpack Compose, Material 3, CameraX, ML Kit (text, face, barcode), "
                                  "ONNX Runtime (YOLO11n regions, MiniFASNet-V2 anti-spoof), PdfRenderer, Retrofit, "
                                  "WorkManager, Android Keystore (AES-GCM), 7 UI languages"],
                  ["Server", "Python, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL (SQLite for local dev), "
                             "JWT + Argon2, RapidOCR / PP-OCR (ONNX) incl. PP-OCRv5 Devanagari, InsightFace "
                             "(SCRFD + ArcFace-family), OpenCV, cryptography (signatures), NetworkX (identity graph)"],
                  ["Web console", "React 19, TypeScript, Vite, Tailwind CSS, Recharts"],
                  ["Operations", "Docker, Render (API + PostgreSQL + static site), GitHub Releases (APK)"],
              ], [32, 138]),
              Paragraph("Verification checks (server)", H2),
              table([
                  ["Area", "Checks"],
                  ["Machine-readable", "MRZ structure and check digits (TD1/TD2/TD3, MRV-A/B); MRZ vs printed "
                                       "details; QR/barcode decoding and QR vs printed; digital signature against a "
                                       "configured trust store"],
                  ["Content", "Key fields read; date order and validity; number formats; nationality codes; "
                              "cross-document consistency (passport vs visa)"],
                  ["Stamps and rules", "Stamp detection and text reading; checkpoint matched to the official "
                                       "reference; stamp vs visa; India–Nepal / India–Bhutan crossing rules"],
                  ["Face and liveness", "Document photo quality; secondary (ghost) portrait; face match with the "
                                        "live photo; liveness report from the phone"],
                  ["Image integrity", "Region-vs-surroundings forensics (noise, sharpness, error level, JPEG grid, "
                                      "duplicates); capture quality"],
                  ["Registry and identity", "Mock registry lookup (labelled); duplicate document number; face "
                                            "cluster (same face, other names)"],
              ], [34, 136])]

    # ---------------------------------------------------------------- 5 methodology / workflow
    story += [PageBreak(), Paragraph("5. Methodology and workflow", H1),
              p("The design follows four rules taken from the problem: <b>work at the post with a phone</b>, "
                "<b>never block on connectivity</b>, <b>explain every flag</b>, and <b>leave the decision to the "
                "officer</b>. Each check is a separate, swappable service (OCR, MRZ, face, registry, forensics) with "
                "a clearly labelled mock where a real government system would sit."),
              workflow(),
              Paragraph("Result states", H2),
              p("<b>Verified</b> (all blocking checks pass) · <b>Review required</b> (a named inconsistency) · "
                "<b>Not verified</b> (a check could not run, e.g. an unreadable region) · <b>Official verification "
                "required</b> (e.g. Aadhaar or e-Visa, which only the issuing service can confirm). Advisory checks "
                "(liveness, Devanagari text, electronic documents) are shown but never change the status on their "
                "own.")]

    # ---------------------------------------------------------------- 6 implementation
    story += [Paragraph("6. Implementation process", H1),
              table([
                  ["Phase", "Delivered"],
                  ["1 — Server", "FastAPI services, models and migrations, mock registries, explainable decision "
                                 "engine, audit hash chain; verified through /docs and automated tests."],
                  ["2 — Android", "On-device region detection and text/MRZ, live connectivity state, encrypted "
                                  "offline queue with sync, Verify-document flow, liveness, PDF input."],
                  ["3 — Web console", "Verification Desk, case review with document evidence, automatic suggested "
                                      "action, identity intelligence, analytics, audit trail; public landing page."],
                  ["4 — Integration", "End-to-end wiring check (phone → server → admin → phone) run against the "
                                      "live deployment; UI polish and translations."],
              ], [34, 136]),
              Paragraph("Demo posts and accounts", H2),
              p("The demo deployment is set on SSB's own borders. Each post matches the official checkpoint "
                "reference data, so an officer's assigned post fills in the crossing and its rules automatically."),
              table([
                  ["Post (code)", "Border", "Location", "Demo login"],
                  ["Raxaul (RAX)", "India–Nepal", "Bihar", "raxaul_officer"],
                  ["Sunauli (SUN)", "India–Nepal", "Uttar Pradesh", "sunauli_officer"],
                  ["Jaigaon (JGN)", "India–Bhutan", "West Bengal", "jaigaon_officer"],
                  ["Web console (admin)", "—", "—", "it_admin"],
              ], [40, 34, 40, 56]),
              Paragraph("Password for all demo accounts: BorderShield123. All case data in the demo is synthetic.",
                        SMALL),
              Paragraph("Quality evidence", H2)]
    story += bullets([
        "<b>187 automated server tests</b> pass (unit and API).",
        "<b>End-to-end wiring check: 24/24</b> on the live Render deployment (verify → case → evidence → send to "
        "admin → admin decision → the phone sees the answer → audit chain intact).",
        "<b>On-device parity test</b> for the anti-spoof model: Android scores match the Python reference within "
        "0.05.",
        "<b>Fresh-database migrations</b> verified on SQLite and PostgreSQL 16.",
    ])

    # ---------------------------------------------------------------- 7 results
    story += [Spacer(1, 8), Paragraph("7. Measured results", H1),
              p("Synthetic documents were generated by the project with layouts matching its own templates, so "
                "synthetic numbers are <b>optimistic</b> and not evidence of real-world accuracy. The real set is "
                "57 labelled photographs of real documents (kept local, never published)."),
              table([
                  ["Measure", "Result"],
                  ["Overall status matches expectation (46 synthetic cases)", "0.891"],
                  ["Expected check-level outcomes (synthetic)", "53 / 56"],
                  ["Needs-attention detection, F1 (synthetic)", "0.925 (precision 0.939, recall 0.912)"],
                  ["OCR key fields (synthetic)", "18 / 18"],
                  ["Document type, real photographs", "0.877 (57 documents)"],
                  ["Phone path vs server path (39 real captures replayed)", "status 38/39, type 39/39"],
                  ["Devanagari text on Nepal ID / citizenship / permit / Aadhaar", "0 characters before; now read "
                                                                                   "(conf. 0.76–0.93), +0.07 s/doc"],
                  ["Speed-ups (6-image profile)", "67.8 s → 45.6 s, identical accuracy"],
                  ["Server memory (3 + 2 parallel verifications)", "685 MB → about 420 MB peak"],
                  ["Tampering detection (synthetic)", "recall 0.33 — the weakest module (see §8)"],
              ], [110, 60]),
              Paragraph("Where it is weak — stated plainly", H2)]
    story += bullets([
        "Pixel-level tampering (a re-compressed photo or pasted text) is often missed; flags are advisory.",
        "Handwritten entries on visa stamps are not read reliably: 0/7 with the current OCR, 1/7 even on "
        "hand-placed crops. The officer reads them from the document image.",
        "Anti-spoof was checked on a handful of images: printed/document faces were flagged, but a clean digital "
        "passport photo passed as real — liveness prompts are the stronger signal; the score is advisory until "
        "calibrated on field captures.",
        "Bengali, Gurmukhi and Dzongkha document text is not read; the Dzongkha UI is partly English.",
    ])

    # ---------------------------------------------------------------- 8 feasibility / viability
    story += [Paragraph("8. Feasibility and viability", H1),
              table([
                  ["Aspect", "Assessment"],
                  ["Technical", "Runs today on a mid-range Android phone and a 512 MB cloud instance; all models "
                                "are open (Apache-2.0 / MIT-compatible) and run on CPU with ONNX Runtime."],
                  ["Operational", "Fits existing SSB practice: the officer keeps the decision; no new hardware at "
                                  "posts; works offline; 7 UI languages."],
                  ["Integration", "Every external dependency (registry, UIDAI, e-Visa status, DigiLocker, ePassport "
                                  "PKI) sits behind an interface with a labelled mock, ready for an authorised API."],
                  ["Cost", "Open-source stack; one central server scales horizontally (stateless API, bounded "
                           "concurrency, 503 + retry when saturated)."],
                  ["Security and privacy", "See section 9."],
              ], [34, 136])]

    # ---------------------------------------------------------------- 9 security
    story += [PageBreak(), Paragraph("9. Security", H1),
              p("Security is applied at every layer: the officer's phone, the network, the server and the stored "
                "records. Every item below is implemented in this build."),
              table([
                  ["Layer", "Measure", "How"],
                  ["Access", "Sign-in", "JWT access tokens (30 min) and refresh tokens (24 h); passwords hashed with "
                                        "Argon2; login limited to 5 attempts per minute per address."],
                  ["Access", "Roles", "Enforced on the server, not only in the UI: officers verify and send; only "
                                      "admins (Reviewer) decide cases, manage users and devices, or remove data."],
                  ["Access", "Session", "Auto-lock after inactivity with a warning; tokens kept in encrypted storage "
                                        "on the phone; lost devices can be disabled or revoked by the admin."],
                  ["Transport", "Encryption in transit", "HTTPS (TLS) between the phone, the web console and the "
                                                         "server."],
                  ["Phone", "Encryption at rest", "Captures and the offline queue are encrypted with AES-GCM using a "
                                                  "key held in the Android Keystore; images are deleted "
                                                  "automatically after the retention period."],
                  ["Data", "Minimisation", "Only detected regions and phone-read text are sent for verification — "
                                           "never the full frame; the verify endpoints process images in memory "
                                           "and keep only SHA-256 hashes; raw OCR text is not stored; Aadhaar is "
                                           "masked (XXXX XXXX 1234); evidence images are attached only when a case "
                                           "is opened for review."],
                  ["Data", "Input limits", "Uploads ≤ 10 MB and ≤ 40 MP, 1–4 images; region crops covering > 90% "
                                           "of the frame are rejected; every request is schema-validated."],
                  ["Integrity", "Tamper-evident records", "Each verification is hashed (SHA-256), linked to the "
                                                          "previous record and signed with HMAC-SHA256; the whole "
                                                          "chain can be re-verified at any time."],
                  ["Integrity", "Audit trail", "Created, viewed, sent, decided and removed events are logged with "
                                               "the actor; removed test data stays in the chain, marked withdrawn."],
                  ["Integrity", "Document signatures", "Signed QR data is checked against a configured trust store "
                                                       "(Ed25519); altered data fails the check."],
                  ["Identity", "Anti-impersonation", "Face match with the live photo, blink / head-turn liveness "
                                                     "prompts and an on-device anti-spoof score."],
                  ["Server", "Hardening", "Secrets only in environment variables; personal data redacted from "
                                          "server logs; bounded concurrency (503 + retry when busy)."],
                  ["Ethics", "Fairness", "No emotion, skin temperature, nationality, religion or ethnicity used as a "
                                         "signal; wording never accuses; mock data labelled everywhere."],
              ], [22, 36, 112]),
              Paragraph("Security workflow — one verification, end to end", H2),
              table([
                  ["Step", "What protects it"],
                  ["1  Sign in", "Argon2-checked password, rate-limited login, short-lived JWT; role attached to "
                                 "the token."],
                  ["2  Capture", "Image stays on the phone, encrypted (AES-GCM, Keystore key)."],
                  ["3  Minimise", "Phone finds the regions; only crops and text are prepared — never the full frame."],
                  ["4  Send", "TLS; bearer token checked; offline requests wait encrypted and are retried safely "
                              "(same request id = same record, never a duplicate)."],
                  ["5  Check", "Server validates size and schema, processes images in memory, stores only hashes and "
                               "a minimised result."],
                  ["6  Record", "Result hashed, linked to the previous record, HMAC-signed; audit event written."],
                  ["7  Decide", "Officer clears or sends to admin; only an admin (server-checked role) can decide "
                                "the case; every decision is audit-logged."],
                  ["8  Retain", "Phone images auto-deleted after the retention period; session auto-locks; the "
                                "chain can be re-verified at any time."],
              ], [30, 140])]

    # ---------------------------------------------------------------- 9 challenges
    story += [PageBreak(), Paragraph("10. Challenges and the strategy used to solve them", H1),
              table([
                  ["Challenge", "Strategy"],
                  ["Weak or no connectivity", "Phone-side detection and MRZ; one small request of crops; live "
                                              "Online/Weak/Offline check; encrypted queue; idempotent sync."],
                  ["Phone APK size (227 MB)", "ARM-only native libraries and R8 shrinking → 97 MB, with ML Kit keep "
                                              "rules to avoid release-only crashes."],
                  ["Same person reported as 'no match'", "Tight crops had no detectable face; added padded "
                                                         "detection variants, 'no face' = inconclusive (never a "
                                                         "mismatch), and a 'possible match → review' band."],
                  ["Two portraits on passports/licences flagged", "Recognised the secondary (ghost) portrait as a "
                                                                   "normal feature and compared it with the main "
                                                                   "photo instead."],
                  ["Nepali/Hindi documents unreadable", "Devanagari recogniser on the boxes the Latin pass drops; "
                                                        "separate fields; Bikram Sambat kept."],
                  ["Handwriting", "Measured three approaches; none reliable → not shipped, documented honestly."],
                  ["Server out of memory on Render", "Profiled per model; MediaPipe loaded only when used; shared "
                                                     "OCR engine pool; one verification at a time; malloc tuning "
                                                     "→ 685 MB to about 420 MB."],
                  ["Photos or screens held up to the camera", "Random blink / head-turn prompts on the same tracked "
                                                              "face + on-device anti-spoof score."],
                  ["Explainability for the admin", "Problem boxes on the document, identity links, and an "
                                                   "automatic suggested action with its reasons."],
                  ["Database differences (SQLite vs PostgreSQL)", "Found write-order and ID-type bugs by running the "
                                                                  "full flow against PostgreSQL 16; fixed "
                                                                  "migrations for fresh databases."],
              ], [48, 122])]

    # ---------------------------------------------------------------- 10 impact
    story += [Paragraph("11. Impact and benefits", H1)]
    story += bullets([
        "<b>Faster, more consistent checks:</b> MRZ digits, dates, stamps and face comparison in one flow instead of "
        "by eye — the officer spends time on the cases that need it.",
        "<b>Fewer impersonation misses:</b> live photo + liveness + identity graph target the main real-world risk.",
        "<b>Works where the border is:</b> offline-first, phone-only, in the officer's language.",
        "<b>Accountability:</b> every decision is explained, reviewed when needed, and recorded in a tamper-evident "
        "audit trail.",
        "<b>Fair by design:</b> no emotion, skin temperature, nationality, religion or ethnicity used as a signal; "
        "the wording never accuses; the officer decides.",
        "<b>Ready to connect:</b> swappable services let authorised government APIs replace the mocks without "
        "changing the app.",
    ])

    # ---------------------------------------------------------------- 11 screenshots
    story += [PageBreak(), Paragraph("12. Screens (synthetic data)", H1),
              shot("03-verification-desk.png", 170, "Verification Desk — cases from the app with their verification "
                                                    "result; earlier-flow and demo cases behind a toggle."),
              shot("04-case-review.png", 120, "Case review — document with problem areas, face match, identity "
                                              "links, fields with sources, suggested wording."),
              PageBreak(),
              shot("05-take-action.png", 80, "Take action — automatic suggestion written from the checks; 'Use "
                                             "suggestion' pre-fills the form, the admin confirms."),
              shot("02-overview.png", 170, "Overview — live operational status."),
              shot("09-area-monitoring.png", 170, "Area Monitoring — per-post activity at Jaigaon, Raxaul and "
                                                  "Sunauli."),
              shot("11-analytics.png", 170, "Analytics & Intelligence.")]

    # ---------------------------------------------------------------- 12 future
    story += [PageBreak(), Paragraph("13. Future work", H1),
              table([
                  ["Idea", "Implementation and methodology"],
                  ["Officer assistant chatbot", "A chat panel in the app and console that answers procedure "
                                                "questions (\"Does a US national need a visa at Sunauli?\", \"Which "
                                                "crossings are designated for foreigners?\") in the officer's "
                                                "language. Retrieval-augmented generation over the project's own "
                                                "reference data (border rules, checkpoint list, SOPs) with "
                                                "citations; server-side LLM with an offline FAQ fallback on the "
                                                "phone. It explains rules and results — it never makes the decision."],
                  ["Geo-fencing", "Checkpoint polygons in the reference data; GNSS/NavIC location on the phone "
                                  "fills the post automatically and tags each verification; advisory when outside a "
                                  "designated crossing; mock-location and impossible-speed checks."],
                  ["CCTV at crossings", "Edge box reads RTSP feeds: YOLO person/vehicle detection and tracking, "
                                        "line-crossing counts, loitering and night-movement alerts, number-plate "
                                        "reading against the (mock) vehicle-permit registry. No blanket face "
                                        "recognition — only with legal authorisation (DPDP Act 2023)."],
                  ["Satellite", "Satellite messaging for posts with no network (tiny case summaries, full sync "
                                "later); Sentinel-2 / Bhuvan change detection along the border to suggest patrol "
                                "areas; NavIC for location."],
                  ["ePassport chip (NFC)", "Read DG1/DG2 with BAC/PACE keyed from the MRZ; compare chip data and "
                                           "photo with the printed page and the live photo; passive authentication "
                                           "once an authorised CSCA trust list is available."],
                  ["Official e-document checks", "Authorised APIs for e-Visa status, UIDAI secure QR, DigiLocker / "
                                                 "Parivahan in place of today's 'confirm on the official service' "
                                                 "guidance."],
                  ["Handwriting", "Label handwritten-field boxes (new YOLO class) and fine-tune a handwriting "
                                  "recogniser on border forms."],
                  ["More scripts", "Bengali, Gurmukhi and Dzongkha document text; complete Dzongkha UI with a "
                                   "native reviewer."],
                  ["Calibration", "Field pilot to calibrate the anti-spoof threshold and forensic flags on real "
                                  "captures before any check is made blocking."],
              ], [40, 130]),
              Paragraph("Planned security", H2),
              table([
                  ["Addition", "Purpose"],
                  ["Certificate pinning + mutual TLS", "The app talks only to the genuine server; only registered "
                                                       "devices can connect."],
                  ["Device attestation (Play Integrity)", "Refuse rooted, emulated or tampered phones."],
                  ["Multi-factor sign-in for admins", "Hardware key or OTP for the web console."],
                  ["Keys in a KMS / HSM with rotation", "Signing and encryption keys never leave secure hardware."],
                  ["Encryption of stored records", "Field-level encryption of personal data in the database."],
                  ["External anchoring of the audit chain", "Periodic signed timestamps of the chain head from a "
                                                            "trusted time-stamping authority."],
                  ["Post-scoped access", "Officers see only their own post's data; supervisors their area."],
                  ["Security monitoring", "Alerts on unusual sign-ins, bulk exports or repeated failed checks."],
                  ["Shared rate limiting", "Login and API limits enforced across all server instances."],
                  ["DPDP Act 2023 compliance", "Retention schedules, purpose limitation and data-subject "
                                               "procedures agreed with MHA / SSB."],
                  ["Independent security audit", "VAPT by a CERT-In empanelled auditor before field deployment."],
              ], [58, 112]),
              Spacer(1, 10),
              Paragraph("Data notice: registry lookups in this build use fictional mock data only; no real government "
                        "database is accessed. Real document photographs used for evaluation are kept locally and "
                        "are not published.", SMALL)]

    doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=16 * mm, title="PramaanAI — Project Report", author="Team AlphaX",
                            subject="SIH 2026 PS 26188")
    doc.build(story, onFirstPage=lambda c, d: None, onLaterPages=on_page)
    print(OUT)


if __name__ == "__main__":
    build()
