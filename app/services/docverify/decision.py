"""Final decision engine — evidence in, officer-facing assessment out.

Overall status precedence (blocking checks only; advisory checks are shown
but never drive the status):

  FAIL                  >= 2 independent STRONG deterministic failures from
                        different evidence sources (e.g. MRZ check digits AND
                        a registry mismatch). One weak or single signal is
                        never enough.
  REVIEW_REQUIRED       any blocking REVIEW_REQUIRED, or exactly one FAIL
  NOT_VERIFIED          essential checks could not run (unreadable, type
                        uncertain, poor image)
  OFFICIAL_VERIFICATION_REQUIRED   only an official mechanism can conclude
  REGISTRY_NOT_AVAILABLE           everything else passed, registry absent
  PASS

Risk score (problem statement): 0-100, the sum of named contributions, each
tied to a check — a triage indicator, not a probability of fraud.
"""
from __future__ import annotations

from typing import Any

from app.services.docverify.types import CheckResult, CheckStatus, OfficerLine, OfficerSummary

_PRECEDENCE = [CheckStatus.FAIL, CheckStatus.REVIEW_REQUIRED, CheckStatus.NOT_VERIFIED,
               CheckStatus.OFFICIAL_VERIFICATION_REQUIRED, CheckStatus.REGISTRY_NOT_AVAILABLE, CheckStatus.PASS]

# name -> (source family, plain PASS text, plain issue text)
PLAIN: dict[str, tuple[str, str, str]] = {
    "image_quality": ("image", "Image is clear enough to read", "Image quality is too low — recapture recommended"),
    "document_type": ("classifier", "Document type identified", "Document type could not be identified with confidence"),
    "ocr": ("ocr", "Text extracted", "Key printed details could not be read"),
    "electronic_document": ("official", "Electronic document confirmed with the issuing service", "Electronic document — confirm with the issuing service"),
    "ocr_devanagari": ("ocr", "Nepali/Hindi (Devanagari) text read", "Nepali/Hindi (Devanagari) text could not be read"),
    "field_format": ("format", "Document number format is valid", "Document number format does not match this document type"),
    "document_validity": ("dates", "Document is within its validity period", "Document validity needs attention"),
    "date_logic": ("dates", "Dates are in a sensible order", "Dates on the document are not in a sensible order"),
    "mrz_structure": ("mrz", "Machine-readable zone found and well-formed", "Machine-readable zone missing or malformed"),
    "mrz_check_digits": ("mrz", "Machine-readable zone check digits correct", "Machine-readable zone check digit failed"),
    "machine_readable_code": ("qr", "QR/barcode read", "QR/barcode could not be read or is missing"),
    "identity_consistency": ("consistency", "Identity information consistent", "Identity information differs between sources"),
    "mrz_consistency": ("mrz", "MRZ consistent with printed details", "MRZ differs from printed details"),
    "qr_consistency": ("qr", "QR/barcode data consistent with printed details", "QR/barcode data differs from printed details"),
    "registry_consistency": ("registry", "Consistent with reference registry (mock)", "Differs from reference registry (mock)"),
    "stamp_consistency": ("stamp", "Stamp consistent with visa and checkpoint reference", "Stamp inconsistent with visa or checkpoint reference"),
    "cross_document": ("consistency", "Documents agree with each other", "Documents do not agree with each other"),
    "registry": ("registry", "Matches the reference registry (mock)", "Reference registry check needs attention"),
    "photo": ("photo", "Photo location consistent", "Photo needs review"),
    "liveness": ("face", "Live person confirmed on camera", "Liveness of the live photo needs confirmation"),
    "face_verification": ("face", "Face matches", "Face comparison needs review"),
    "layout": ("layout", "Layout matches the document template", "Layout differs from the document template"),
    "security_features": ("security", "Visual security features observed", "Visual security features need review"),
    "yellow_gold_feature": ("security", "Yellow/gold visual feature consistent with template", "Yellow/gold visual feature needs review"),
    "digital_signature": ("signature", "Digital signature verified", "Digital signature did not verify"),
    "aadhaar_number": ("format", "Aadhaar number checksum valid", "Aadhaar number checksum failed"),
    "aadhaar_official": ("official", "Aadhaar verified officially", "Aadhaar requires official verification"),
    "epassport_chip": ("official", "Chip verified", "Chip not verified (no authorised reader)"),
    "stamp_detection": ("stamp", "Stamp detected", "No stamp detected"),
    "stamp_identification": ("stamp", "Stamp text read and identified", "Stamp only partly identified"),
    "authority_identification": ("stamp", "Authority identified", "Issuing authority not identified"),
    "checkpoint_match": ("stamp", "Checkpoint matched to official reference", "Checkpoint not matched"),
    "stamp_reference": ("stamp", "Stamp consistent with reference", "Stamp differs from reference"),
    "stamp_forensics": ("tampering", "No manipulation indicators around stamp", "Stamp requires review"),
    "tampering_analysis": ("tampering", "No strong tampering indicator", "Possible image manipulation — review"),
    "accepted_travel_document": ("rules", "Accepted document for this crossing", "Document acceptance for this crossing needs confirmation"),
    "visa_requirement": ("rules", "Visa requirement satisfied", "Required visa not presented"),
    "stamp_requirement": ("rules", "Stamp requirement satisfied", "Expected stamp not found"),
    "designated_crossing": ("rules", "Designated crossing", "Stamp checkpoint is not a designated foreigner crossing"),
    "entry_permit": ("rules", "Entry permit presented", "Entry permit not presented"),
    "border_rules": ("rules", "Crossing rules evaluated", "Crossing rules not evaluated"),
    "document_detected": ("image", "Document detected", "Document outline not located"),
    "document_framing": ("image", "Whole document in frame", "Document may be cropped"),
    "document_proportions": ("layout", "Document proportions as expected", "Unexpected document proportions"),
    "ocr_confidence": ("ocr", "Text read with good confidence", "Low text-reading confidence"),
    "nationality_code": ("format", "Country codes valid", "Invalid country code"),
    "document_face_quality": ("photo", "Document photo face is clear", "Document photo face quality is low"),
    "reference_photo_match": ("face", "Document photo matches the registry photo", "Document photo differs from the registry photo"),
    "face_manipulation_indicators": ("face", "No replayed or synthetic-face indicators", "Possible replayed or synthetic face"),
}

