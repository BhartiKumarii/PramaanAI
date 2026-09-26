"""Document-type identification.

Combines three independent kinds of evidence, each named in `basis`:
  1. The MRZ document code + issuing state (strongest, machine-readable).
  2. Printed title/keyword text from OCR.
  3. Detected regions (MRZ / QR / photograph / stamps).
Returns DOCUMENT_TYPE_UNCERTAIN instead of forcing a label when the evidence
is weak or two types are close.
"""
from __future__ import annotations

import re

from app.services.docverify.types import DocumentType, DocumentTypeResult, Region, RegionLabel

UNCERTAIN_THRESHOLD = 0.55

# (pattern, family, weight). Families are resolved to a DocumentType together
# with the country below.
_KEYWORDS: list[tuple[str, str, float]] = [
    # "passport page" = visa/stamp page header; "Passport No"/"Number" is a
    # field on visas and permits too (a real passport also has its title/MRZ)
    (r"\bPASSPORT\b(?!\s*(?:PAGE|NO\b|NO\.|NO:|NUMBER))|पासपोर्ट|राहदानी", "passport", 8),
    (r"\bP\s?<\s?[A-Z]{3}", "passport", 12),
    (r"DRIV\w*\s*LICEN[CS]E|DRIVING\s*LICENSE|LICEN[CS]E\s*NO|\bDL\s*NO", "driving_licence", 14),
    (r"MOTOR\s*DRIVING|MOTOR\s*VEHICLE|\bCOV\b|\bLMV\b|\bMCWG\b|LICEN[CS]ING\s*AUTHORITY|\bRTO\b", "driving_licence", 5),
    (r"INTERNATIONAL\s*DRIVING\s*PERMIT|INTERNATIONAL\s*MOTOR\s*TRAFFIC|CONVENTION\s*ON\s*ROAD\s*TRAFFIC", "driving_licence", 16),
    # Bhutan (RSTA) licences carry an offences / endorsements table and blood group
    (r"OFFENCES|ENDORSEMENTS?|ROAD\s*SAFETY|\bRSTA\b|BLOOD\s*GROUP", "driving_licence", 6),
    (r"AADHAAR|\bUIDAI\b|UNIQUE\s*IDENTIFICATION|आधार", "aadhaar", 16),
    (r"TOURIST\s*VISA|ENTRY\s*VISA|VISA\s*NO|VISA\s*TYPE|VISA\s*PLAN|TYPE\s*OF\s*VISA|VISA\s*ON\s*ARRIVAL", "visa", 14),
    (r"\bVISA\b", "visa", 7),
    (r"E-?VISA|ELECTRONIC\s*TRAVEL\s*AUTHORI[SZ]ATION|\bETA\b", "evisa", 12),
    (r"ENTRY\s*PERMIT|PERMIT\s*NO|PURPOSE\s*OF\s*VISIT|TRAVEL\s*PERMIT|अनुमति", "permit", 13),
    (r"NATIONAL\s*IDENTITY\s*CARD|CITIZENSHIP\s*(CARD|CERTIFICATE|ID)|IDENTITY\s*CARD|नागरिकता|\bCID\b", "identity", 11),
    (r"ELECTION\s*COMMISSION|ELECTOR|VOTER", "voter_id", 14),
    (r"IMMIGRATION|ARRIVED|DEPARTED|\bARRIVAL\b|\bDEPARTURE\b", "stamp", 3),
]

_COUNTRY_CUES: list[tuple[str, str, float]] = [
    (r"REPUBLIC\s*OF\s*INDIA|GOVERNMENT\s*OF\s*INDIA|UNION\s*OF\s*INDIA|INDIAN\s*UNION|भारत", "INDIA", 6),
    (r"\bINDIA\b|\bIND\b|\bRTO\b|MAHARASHTRA|GUJARAT|TELANGANA|TAMIL\s*NADU|UTTAR\s*PRADESH|BIHAR|WEST\s*BENGAL|CHHATTISGARH|KERALA|KARNATAKA", "INDIA", 2),
    (r"GOVERNMENT\s*OF\s*NEPAL|NEPAL\s*GOVERNMENT|नेपाल", "NEPAL", 6),
    (r"\bNEPAL\b|\bNPL\b|KATHMANDU|TRIBHUVAN", "NEPAL", 2),
    (r"KINGDOM\s*OF\s*BHUTAN|ROYAL\s*GOVERNMENT\s*OF\s*BHUTAN|TOURISM\s*COUNCIL\s*OF\s*BHUTAN", "BHUTAN", 6),
    (r"\bBHUTAN\b|\bBTN\b|THIMPHU|PHUENTSHOLING|DRUK", "BHUTAN", 2),
]

_ICAO_COUNTRY = {"IND": "INDIA", "NPL": "NEPAL", "BTN": "BHUTAN"}


def _country_scores(text: str) -> dict[str, float]:
    scores: dict[str, float] = {}
    for pattern, country, weight in _COUNTRY_CUES:
        hits = len(re.findall(pattern, text))
        if hits:
            scores[country] = scores.get(country, 0) + weight * min(hits, 3)
    return scores


