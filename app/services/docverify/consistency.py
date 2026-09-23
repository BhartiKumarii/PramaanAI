"""Unified cross-field / cross-document consistency engine.

Compares, and records separately (one row per comparison, both values shown):
  OCR <-> MRZ, OCR <-> QR/barcode, OCR <-> registry, passport <-> visa/permit,
  identity document <-> identity document, stamp <-> visa validity,
  stamp <-> checkpoint reference, expiry <-> verification date.

Result per comparison:
  CONSISTENT
  INCONSISTENCY_DETECTED     values genuinely differ
  POSSIBLE_OCR_CONFUSION     differ only by classic OCR confusions (0/O, 1/I...)
  PARTIAL_MATCH              names overlap but not fully (e.g. missing middle name)
"""
from __future__ import annotations

import re
from datetime import date
from difflib import SequenceMatcher
from typing import Any

from app.services.docverify.types import DocumentAnalysis, DocumentType, PASSPORT_TYPES, VISA_TYPES

_CONFUSABLE = str.maketrans({"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1", "Z": "2", "S": "5", "B": "8", "G": "6"})

_NATIONALITY_ICAO = {
    "INDIAN": "IND", "INDIA": "IND", "IND": "IND", "NEPALI": "NPL", "NEPALESE": "NPL", "NEPAL": "NPL", "NPL": "NPL",
    "BHUTANESE": "BTN", "BHUTAN": "BTN", "BTN": "BTN", "ITALIAN": "ITA", "ITA": "ITA", "BRITISH": "GBR", "GBR": "GBR",
    "AMERICAN": "USA", "USA": "USA", "GERMAN": "D", "D": "D", "DEU": "D", "CHINESE": "CHN", "CHN": "CHN",
    "BANGLADESHI": "BGD", "BGD": "BGD", "JAPANESE": "JPN", "JPN": "JPN", "FRENCH": "FRA", "FRA": "FRA",
}

LABELS = {
    "document_number": "document number", "passport_number": "passport number", "name": "name",
    "date_of_birth": "date of birth", "date_of_expiry": "expiry date", "nationality": "nationality", "sex": "sex",
}


def norm_number(v: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (v or "").upper())


def norm_name_tokens(v: str | None) -> list[str]:
    return [t for t in re.sub(r"[^A-Z ]", " ", (v or "").upper()).split() if len(t) > 1]


def norm_nationality(v: str | None) -> str | None:
    if not v:
        return None
    key = re.sub(r"[^A-Z]", "", v.upper())
    return _NATIONALITY_ICAO.get(key, key)


def compare_values(field: str, a: str | None, b: str | None) -> str | None:
    if not a or not b:
        return None
    if field in ("document_number", "passport_number", "visa_number", "permit_number"):
        na, nb = norm_number(a), norm_number(b)
        if na == nb:
            return "CONSISTENT"
        if na.translate(_CONFUSABLE) == nb.translate(_CONFUSABLE):
            return "POSSIBLE_OCR_CONFUSION"
        return "INCONSISTENCY_DETECTED"
    if field == "name":
        ta, tb = norm_name_tokens(a), norm_name_tokens(b)
        if not ta or not tb:
            return None
        sa, sb = set(ta), set(tb)
        if sa == sb or sa <= sb or sb <= sa:
            return "CONSISTENT"
        # OCR often drops the space between names ("ANANYASYNTHETIC"): the
        # names agree if one side's tokens tile the other's letters exactly.
        ca, cb = "".join(ta), "".join(tb)
        for tokens, other in ((ta, cb), (tb, ca)):
            if len("".join(tokens)) == len(other) and all(t in other for t in tokens):
                return "CONSISTENT"
        ratio = SequenceMatcher(None, " ".join(sorted(ta)), " ".join(sorted(tb))).ratio()
        if ratio >= 0.9:
            return "POSSIBLE_OCR_CONFUSION"
        if len(sa & sb) >= 1 and ratio >= 0.6:
            return "PARTIAL_MATCH"
        return "INCONSISTENCY_DETECTED"
    if field == "nationality":
        return "CONSISTENT" if norm_nationality(a) == norm_nationality(b) else "INCONSISTENCY_DETECTED"
    if field == "sex":
        return "CONSISTENT" if a.strip().upper()[:1] == b.strip().upper()[:1] else "INCONSISTENCY_DETECTED"
    return "CONSISTENT" if a.strip() == b.strip() else "INCONSISTENCY_DETECTED"