_WEIGHTS = {
    (CheckStatus.FAIL, True): 35, (CheckStatus.FAIL, False): 25,
    (CheckStatus.REVIEW_REQUIRED, True): 20, (CheckStatus.REVIEW_REQUIRED, False): 12,
    (CheckStatus.NOT_VERIFIED, True): 6,
}


def overall_status(checks: list[CheckResult]) -> CheckStatus:
    blocking = [c for c in checks if c.blocking and c.status != CheckStatus.NOT_APPLICABLE]
    strong_fail_sources = {PLAIN.get(c.name, (c.name,))[0] for c in blocking
                           if c.status == CheckStatus.FAIL and c.strong_evidence}
    if len(strong_fail_sources) >= 2:
        return CheckStatus.FAIL
    statuses = {c.status for c in blocking}
    if CheckStatus.FAIL in statuses or CheckStatus.REVIEW_REQUIRED in statuses:
        return CheckStatus.REVIEW_REQUIRED
    for s in _PRECEDENCE[2:]:
        if s in statuses:
            return s
    return CheckStatus.PASS if blocking else CheckStatus.NOT_VERIFIED


def risk(checks: list[CheckResult]) -> tuple[int, str, list[dict[str, Any]]]:
    parts: list[dict[str, Any]] = []
    for c in checks:
        if c.status in (CheckStatus.PASS, CheckStatus.NOT_APPLICABLE):
            continue
        if "unregistered_document" in (c.details.get("flags") or []):
            # No registry record: the identity could not be confirmed at all,
            # so the case is treated as high risk until an officer checks it.
            weight = 60
        elif not c.blocking:
            weight = 5 if c.status in (CheckStatus.REVIEW_REQUIRED, CheckStatus.FAIL) else 0
        else:
            weight = _WEIGHTS.get((c.status, c.strong_evidence), _WEIGHTS.get((c.status, True), 0))
        if weight:
            parts.append({"check": c.name, "status": c.status.value, "points": weight, "reason": c.summary})
    score = min(100, sum(p["points"] for p in parts))
    level = "HIGH" if score >= 60 else "MEDIUM" if score >= 25 else "LOW"
    return score, level, sorted(parts, key=lambda p: -p["points"])


def evidence_confidence(checks: list[CheckResult]) -> float:
    """How complete the evidence is: share of applicable checks that could
    actually be performed (not NOT_VERIFIED / unavailable)."""
    applicable = [c for c in checks if c.status != CheckStatus.NOT_APPLICABLE]
    if not applicable:
        return 0.0
    performed = [c for c in applicable if c.status not in (CheckStatus.NOT_VERIFIED, CheckStatus.REGISTRY_NOT_AVAILABLE,
                                                           CheckStatus.OFFICIAL_VERIFICATION_REQUIRED,
                                                           CheckStatus.REFERENCE_NOT_AVAILABLE)]
    return round(len(performed) / len(applicable), 2)


