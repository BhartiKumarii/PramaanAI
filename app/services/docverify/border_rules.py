"""India–Nepal and India–Bhutan border-rule evaluation (separate, versioned,
date-aware configurations in reference_data/rules/).

Answers "what evidence does THIS traveller need on THIS route on THIS date",
so that e.g. an Indian or Nepali citizen without a visa or stamp is never
flagged (treaty-based open border), while a third-country national without
the required visa is routed to officer review. Missing evidence is always
REVIEW_REQUIRED — never FAIL, never "fraud".
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.services.docverify import reference
from app.services.docverify.consistency import norm_nationality
from app.services.docverify.fields import age_on
from app.services.docverify.types import CheckResult, CheckStatus, DocumentAnalysis, DocumentType, VISA_TYPES

_ROUTE_NATIONALS = {"INDIA_NEPAL": {"IND": "INDIAN", "NPL": "NEPALI"},
                    "INDIA_BHUTAN": {"IND": "INDIAN", "BTN": "BHUTANESE"}}
_DOC_NATIONALITY = {DocumentType.INDIAN_PASSPORT: "IND", DocumentType.AADHAAR: "IND", DocumentType.VOTER_ID: "IND"}


def infer_nationality(documents: list[DocumentAnalysis], declared: str | None) -> tuple[str | None, str]:
    for d in documents:
        if d.mrz and d.mrz.get("nationality") and d.mrz.get("all_checks_valid"):
            return norm_nationality(d.mrz["nationality"]), f"MRZ of document {d.document_index + 1}"
    for d in documents:
        if d.document_type.document_type in _DOC_NATIONALITY:
            return _DOC_NATIONALITY[d.document_type.document_type], f"{d.document_type.document_type.value} presented"
        if "nationality" in d.fields:
            return norm_nationality(d.fields["nationality"].value), f"printed nationality on document {d.document_index + 1}"
    if declared:
        return norm_nationality(declared), "declared by officer"
    return None, "not established"


def evaluate(route: str | None, documents: list[DocumentAnalysis], *, on: date, direction: str | None,
             declared_nationality: str | None) -> tuple[list[CheckResult], dict[str, Any] | None]:
    if not route:
        return [CheckResult(name="border_rules", status=CheckStatus.NOT_APPLICABLE, blocking=False,
                            summary="No border route selected — crossing rules were not evaluated")], None
    route = route.upper()
    version = reference.rule_version_for(route, on)
    if version is None:
        return [CheckResult(name="border_rules", status=CheckStatus.REFERENCE_NOT_AVAILABLE, blocking=False,
                            summary=f"No {route} rule version is configured for {on.isoformat()}")], None

    icao, basis = infer_nationality(documents, declared_nationality)
    category = _ROUTE_NATIONALS[route].get(icao or "", "THIRD_COUNTRY" if icao else None)
    info: dict[str, Any] = {"route": route, "rule_version": version["version"], "travel_date": on.isoformat(),
                            "nationality": icao, "nationality_basis": basis, "category": category,
                            "direction": direction, "sources": version["sources"]}
    checks: list[CheckResult] = []
    if category is None:
        checks.append(CheckResult(name="border_rules", status=CheckStatus.NOT_VERIFIED, blocking=False,
                                  summary="Traveller nationality could not be established, so crossing rules were not applied",
                                  details=info))
        return checks, info
    rules = version["nationality_rules"][category]
    info["basis"] = rules["basis"]
    types = {d.document_type.document_type for d in documents}
    type_names = {t.value for t in types}

    # Accepted identity documents
    accepted = set(rules.get("accepted_identity_documents", []))
    not_accepted = set(rules.get("not_accepted_as_travel_document", []))
    ages = [a for a in (age_on((d.fields.get("date_of_birth").value if d.fields.get("date_of_birth") else
                                (d.mrz or {}).get("date_of_birth_iso")), on) for d in documents) if a is not None]
    age = ages[0] if ages else None
    exempt = next((e for e in rules.get("age_exemptions", []) if age is not None
                   and (e["min_age"] is None or age >= e["min_age"]) and (e["max_age"] is None or age < e["max_age"])), None)
    presented_ok = type_names & accepted
    if presented_ok:
        checks.append(CheckResult(name="accepted_travel_document", status=CheckStatus.PASS, blocking=False,
                                  summary=f"{', '.join(sorted(presented_ok))} is an accepted document for {category.lower()} "
                                          f"travellers on this route", details=info))
    elif exempt:
        checks.append(CheckResult(name="accepted_travel_document", status=CheckStatus.PASS, blocking=False,
                                  summary=f"Age {age}: {exempt['note']}", details=info))
    else:
        bad = type_names & not_accepted
        checks.append(CheckResult(
            name="accepted_travel_document", status=CheckStatus.REVIEW_REQUIRED, blocking=False,
            summary=(f"{', '.join(sorted(bad))} is not listed as an accepted travel document for this route — "
                     "confirm under current procedure" if bad else
                     "None of the presented documents is on this route's accepted-document list — confirm under current procedure"),
            details=info))

    # Visa requirement
    if rules.get("visa_required"):
        needed = rules.get("required_visa", {})
        wanted = set(needed.get(direction or "", [])) or {v for vs in needed.values() for v in vs}
        have = type_names & wanted
        checks.append(CheckResult(
            name="visa_requirement", status=CheckStatus.PASS if have else CheckStatus.REVIEW_REQUIRED,
            summary=(f"Required visa present ({', '.join(sorted(have))})" if have else
                     f"{category.replace('_', ' ').title()} traveller: expected {' or '.join(sorted(wanted))} was not "
                     "among the documents presented — officer to confirm"),
            details={**info, "required": sorted(wanted)}))
    else:
        checks.append(CheckResult(name="visa_requirement", status=CheckStatus.NOT_APPLICABLE, blocking=False,
                                  summary=f"No visa is required for {category.lower()} travellers on this route "
                                          "(absence of a visa is not a finding)", details=info))

    # Stamp expectation
    stamps = [s for d in documents for s in d.stamps]
    stamp_expected = rules.get("immigration_stamp_expected", rules.get("physical_stamp_expected", False))
    if stamp_expected and rules.get("missing_stamp_is_finding"):
        checks.append(CheckResult(
            name="stamp_requirement", status=CheckStatus.PASS if stamps else CheckStatus.REVIEW_REQUIRED,
            summary=("Immigration stamp evidence present" if stamps else
                     "No immigration stamp found for a traveller for whom one is expected — officer to confirm entry/exit record"),
            details=info))
        if category == "THIRD_COUNTRY" and route == "INDIA_NEPAL":
            for s in stamps:
                cp = reference.get_checkpoint(s.checkpoint_id) if s.checkpoint_id else None
                if cp and cp["country"] == "NEPAL" and cp.get("foreigner_immigration_point") is False:
                    checks.append(CheckResult(
                        name="designated_crossing", status=CheckStatus.REVIEW_REQUIRED,
                        summary=f"Stamp names {cp['checkpoint_name']}, which is not listed as a designated entry/exit "
                                "point for foreigners — officer to confirm", details=info))
    else:
        note = rules.get("physical_stamp_note") or "a physical stamp is not expected for this traveller category"
        checks.append(CheckResult(name="stamp_requirement", status=CheckStatus.NOT_APPLICABLE, blocking=False,
                                  summary=f"Stamp not required: {note}", details=info))

    if rules.get("entry_permit_required"):
        has_permit = DocumentType.BHUTAN_ENTRY_PERMIT in types
        checks.append(CheckResult(
            name="entry_permit", status=CheckStatus.PASS if has_permit else CheckStatus.NOT_VERIFIED, blocking=False,
            summary=("Bhutan entry permit presented" if has_permit else
                     "Bhutan entry permit not presented — it may be issued at the port of entry or online (e-permit); "
                     "absence is not evidence of irregularity"), details=info))
    info["age"] = age
    info["presented"] = sorted(type_names)
    return checks, info