class ConsistencyEngine:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def add(self, comparison: str, field: str, source_a: str, a: str | None, source_b: str, b: str | None,
            doc_index: int | None, bbox: list[int] | None = None, strong: bool = True) -> None:
        result = compare_values(field, a, b)
        if result is None:
            return
        self.rows.append({
            "id": f"cmp-{len(self.rows) + 1}", "comparison": comparison, "field": field,
            "source_a": source_a, "value_a": a, "source_b": source_b, "value_b": b,
            "result": result, "strong": strong and result == "INCONSISTENCY_DETECTED",
            "document_index": doc_index, "bbox": bbox,
            "explanation": self._explain(field, source_a, a, source_b, b, result),
        })

    def add_fact(self, comparison: str, field: str, result: str, explanation: str, doc_index: int | None,
                 strong: bool = False, bbox: list[int] | None = None, values: dict | None = None) -> None:
        self.rows.append({"id": f"cmp-{len(self.rows) + 1}", "comparison": comparison, "field": field,
                          "result": result, "strong": strong, "document_index": doc_index, "bbox": bbox,
                          "explanation": explanation, **(values or {})})

    @staticmethod
    def _explain(field: str, sa: str, a: str | None, sb: str, b: str | None, result: str) -> str:
        label = LABELS.get(field, field.replace("_", " "))
        if result == "CONSISTENT":
            return f"{label} on {sa} matches {sb}"
        if result == "POSSIBLE_OCR_CONFUSION":
            return f"{label} on {sa} ({a}) and {sb} ({b}) differ only by characters OCR commonly confuses — check by eye"
        if result == "PARTIAL_MATCH":
            return f"{label} on {sa} ({a}) only partly matches {sb} ({b})"
        return f"{label} on {sa} ({a}) differs from {sb} ({b})"


def _identity(doc: DocumentAnalysis) -> dict[str, tuple[str, str, list[int] | None]]:
    """Best value per identity field: MRZ when its check digits pass, else OCR."""
    out: dict[str, tuple[str, str, list[int] | None]] = {}
    for key, fv in doc.fields.items():
        out[key] = (fv.value, "printed text", fv.bbox)
    mrz = doc.mrz
    if mrz and mrz.get("all_checks_valid"):
        mapping = {"document_number": mrz.get("document_number"), "name": mrz.get("full_name"),
                   "date_of_birth": mrz.get("date_of_birth_iso"), "date_of_expiry": mrz.get("date_of_expiry_iso"),
                   "nationality": mrz.get("nationality")}
        for k, v in mapping.items():
            if v:
                out[k] = (v, "MRZ", mrz.get("bbox"))
    return out