HEADLINES = {
    CheckStatus.PASS: "DOCUMENT VERIFIED",
    CheckStatus.REVIEW_REQUIRED: "REVIEW REQUIRED",
    CheckStatus.FAIL: "VERIFICATION FAILED — OFFICER REVIEW REQUIRED",
    CheckStatus.NOT_VERIFIED: "NOT VERIFIED",
    CheckStatus.REGISTRY_NOT_AVAILABLE: "CHECKS PASSED — REGISTRY NOT AVAILABLE",
    CheckStatus.OFFICIAL_VERIFICATION_REQUIRED: "OFFICIAL VERIFICATION REQUIRED",
}


def officer_summary(status: CheckStatus, facts: dict[str, str], checks: list[CheckResult],
                    offline: bool) -> tuple[OfficerSummary, str]:
    lines: list[OfficerLine] = []
    seen: set[str] = set()
    order = sorted(checks, key=lambda c: (c.status == CheckStatus.PASS, not c.blocking))
    for c in order:
        if c.status == CheckStatus.NOT_APPLICABLE:
            continue
        family, ok_text, issue_text = PLAIN.get(c.name, (c.name, c.name.replace("_", " ").capitalize(), c.summary))
        if c.status == CheckStatus.PASS:
            text, icon = ok_text, "ok"
        elif c.status == CheckStatus.FAIL:
            text, icon = f"{issue_text}: {c.summary}", "fail"
        elif c.status == CheckStatus.REVIEW_REQUIRED:
            text, icon = f"{issue_text}: {c.summary}", "warn"
        else:
            text, icon = c.summary, "info"
        if text in seen:
            continue
        seen.add(text)
        lines.append(OfficerLine(icon=icon, text=text))
    # Checks already passing are summarised last so issues are read first.
    lines.sort(key=lambda l: {"fail": 0, "warn": 1, "info": 2, "ok": 3}[l.icon])
    headline = HEADLINES[status]
    if offline:
        headline = f"OFFLINE VERIFICATION — {headline}"
        lines.insert(0, OfficerLine(icon="info", text="OFFLINE — external registry verification unavailable"))
    issues = [c for c in checks if c.blocking and c.status in (CheckStatus.FAIL, CheckStatus.REVIEW_REQUIRED)]
    if issues:
        explanation = "; ".join(dict.fromkeys(c.summary for c in issues[:3]))
    elif status == CheckStatus.PASS:
        explanation = "All applicable checks passed. The officer makes the final decision."
    else:
        pending = [c.summary for c in checks if c.blocking and c.status not in (CheckStatus.PASS, CheckStatus.NOT_APPLICABLE)]
        explanation = pending[0] if pending else "Evidence incomplete."
    return OfficerSummary(headline=headline, facts=facts, lines=lines), explanation


def suggested_reasons(status: CheckStatus, checks: list[CheckResult]) -> dict[str, str]:
    """Editable, pre-written reasons for the officer's two actions — Clear,
    or Send to a reviewing officer — built only from the named checks, so the
    officer rarely has to type. Wording stays factual: it describes what was
    found, never a conclusion about the traveller."""
    def rank(c: CheckResult) -> tuple[int, int]:
        order = {CheckStatus.FAIL: 0, CheckStatus.REVIEW_REQUIRED: 1, CheckStatus.NOT_VERIFIED: 2,
                 CheckStatus.OFFICIAL_VERIFICATION_REQUIRED: 3}
        return (order.get(c.status, 9), 0 if c.blocking else 1)

    seen: set[str] = set()
    flagged: list[str] = []
    for c in sorted((c for c in checks if c.status in (CheckStatus.FAIL, CheckStatus.REVIEW_REQUIRED,
                                                      CheckStatus.NOT_VERIFIED,
                                                      CheckStatus.OFFICIAL_VERIFICATION_REQUIRED)), key=rank):
        text = c.summary.rstrip(".")
        if text not in seen:
            seen.add(text)
            flagged.append(text)
    top = "; ".join(flagged[:3])
    more = f" (+{len(flagged) - 3} more)" if len(flagged) > 3 else ""

    if status == CheckStatus.PASS:
        clear = "All automated checks passed and the document details are consistent."
    elif status == CheckStatus.REGISTRY_NOT_AVAILABLE:
        clear = "Document checks passed; registry not available here — cleared on inspection of the document."
    elif status == CheckStatus.OFFICIAL_VERIFICATION_REQUIRED:
        clear = ("Cleared after inspection by the officer; official verification is not available at this post. "
                 f"Noted: {top}{more}.")
    else:
        clear = f"Cleared after inspection by the officer. Noted: {top}{more}."
    send = (f"Admin review requested: {top}{more}." if flagged else
            "Admin review requested for confirmation — no automated check reported an issue.")
    return {"clear": clear, "send": send}
