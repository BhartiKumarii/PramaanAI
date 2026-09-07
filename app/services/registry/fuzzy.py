"""Real fuzzy name matching via difflib — no external dependency. Takes
the better of a raw character-similarity ratio and a token-sorted ratio,
since border documents commonly vary surname-first vs given-name-first
ordering, which a raw ratio alone would badly under-score.
"""
import difflib

DEFAULT_FUZZY_THRESHOLD = 0.82


def _normalize(name: str) -> str:
    return " ".join(name.strip().upper().split())


def name_similarity(a: str, b: str) -> float:
    norm_a, norm_b = _normalize(a), _normalize(b)
    raw_ratio = difflib.SequenceMatcher(None, norm_a, norm_b).ratio()
    sorted_a = " ".join(sorted(norm_a.split()))
    sorted_b = " ".join(sorted(norm_b.split()))
    sorted_ratio = difflib.SequenceMatcher(None, sorted_a, sorted_b).ratio()
    return max(raw_ratio, sorted_ratio)
