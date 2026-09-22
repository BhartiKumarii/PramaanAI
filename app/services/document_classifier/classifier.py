"""Document type classifier — OCR text keywords first, visual features as fallback.

The previous version relied only on visual feature profiles (color histograms,
aspect ratios) which are too unreliable for real documents. OCR text is far more
accurate: a passport literally says "PASSPORT", a driving licence says "DRIVING
LICENCE", etc. Visual features are used only when OCR text is ambiguous.
"""
import io
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from app.services.document_classifier.feature_extractor import extract_features_from_bytes

SCALAR_KEYS = [
    "aspect_ratio",
    "text_density",
    "face_present",
    "face_count",
    "face_area_ratio",
    "h_line_count",
    "blue_ratio",
    "green_ratio",
    "red_ratio",
    "white_ratio",
    "edge_uniformity",
]
HISTOGRAM_KEYS = ["hist_h", "hist_s", "hist_v"]

REFERENCE_PATH = Path(__file__).parent / "reference_profiles.json"

ID_DOC_THRESHOLD = 0.72

FEATURE_WEIGHTS = {
    "aspect_ratio": 3.0,
    "text_density": 2.0,
    "face_present": 4.0,
    "face_area_ratio": 2.0,
    "h_line_count": 1.0,
    "blue_ratio": 1.5,
    "green_ratio": 1.0,
    "red_ratio": 1.0,
    "white_ratio": 1.5,
    "edge_uniformity": 1.5,
    "face_count": 1.0,
    "hist_h": 2.0,
    "hist_s": 1.5,
    "hist_v": 1.0,
}

DOCTYPE_MAP = {
    "National_ID": "national_id",
    "Passport": "passport",
    "Driving_License": "driving_license",
    "Visa": "visa",
    "Permit": "permit",
}

_KEYWORD_RULES: list[tuple[str, str, list[str]]] = [
    # (doc_type, country, keywords) — first match wins, most specific first
    ("passport", "India", ["republic of india", "indian passport", "passport", r"type\s*p"]),
    ("passport", "Nepal", ["nepal", "nepali passport", r"government\s*of\s*nepal"]),
    ("passport", "Bhutan", ["bhutan", "bhutanese passport", r"kingdom\s*of\s*bhutan"]),
    ("national_id", "India", ["aadhaar", "unique identification", "uidai", r"xxxx\s*\d{4}", r"\d{4}\s*\d{4}\s*\d{4}"]),
    ("national_id", "India", ["election commission", "voter", "electors photo", "epic"]),
    ("national_id", "India", ["permanent account number", "income tax", r"pan\s*card", r"[A-Z]{5}\d{4}[A-Z]"]),
    ("national_id", "Nepal", ["nepal", r"national\s*id", r"citizenship", r"nagarikta"]),
    ("national_id", "Bhutan", ["bhutan", r"citizen\s*id", r"cid\s*no"]),
    ("driving_license", "India", [r"driving\s*licen[cs]e", r"motor\s*vehicle", "transport", r"dl\s*no", r"licen[cs]e\s*no"]),
    ("driving_license", "Nepal", ["nepal", r"driving\s*licen[cs]e", r"sawari\s*chalak"]),
    ("driving_license", "Bhutan", ["bhutan", r"driving\s*licen[cs]e"]),
    ("visa", "India", [r"visa", r"entry\s*permit", r"valid\s*for", r"no\.\s*of\s*entries"]),
    ("visa", "Nepal", ["nepal", r"visa", r"arrival"]),
    ("permit", "unknown", [r"permit", r"border\s*pass", r"entry\s*pass", r"inner\s*line"]),
]

_COUNTRY_KEYWORDS = {
    "India": [r"india", r"republic of india", r"bharat", r"government of india"],
    "Nepal": [r"nepal", r"government of nepal"],
    "Bhutan": [r"bhutan", r"kingdom of bhutan", r"druk"],
}


@dataclass
class DocumentClassification:
    is_identity_document: bool
    document_type: str  # "passport", "national_id", "driving_license", "visa", "permit", "unknown"
    country: str  # "India", "Nepal", "Bhutan", "unknown"
    confidence: float  # 0-1
    reason: str
    features: dict = field(default_factory=dict)


