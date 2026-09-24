"""Electronic documents: e-Visa / ETA, e-Aadhaar, DigiLocker / mParivahan
driving licences and online permits.

These are issued as PDFs or app screens and are presented printed or on a
phone. Their authenticity is established by the issuing service (an online
status check or the service's own signed QR), not by print security
features. The server recognises the electronic form from its printed markers
and tells the officer which official service confirms it. It never claims to
have queried that service — no government system is connected in this build.
"""
from __future__ import annotations

import re
from typing import Any

from app.services.docverify.types import DocumentType

# (form, markers, label, official check). Markers are matched on upper-cased
# OCR text; `needs` restricts a form to the document types it can belong to.
_FORMS: list[dict[str, Any]] = [
    {
        "form": "E_VISA",
        "markers": r"E-?\s?VISA|ELECTRONIC\s*TRAVEL\s*AUTHORI[SZ]ATION|\bETA\s*(NUMBER|NO)\b|INDIANVISAONLINE",
        "needs": {DocumentType.INDIAN_VISA, DocumentType.DOCUMENT_TYPE_UNCERTAIN, DocumentType.OTHER_TRAVEL_DOCUMENT},
        "label": "Indian e-Visa / Electronic Travel Authorisation",
        "official_check": "Confirm the ETA status on the official Indian e-Visa portal (indianvisaonline.gov.in) "
                          "using the application ID and passport number; the printout alone cannot be verified here.",
    },
    {
        "form": "E_AADHAAR",
        "markers": r"E-?\s?AADHAAR|ELECTRONICALLY\s*GENERATED|DOWNLOAD\s*DATE",
        "needs": {DocumentType.AADHAAR},
        "label": "e-Aadhaar (downloaded copy)",
        "official_check": "Scan its secure QR with UIDAI's official Aadhaar QR scanner or the mAadhaar app "
                          "(uidai.gov.in); the printed copy alone cannot be verified here.",
    },
    {
        "form": "E_DRIVING_LICENCE",
        "markers": r"DIGI\s?LOCKER|M-?\s?PARIVAHAN|PARIVAHAN",
        "needs": {DocumentType.DRIVING_LICENCE, DocumentType.DOCUMENT_TYPE_UNCERTAIN},
        "label": "Digital driving licence (DigiLocker / mParivahan)",
        "official_check": "Confirm the licence on the official Parivahan service (parivahan.gov.in) or by scanning "
                          "its QR in the mParivahan app.",
    },
    {
        "form": "E_PERMIT",
        "markers": r"ONLINE\s*(ENTRY\s*)?PERMIT|E-?\s?PERMIT|ELECTRONIC\s*PERMIT|PERMIT\s*APPLICATION\s*(ID|NO)",
        "needs": {DocumentType.BHUTAN_ENTRY_PERMIT, DocumentType.OTHER_TRAVEL_DOCUMENT, DocumentType.DOCUMENT_TYPE_UNCERTAIN},
        "label": "Online / electronic permit",
        "official_check": "Confirm the permit number with the issuing authority's online permit service.",
    },
]


def detect(text: str, document_type: DocumentType) -> dict[str, Any] | None:
    """The electronic form of this document, or None for a physical document."""
    upper = text.upper()
    for f in _FORMS:
        if document_type not in f["needs"]:
            continue
        found = sorted({m.group(0).strip() for m in re.finditer(f["markers"], upper)})
        if found:
            return {"form": f["form"], "label": f["label"], "official_check": f["official_check"],
                    "markers": found[:4]}
    return None