def run(documents: list[DocumentAnalysis], registry_results: dict[int, dict[str, Any]], on: date) -> ConsistencyEngine:
    eng = ConsistencyEngine()

    for doc in documents:
        i = doc.document_index
        f = doc.fields
        # OCR <-> MRZ
        if doc.mrz and not doc.mrz.get("format_error"):
            mb = doc.mrz.get("bbox")
            pairs = [("document_number", doc.mrz.get("document_number")), ("name", doc.mrz.get("full_name")),
                     ("date_of_birth", doc.mrz.get("date_of_birth_iso")),
                     ("date_of_expiry", doc.mrz.get("date_of_expiry_iso")),
                     ("nationality", doc.mrz.get("nationality")), ("sex", doc.mrz.get("sex"))]
            for key, mv in pairs:
                # An MRV (visa) MRZ's document-number field carries the visa number.
                is_visa = doc.document_type.document_type in VISA_TYPES
                ocr_key = "visa_number" if key == "document_number" and is_visa else key
                fv = f.get(ocr_key)
                eng.add("printed_vs_mrz", key, "printed text", fv.value if fv else None, "MRZ", mv, i,
                        bbox=fv.bbox if fv else mb)
        # OCR <-> QR / barcode
        for code in doc.codes:
            if not code.fields:
                continue
            src = "signed QR" if code.payload_kind == "SIGNED_STRUCTURED" else "QR/barcode"
            region = next((r.bbox for r in doc.regions if r.id == code.region_id), None)
            qr_doc_no = code.fields.get("document_number") or code.fields.get("passport_number")
            ocr_doc_no = f.get("document_number") or f.get("visa_number") or f.get("permit_number")
            eng.add("printed_vs_machine_readable", "document_number", "printed text",
                    ocr_doc_no.value if ocr_doc_no else None, src, qr_doc_no, i, bbox=region)
            for key in ("name", "date_of_birth", "date_of_expiry"):
                qv = code.fields.get(key)
                if key.startswith("date") and qv:
                    from app.services.docverify.fields import normalize_date
                    qv = normalize_date(qv) or qv
                fv = f.get(key)
                eng.add("printed_vs_machine_readable", key, "printed text", fv.value if fv else None, src, qv, i, bbox=region)
            if "passport_number" in code.fields and "passport_number" in f:
                eng.add("printed_vs_machine_readable", "passport_number", "printed text", f["passport_number"].value,
                        src, code.fields["passport_number"], i, bbox=region)
        # OCR <-> registry
        reg = registry_results.get(i) or {}
        rec = reg.get("record")
        if rec:
            ident = _identity(doc)
            for key, rkey in (("name", "name"), ("date_of_birth", "dob"), ("date_of_expiry", "expiry_date"),
                              ("date_of_expiry", "valid_until"), ("nationality", "nationality")):
                if rkey in rec and key in ident:
                    eng.add("document_vs_registry", key, ident[key][1], ident[key][0], "mock registry",
                            rec[rkey], i, bbox=ident[key][2])
        # Expiry <-> verification date
        ident = _identity(doc)
        if "date_of_expiry" in ident:
            exp = ident["date_of_expiry"][0]
            try:
                expired = date.fromisoformat(exp) < on
            except ValueError:
                expired = None
            if expired is not None:
                eng.add_fact("expiry_vs_verification_date", "date_of_expiry",
                             "INCONSISTENCY_DETECTED" if expired else "CONSISTENT",
                             f"document {'expired on' if expired else 'valid until'} {exp} (checked on {on.isoformat()})",
                             i, strong=expired, bbox=ident["date_of_expiry"][2],
                             values={"value_a": exp, "value_b": on.isoformat()})

    # Cross-document
    passports = [d for d in documents if d.document_type.document_type in PASSPORT_TYPES]
    travel = [d for d in documents if d.document_type.document_type in VISA_TYPES
              or d.document_type.document_type == DocumentType.BHUTAN_ENTRY_PERMIT]
    ids = [d for d in documents if d.document_type.document_type not in (DocumentType.IMMIGRATION_STAMP,
                                                                        DocumentType.DOCUMENT_TYPE_UNCERTAIN)]
    for p in passports:
        pid = _identity(p)
        for t in travel:
            tf = t.fields
            label = t.document_type.document_type.value.lower()
            if "passport_number" in tf and "document_number" in pid:
                eng.add("passport_vs_" + ("permit" if "PERMIT" in label.upper() else "visa"), "passport_number",
                        "passport", pid["document_number"][0], label, tf["passport_number"].value, t.document_index,
                        bbox=tf["passport_number"].bbox)
    for a_idx in range(len(ids)):
        for b_idx in range(a_idx + 1, len(ids)):
            a, b = ids[a_idx], ids[b_idx]
            ia, ib = _identity(a), _identity(b)
            la, lb = a.document_type.document_type.value.lower(), b.document_type.document_type.value.lower()
            for key in ("name", "date_of_birth", "nationality"):
                if key in ia and key in ib:
                    eng.add("document_vs_document", key, la, ia[key][0], lb, ib[key][0], b.document_index,
                            bbox=ib[key][2])

    # Stamps <-> visa validity / checkpoint reference
    visas = [d for d in documents if d.document_type.document_type in VISA_TYPES]
    for doc in documents:
        for s in doc.stamps:
            if s.date:
                if s.date > on.isoformat():
                    eng.add_fact("stamp_vs_verification_date", "stamp_date", "INCONSISTENCY_DETECTED",
                                 f"stamp is dated {s.date}, after today's date {on.isoformat()}", doc.document_index,
                                 bbox=s.bbox, values={"value_a": s.date, "value_b": on.isoformat()})
                for v in visas:
                    vf, vt = v.fields.get("valid_from"), v.fields.get("date_of_expiry")
                    if s.direction == "ENTRY" and vf and vt:
                        inside = vf.value <= s.date <= vt.value
                        eng.add_fact("stamp_vs_visa_validity", "stamp_date",
                                     "CONSISTENT" if inside else "INCONSISTENCY_DETECTED",
                                     f"entry stamp date {s.date} is {'within' if inside else 'outside'} the visa's "
                                     f"validity {vf.value} to {vt.value}", doc.document_index, strong=not inside,
                                     bbox=s.bbox, values={"value_a": s.date, "value_b": f"{vf.value}..{vt.value}"})
            country_note = next((n for n in s.notes if "belongs to" in n), None)
            if country_note:
                eng.add_fact("stamp_vs_checkpoint_reference", "checkpoint", "INCONSISTENCY_DETECTED",
                             country_note, doc.document_index, strong=True, bbox=s.bbox)
            elif s.checkpoint_id:
                eng.add_fact("stamp_vs_checkpoint_reference", "checkpoint", "CONSISTENT",
                             f"stamp checkpoint {s.checkpoint} found in the official checkpoint reference "
                             f"({s.checkpoint_type})", doc.document_index, bbox=s.bbox)
    return eng