class DocumentClassifier:
    def __init__(self):
        self._profiles: dict = {}
        self._loaded = False
        self._load_profiles()

    def _load_profiles(self):
        if not REFERENCE_PATH.exists():
            print(f"[DocumentClassifier] WARNING: no reference profiles at {REFERENCE_PATH}")
            return
        data = json.loads(REFERENCE_PATH.read_text())
        self._profiles = data.get("profiles", {})
        self._loaded = bool(self._profiles)
        print(f"[DocumentClassifier] Loaded {len(self._profiles)} reference profiles")

    def _ocr_text(self, image_bytes: bytes) -> str:
        try:
            import pytesseract
            from PIL import Image, ImageOps
            image = Image.open(io.BytesIO(image_bytes))
            image = ImageOps.exif_transpose(image)
            gray = image.convert("L")
            gray = ImageOps.autocontrast(gray)
            return pytesseract.image_to_string(gray)
        except Exception:
            return ""

    def _classify_by_text(self, text: str) -> tuple[str, str, float, str] | None:
        """Return (doc_type, country, confidence, reason) from OCR keywords."""
        lower = text.lower()
        if len(lower.strip()) < 5:
            return None

        best_match: tuple[str, str, int, str] | None = None

        for doc_type, country, patterns in _KEYWORD_RULES:
            hits = 0
            matched = []
            for pat in patterns:
                if re.search(pat, lower):
                    hits += 1
                    matched.append(pat)
            if hits >= 2 or (hits == 1 and doc_type in ("passport", "visa", "permit")):
                if best_match is None or hits > best_match[2]:
                    best_match = (doc_type, country, hits, ", ".join(matched))

        if best_match is None:
            return None

        doc_type, country, hits, matched_str = best_match

        if country == "unknown":
            country = self._detect_country_from_text(lower)

        confidence = min(0.95, 0.70 + hits * 0.08)
        reason = f"OCR text matched {country} {doc_type} (keywords: {matched_str})"
        return doc_type, country, confidence, reason

    def _detect_country_from_text(self, lower_text: str) -> str:
        for country, patterns in _COUNTRY_KEYWORDS.items():
            for pat in patterns:
                if re.search(pat, lower_text):
                    return country
        return "unknown"

    def classify(self, image_bytes: bytes) -> DocumentClassification:
        features = extract_features_from_bytes(image_bytes)
        if features is None:
            return DocumentClassification(
                is_identity_document=False,
                document_type="unknown",
                country="unknown",
                confidence=0.0,
                reason="Could not decode image",
            )

        ocr_text = self._ocr_text(image_bytes)
        text_result = self._classify_by_text(ocr_text) if ocr_text else None

        if text_result is not None:
            doc_type, country, confidence, reason = text_result
            return DocumentClassification(
                is_identity_document=True,
                document_type=doc_type,
                country=country,
                confidence=confidence,
                reason=reason,
                features=features,
            )

        if not self._loaded:
            return DocumentClassification(
                is_identity_document=False,
                document_type="unknown",
                country="unknown",
                confidence=0.0,
                reason="No reference profiles loaded and OCR text inconclusive",
                features=features,
            )

        scores: list[tuple[str, float]] = []
        for profile_key, profile_data in self._profiles.items():
            score = self._compute_similarity(features, profile_data["features"])
            scores.append((profile_key, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        best_key, best_score = scores[0]

        parts = best_key.split("_", 1)
        country = parts[0] if len(parts) >= 2 else "unknown"
        raw_doc_type = parts[1] if len(parts) >= 2 else best_key
        doc_type = DOCTYPE_MAP.get(raw_doc_type, raw_doc_type.lower())

        is_id = best_score >= ID_DOC_THRESHOLD

        if is_id:
            structural_issues = self._structural_check(features, doc_type)
            if structural_issues:
                is_id = False
                reason = "Document rejected — " + "; ".join(structural_issues)
            else:
                reason = f"Visual profile matched {country} {doc_type} (confidence: {best_score:.2f})"
        else:
            reason = self._build_rejection_reason(features, best_score)

        if len(scores) > 1:
            runner_key, runner_score = scores[1]
            features["_runner_up"] = f"{runner_key}={runner_score:.3f}"

        return DocumentClassification(
            is_identity_document=is_id,
            document_type=doc_type if is_id else "unknown",
            country=country if is_id else "unknown",
            confidence=best_score,
            reason=reason,
            features=features,
        )

    def is_identity_document(self, image_bytes: bytes) -> tuple[bool, str, float]:
        result = self.classify(image_bytes)
        return result.is_identity_document, result.document_type, result.confidence

    def _compute_similarity(self, features: dict, profile_features: dict) -> float:
        """Compute weighted similarity between input features and a reference profile."""
        total_weight = 0.0
        weighted_score = 0.0

        # Scalar features: Gaussian similarity
        for key in SCALAR_KEYS:
            if key not in profile_features:
                continue
            pf = profile_features[key]
            mean = pf["mean"]
            std = max(pf["std"], 0.01)  # avoid division by zero
            value = features.get(key, 0.0)
            weight = FEATURE_WEIGHTS.get(key, 1.0)

            # Z-score → Gaussian similarity (1.0 = exact match, decays with distance)
            z = abs(value - mean) / std
            sim = np.exp(-0.5 * z * z)

            weighted_score += sim * weight
            total_weight += weight

        # Histogram features: Bhattacharyya coefficient
        for key in HISTOGRAM_KEYS:
            if key not in profile_features:
                continue
            pf = profile_features[key]
            ref_hist = np.array(pf["mean"], dtype=np.float32)
            inp_hist = np.array(features.get(key, [0.0] * 16), dtype=np.float32)
            weight = FEATURE_WEIGHTS.get(key, 1.0)

            # Bhattacharyya coefficient: sum(sqrt(p*q))
            ref_norm = ref_hist / (ref_hist.sum() + 1e-8)
            inp_norm = inp_hist / (inp_hist.sum() + 1e-8)
            bc = float(np.sum(np.sqrt(ref_norm * inp_norm)))

            weighted_score += bc * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0
        return weighted_score / total_weight

    def _structural_check(self, features: dict, doc_type: str) -> list[str]:
        """Check basic structural properties that every real ID document should have."""
        issues = []
        td = features.get("text_density", 0)
        ar = features.get("aspect_ratio", 0)

        # Most ID documents (except visas) have some text
        if td < 0.01:
            issues.append("no readable text structure detected")

        # Aspect ratio sanity — ID cards are roughly 1.5-1.6:1,
        # passports are 0.7-1.5:1. Anything outside 0.4-3.0 is suspicious.
        if ar < 0.4 or ar > 3.0:
            issues.append(f"aspect ratio {ar:.2f} is outside normal ID document range")

        # For document types that usually have faces (national_id, passport, driving_license)
        if doc_type in ("national_id", "passport", "driving_license"):
            if features.get("face_present", 0) < 0.5 and features.get("face_area_ratio", 0) < 0.01:
                # Only flag if the reference profile expects a face
                pass  # Some back sides don't have faces — let the profile score decide

        return issues

    def _build_rejection_reason(self, features: dict, best_score: float) -> str:
        """Build a human-readable reason for why the document was rejected."""
        issues = []

        if features.get("face_present", 0) < 0.5:
            issues.append("no face detected in document")

        td = features.get("text_density", 0)
        if td < 0.02:
            issues.append("very low text content")
        elif td > 0.25:
            issues.append("unusually high text density (not typical for ID documents)")

        ar = features.get("aspect_ratio", 0)
        if ar < 0.5 or ar > 2.5:
            issues.append(f"unusual aspect ratio ({ar:.2f}) for ID documents")

        if features.get("edge_uniformity", 0) < 0.2:
            issues.append("unstructured layout (no standard document grid)")

        if not issues:
            issues.append(f"no ID document profile matched (best score: {best_score:.2f})")

        return "Document rejected — " + "; ".join(issues)