def _resolve(family: str, country: str | None) -> tuple[DocumentType, str | None]:
    if family == "passport":
        if country == "INDIA":
            return DocumentType.INDIAN_PASSPORT, "INDIA"
        return (DocumentType.FOREIGN_PASSPORT, country) if country else (DocumentType.DOCUMENT_TYPE_UNCERTAIN, None)
    if family in ("visa", "evisa"):
        if family == "evisa" and country in (None, "INDIA"):
            return DocumentType.INDIAN_VISA, "INDIA"
        mapping = {"INDIA": DocumentType.INDIAN_VISA, "NEPAL": DocumentType.NEPAL_VISA, "BHUTAN": DocumentType.BHUTAN_VISA}
        return (mapping[country], country) if country in mapping else (DocumentType.DOCUMENT_TYPE_UNCERTAIN, None)
    if family == "permit":
        return (DocumentType.BHUTAN_ENTRY_PERMIT, "BHUTAN") if country == "BHUTAN" else (DocumentType.OTHER_TRAVEL_DOCUMENT, country)
    if family == "driving_licence":
        return DocumentType.DRIVING_LICENCE, country
    if family == "aadhaar":
        return DocumentType.AADHAAR, "INDIA"
    if family == "voter_id":
        return DocumentType.VOTER_ID, "INDIA"
    if family == "identity":
        return DocumentType.IDENTITY_DOCUMENT, country
    if family == "stamp":
        return DocumentType.IMMIGRATION_STAMP, country
    return DocumentType.DOCUMENT_TYPE_UNCERTAIN, None


def classify(text: str, mrz: dict | None, regions: list[Region], identified_stamps: int = 0) -> DocumentTypeResult:
    upper = text.upper()
    basis: list[str] = []
    family_scores: dict[str, float] = {}

    for pattern, family, weight in _KEYWORDS:
        if re.search(pattern, upper if family != "aadhaar" else text, re.IGNORECASE if family == "aadhaar" else 0):
            family_scores[family] = family_scores.get(family, 0) + weight
            basis.append(f"text matches {family.replace('_', ' ')} keyword /{pattern[:40]}/")
    if "evisa" in family_scores:
        family_scores["visa"] = family_scores.get("visa", 0) + family_scores.pop("evisa")

    countries = _country_scores(upper)
    mrz_country = None
    if mrz:
        code = (mrz.get("document_code") or "")[:1]
        mrz_country = _ICAO_COUNTRY.get(mrz.get("issuing_country", ""), None)
        fam = {"P": "passport", "V": "visa", "I": "identity", "A": "identity", "C": "identity"}.get(code)
        if fam:
            family_scores[fam] = family_scores.get(fam, 0) + 25
            basis.append(f"MRZ document code {mrz.get('document_code')!r} ({mrz.get('format')}) issued by {mrz.get('issuing_country')}")
        printed_strong = max(countries.values(), default=0) >= 6  # e.g. "REPUBLIC OF INDIA" printed
        if mrz_country:
            countries[mrz_country] = countries.get(mrz_country, 0) + 20
        elif mrz.get("issuing_country") and not printed_strong:
            countries[mrz["issuing_country"]] = countries.get(mrz["issuing_country"], 0) + 20
        elif mrz.get("issuing_country"):
            # An unfamiliar MRZ country against a clearly printed one is
            # usually an OCR misread of the MRZ ("NDP" for IND): weigh it less.
            countries[mrz["issuing_country"]] = countries.get(mrz["issuing_country"], 0) + 4

    labels = {r.label for r in regions}
    if RegionLabel.MRZ in labels:
        for fam in ("passport", "visa"):
            if fam in family_scores:
                family_scores[fam] += 3
    if identified_stamps:
        family_scores["stamp"] = family_scores.get("stamp", 0) + 10 * identified_stamps
        basis.append(f"{identified_stamps} stamp region(s) detected and identified from their text")

    evisa = bool(re.search(r"E-?VISA|ELECTRONIC\s*TRAVEL\s*AUTHORI", upper))
    ranked = sorted(family_scores.items(), key=lambda kv: -kv[1])
    if not ranked:
        return DocumentTypeResult(document_type=DocumentType.DOCUMENT_TYPE_UNCERTAIN, country=None, confidence=0.0,
                                  basis=["no document keywords, MRZ or identified stamps found"])

    # A passport page carrying stamps is still a passport page; a page with
    # only stamps (no title text) is a stamp page.
    top_family, top_score = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 0.0
    if top_family == "stamp" and any(f in family_scores for f in ("visa", "permit")) and not identified_stamps:
        top_family, top_score = ranked[1]

    country = max(countries.items(), key=lambda kv: kv[1])[0] if countries else None
    if top_family == "passport" and mrz_country is None and mrz and mrz.get("issuing_country") and \
            countries.get(country or "", 0) < 6:
        country = mrz["issuing_country"]
    doc_type, resolved_country = _resolve("evisa" if top_family == "visa" and evisa else top_family, country)

    margin = (top_score - second) / top_score if top_score else 0.0
    strength = min(1.0, top_score / 20.0)
    confidence = round(min(0.99, 0.5 * strength + 0.5 * margin + (0.1 if mrz else 0.0)), 3)
    candidates = [{"family": f, "score": round(s, 1)} for f, s in ranked[:4]]
    if confidence < UNCERTAIN_THRESHOLD or doc_type == DocumentType.DOCUMENT_TYPE_UNCERTAIN:
        basis.append(f"top candidate {top_family!r} (confidence {confidence:.2f}) is below the "
                     f"{UNCERTAIN_THRESHOLD:.2f} threshold or its issuing country could not be established")
        return DocumentTypeResult(document_type=DocumentType.DOCUMENT_TYPE_UNCERTAIN, country=resolved_country,
                                  confidence=confidence, candidates=candidates, basis=basis)
    return DocumentTypeResult(document_type=doc_type, country=resolved_country, confidence=confidence,
                              candidates=candidates, basis=basis)
