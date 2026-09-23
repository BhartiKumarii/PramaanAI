"""Loader for the versioned reference dataset under reference_data/.

All lookups are date-aware: a checkpoint, template version or border rule
only applies if the travel/check date falls inside its validity period.
Unknown validity bounds (null) are treated as open — never guessed.
"""
from __future__ import annotations

import json
import re
from datetime import date
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import get_settings

_REPO_ROOT = Path(__file__).resolve().parents[3]


def reference_root() -> Path:
    configured = Path(get_settings().pramaan_reference_data_dir)
    return configured if configured.is_absolute() else _REPO_ROOT / configured


def _load(rel: str) -> dict[str, Any]:
    path = reference_root() / rel
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def in_period(start: str | None, end: str | None, on: date) -> bool:
    s, e = _parse_date(start), _parse_date(end)
    return (s is None or on >= s) and (e is None or on <= e)


# ---------------------------------------------------------------- checkpoints

_CHECKPOINT_FILES = (
    "nepal/checkpoints/checkpoints.json",
    "india/checkpoints/india_nepal_border.json",
    "bhutan/checkpoints/checkpoints.json",
    "india/checkpoints/india_bhutan_border.json",
)


@lru_cache
def all_checkpoints() -> tuple[dict[str, Any], ...]:
    records: list[dict[str, Any]] = []
    for rel in _CHECKPOINT_FILES:
        data = _load(rel)
        for record in data["checkpoints"]:
            records.append({**record, "border": data["border"]})
    return tuple(records)


def get_checkpoint(checkpoint_id: str) -> dict[str, Any] | None:
    return next((c for c in all_checkpoints() if c["checkpoint_id"] == checkpoint_id), None)


def _norm(text: str) -> str:
    return re.sub(r"[^A-Z]", "", text.upper())


def match_checkpoint(text: str, country: str | None = None, min_similarity: float = 0.88) -> dict[str, Any] | None:
    """Find the checkpoint whose name/alias appears in OCR text. Exact
    substring matches win; otherwise a sliding-window fuzzy match tolerant
    to one or two OCR character errors. Returns the record plus how it
    matched, or None — never a forced guess."""
    haystack = _norm(text)
    if not haystack:
        return None
    best: tuple[float, dict[str, Any], str] | None = None
    for record in all_checkpoints():
        if country and record["country"] != country:
            continue
        for name in [record["checkpoint_name"], *record.get("aliases", [])]:
            needle = _norm(name)
            if len(needle) < 4:
                continue
            if needle in haystack:
                score = 1.0
            elif len(needle) < 8:
                continue  # short names must appear exactly — fuzzy matches on them are noise
            else:
                window = len(needle)
                score = max(
                    (SequenceMatcher(None, needle, haystack[i:i + window]).ratio()
                     for i in range(0, max(1, len(haystack) - window + 1))),
                    default=0.0,
                )
            if score >= min_similarity and (best is None or score > best[0] or
                                            (score == best[0] and len(needle) > len(_norm(best[2])))):
                best = (score, record, name)
    if best is None:
        return None
    return {"record": best[1], "similarity": round(best[0], 3), "matched_text": best[2]}


def list_checkpoints(country: str | None = None, border: str | None = None) -> list[dict[str, Any]]:
    return [c for c in all_checkpoints()
            if (country is None or c["country"] == country.upper())
            and (border is None or c["border"] == border.upper())]


# ---------------------------------------------------------------- templates

_TEMPLATE_FILES = {
    ("INDIAN_PASSPORT", "INDIA"): "india/passport/templates.json",
    ("FOREIGN_PASSPORT", "NEPAL"): "nepal/passport/templates.json",
    ("FOREIGN_PASSPORT", "BHUTAN"): "bhutan/passport/templates.json",
    ("INDIAN_VISA", "INDIA"): "india/visa/templates.json",
    ("NEPAL_VISA", "NEPAL"): "nepal/visa/templates.json",
    ("BHUTAN_VISA", "BHUTAN"): "bhutan/visa/templates.json",
    ("BHUTAN_ENTRY_PERMIT", "BHUTAN"): "bhutan/permits/templates.json",
    ("DRIVING_LICENCE", "INDIA"): "india/driving_licence/templates.json",
    ("AADHAAR", "INDIA"): "india/aadhaar/templates.json",
}


@lru_cache
def document_reference(document_type: str, country: str | None) -> dict[str, Any] | None:
    rel = _TEMPLATE_FILES.get((document_type, (country or "").upper()))
    if rel is None:
        # Foreign passports from outside the region still get the generic ICAO layout.
        if document_type == "FOREIGN_PASSPORT":
            rel = "nepal/passport/templates.json"
        else:
            return None
    return _load(rel)


def template_versions(document_type: str, country: str | None, on: date) -> list[dict[str, Any]]:
    ref = document_reference(document_type, country)
    if not ref:
        return []
    # A document issued under an older version is still in circulation, so
    # every version is a candidate; versions valid on `on` are listed first.
    versions = list(ref["versions"])
    versions.sort(key=lambda v: not in_period(v["validity_period"]["from"], v["validity_period"]["to"], on))
    return versions


@lru_cache
def stamp_references() -> tuple[dict[str, Any], ...]:
    return tuple(_load(rel) for rel in (
        "nepal/immigration_stamps/stamps.json",
        "bhutan/immigration/stamps.json",
        "india/checkpoints/stamps.json",
    ))


# ---------------------------------------------------------------- border rules

_RULE_FILES = {"INDIA_NEPAL": "rules/india_nepal.json", "INDIA_BHUTAN": "rules/india_bhutan.json"}


@lru_cache
def border_rules(route: str) -> dict[str, Any]:
    return _load(_RULE_FILES[route.upper()])


def rule_version_for(route: str, on: date) -> dict[str, Any] | None:
    for version in border_rules(route)["versions"]:
        if in_period(version.get("effective_from"), version.get("effective_to"), on):
            return version
    return None


# ---------------------------------------------------------------- mock registries

@lru_cache
def mock_registry(name: str) -> dict[str, Any]:
    return _load(f"mock_registries/{name}.json")


@lru_cache
def stamp_visual_references() -> dict[str, dict[str, Any]]:
    """checkpoint_id:direction -> visual reference. Only SYNTHETIC test
    references exist in this build (see the file's data_classification)."""
    path = reference_root() / "synthetic_references/stamp_visual_references.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {f"{r['checkpoint_id']}:{r['direction']}": {**r, "data_classification": data["data_classification"]}
            for r in data["references"]}


@lru_cache
def nationality_codes() -> frozenset[str]:
    data = _load("icao/nationality_codes.json")
    return frozenset(data["iso_alpha3"]) | frozenset(data["icao_special"])
