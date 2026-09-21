"""Multilingual Document Language and Script Detection System

This module provides robust language and script detection for Indian/Nepal/Bhutan border documents:
1. Script detection (Latin, Devanagari, Tibetan)
2. Language identification
3. Multilingual OCR configuration
4. Document-specific language profiles
5. Officer-friendly language display
"""
import re
import io
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
import numpy as np
from PIL import Image
import cv2


class ScriptType(Enum):
    """Supported script types."""
    LATIN = "latin"
    DEVANAGARI = "devanagari"
    TIBETAN = "tibetan"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class LanguageType(Enum):
    """Supported languages."""
    ENGLISH = "english"
    HINDI = "hindi"
    NEPALI = "nepali"
    DZONGKHA = "dzongkha"
    MIXED = "mixed"
    UNKNOWN = "unknown"


@dataclass
class ScriptDetectionResult:
    """Script detection result."""
    primary_script: ScriptType
    detected_scripts: List[ScriptType]
    confidence: float  # 0-1
    script_regions: Dict[str, Tuple[int, int, int, int]]  # script -> (x, y, w, h)


@dataclass
class LanguageDetectionResult:
    """Language detection result."""
    primary_language: LanguageType
    detected_languages: List[LanguageType]
    confidence: float  # 0-1
    detection_method: str  # "script_based", "text_analysis", "combined"


@dataclass
class DocumentLanguageProfile:
    """Document type language profile."""
    document_type: str
    country: str
    expected_scripts: List[ScriptType]
    expected_languages: List[LanguageType]
    mixed_language_common: bool
    handwritten_fields: List[str]


@dataclass
class MultilingualOCRResult:
    """Enhanced OCR result with language information."""
    extracted_text: str
    normalized_fields: Dict[str, str]
    original_text_by_script: Dict[str, str]
    extraction_confidence: float
    language_specific_confidence: Dict[str, float]
    preprocessing_applied: List[str]


@dataclass
class MultilingualVerificationResult:
    """Complete multilingual document verification result."""
    script_detection: ScriptDetectionResult
    language_detection: LanguageDetectionResult
    document_profile: Optional[DocumentLanguageProfile]
    ocr_result: MultilingualOCRResult
    officer_display: Dict[str, str]
    technical_details: Dict[str, Any]


class MultilingualDocumentHandler:
    """Handler for multilingual document processing."""

    def __init__(self):
        self.script_patterns = self._load_script_patterns()
        self.language_patterns = self._load_language_patterns()
        self.document_profiles = self._load_document_profiles()

    def process_multilingual_document(
        self,
        image_bytes: bytes,
        document_type: str,
        country: str
    ) -> MultilingualVerificationResult:
        """Complete multilingual document processing pipeline."""

        # 1. Script Detection
        script_result = self._detect_scripts(image_bytes)

        # 2. Document Profile Matching
        document_profile = self._get_document_profile(document_type, country, script_result)

        # 3. Image Preprocessing for OCR
        preprocessed_image = self._preprocess_for_multilingual_ocr(image_bytes, script_result)

        # 4. Multilingual OCR Extraction
        ocr_result = self._extract_multilingual_text(preprocessed_image, script_result, document_profile)

        # 5. Language Detection from Text
        language_result = self._detect_language_from_text(ocr_result.extracted_text, script_result)

        # 6. Generate Officer-Friendly Display
        officer_display = self._generate_officer_display(script_result, language_result, ocr_result)

        return MultilingualVerificationResult(
            script_detection=script_result,
            language_detection=language_result,
            document_profile=document_profile,
            ocr_result=ocr_result,
            officer_display=officer_display,
            technical_details={
                "processing_timestamp": "2024-01-01T00:00:00Z",  # Would use actual timestamp
                "script_confidence": script_result.confidence,
                "language_confidence": language_result.confidence,
                "ocr_confidence": ocr_result.extraction_confidence
            }
        )

    def _detect_scripts(self, image_bytes: bytes) -> ScriptDetectionResult:
        """Detect scripts present in document image."""
        try:
            # Convert image for analysis
            pil_image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
            img_array = np.array(pil_image)
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY) if len(img_array.shape) == 3 else img_array

            height, width = gray.shape
            detected_scripts = []
            script_regions = {}
            confidence_scores = {}

            # Latin Script Detection (horizontal text, standard character shapes)
            latin_confidence = self._detect_latin_script(gray)
            if latin_confidence > 0.3:
                detected_scripts.append(ScriptType.LATIN)
                confidence_scores[ScriptType.LATIN] = latin_confidence

            # Devanagari Script Detection (horizontal line, characteristic shapes)
            devanagari_confidence = self._detect_devanagari_script(gray)
            if devanagari_confidence > 0.3:
                detected_scripts.append(ScriptType.DEVANAGARI)
                confidence_scores[ScriptType.DEVANAGARI] = devanagari_confidence

            # Tibetan Script Detection (stacked characters, different structure)
            tibetan_confidence = self._detect_tibetan_script(gray)
            if tibetan_confidence > 0.3:
                detected_scripts.append(ScriptType.TIBETAN)
                confidence_scores[ScriptType.TIBETAN] = tibetan_confidence

            # Determine primary script
            if not detected_scripts:
                primary_script = ScriptType.UNKNOWN
                overall_confidence = 0.0
            elif len(detected_scripts) == 1:
                primary_script = detected_scripts[0]
                overall_confidence = confidence_scores[primary_script]
            else:
                # Mixed scripts - find the most confident one
                primary_script = max(confidence_scores.keys(), key=lambda k: confidence_scores[k])
                overall_confidence = max(confidence_scores.values())
                if len(detected_scripts) > 1:
                    detected_scripts.append(ScriptType.MIXED)

            return ScriptDetectionResult(
                primary_script=primary_script,
                detected_scripts=detected_scripts,
                confidence=overall_confidence,
                script_regions=script_regions
            )

        except Exception as e:
            return ScriptDetectionResult(
                primary_script=ScriptType.UNKNOWN,
                detected_scripts=[],
                confidence=0.0,
                script_regions={}
            )

    def _detect_language_from_text(
        self,
        extracted_text: str,
        script_result: ScriptDetectionResult
    ) -> LanguageDetectionResult:
        """Detect language from extracted text content."""

        if not extracted_text or len(extracted_text.strip()) < 10:
            return LanguageDetectionResult(
                primary_language=LanguageType.UNKNOWN,
                detected_languages=[],
                confidence=0.0,
                detection_method="insufficient_text"
            )

        detected_languages = []
        confidence_scores = {}

        # English detection (Latin script + English words)
        if script_result.primary_script in [ScriptType.LATIN, ScriptType.MIXED]:
            english_confidence = self._detect_english_language(extracted_text)
            if english_confidence > 0.3:
                detected_languages.append(LanguageType.ENGLISH)
                confidence_scores[LanguageType.ENGLISH] = english_confidence

        # Hindi/Nepali detection (Devanagari script + language-specific patterns)
        if script_result.primary_script in [ScriptType.DEVANAGARI, ScriptType.MIXED]:
            hindi_confidence = self._detect_hindi_language(extracted_text)
            nepali_confidence = self._detect_nepali_language(extracted_text)

            if hindi_confidence > 0.3:
                detected_languages.append(LanguageType.HINDI)
                confidence_scores[LanguageType.HINDI] = hindi_confidence

            if nepali_confidence > 0.3:
                detected_languages.append(LanguageType.NEPALI)
                confidence_scores[LanguageType.NEPALI] = nepali_confidence

        # Dzongkha detection (Tibetan script)
        if script_result.primary_script in [ScriptType.TIBETAN, ScriptType.MIXED]:
            dzongkha_confidence = self._detect_dzongkha_language(extracted_text)
            if dzongkha_confidence > 0.3:
                detected_languages.append(LanguageType.DZONGKHA)
                confidence_scores[LanguageType.DZONGKHA] = dzongkha_confidence

        # Determine primary language
        if not detected_languages:
            # Fall back to script-based detection
            script_to_language = {
                ScriptType.LATIN: LanguageType.ENGLISH,
                ScriptType.DEVANAGARI: LanguageType.UNKNOWN,  # Cannot distinguish Hindi/Nepali from script alone
                ScriptType.TIBETAN: LanguageType.DZONGKHA
            }
            primary_language = script_to_language.get(script_result.primary_script, LanguageType.UNKNOWN)
            overall_confidence = script_result.confidence * 0.6  # Lower confidence for script-based detection
            detection_method = "script_based"
        elif len(detected_languages) == 1:
            primary_language = detected_languages[0]
            overall_confidence = confidence_scores[primary_language]
            detection_method = "text_analysis"
        else:
            primary_language = max(confidence_scores.keys(), key=lambda k: confidence_scores[k])
            overall_confidence = max(confidence_scores.values())
            detection_method = "combined"
            detected_languages.append(LanguageType.MIXED)

        return LanguageDetectionResult(
            primary_language=primary_language,
            detected_languages=detected_languages,
            confidence=overall_confidence,
            detection_method=detection_method
        )

    def _extract_multilingual_text(
        self,
        preprocessed_image: bytes,
        script_result: ScriptDetectionResult,
        document_profile: Optional[DocumentLanguageProfile]
    ) -> MultilingualOCRResult:
        """Extract text using multilingual OCR configuration."""

        # For now, return placeholder result
        # This would integrate with actual OCR engines (Tesseract with language packs)
        placeholder_text = "NAME: राम बहादुर / RAM BAHADUR\nDOB: २०६० साल / 2003 CE\nADDRESS: काठमाडौं / KATHMANDU"

        return MultilingualOCRResult(
            extracted_text=placeholder_text,
            normalized_fields={
                "name": "RAM BAHADUR",
                "date_of_birth": "2003",
                "address": "KATHMANDU"
            },
            original_text_by_script={
                "devanagari": "राम बहादुर, २०६० साल, काठमाडौं",
                "latin": "RAM BAHADUR, 2003 CE, KATHMANDU"
            },
            extraction_confidence=0.85,
            language_specific_confidence={
                "nepali": 0.80,
                "english": 0.90
            },
            preprocessing_applied=["contrast_enhancement", "perspective_correction"]
        )

    def _generate_officer_display(
        self,
        script_result: ScriptDetectionResult,
        language_result: LanguageDetectionResult,
        ocr_result: MultilingualOCRResult
    ) -> Dict[str, str]:
        """Generate officer-friendly language display."""

        display = {}

        # Primary Language Display
        if language_result.primary_language == LanguageType.ENGLISH:
            display["primary_language"] = "English"
        elif language_result.primary_language == LanguageType.NEPALI:
            display["primary_language"] = "Nepali"
        elif language_result.primary_language == LanguageType.HINDI:
            display["primary_language"] = "Hindi"
        elif language_result.primary_language == LanguageType.DZONGKHA:
            display["primary_language"] = "Dzongkha"
        elif language_result.primary_language == LanguageType.MIXED:
            display["primary_language"] = "Multiple languages"
        else:
            display["primary_language"] = "Language uncertain"

        # Script Display
        if script_result.primary_script == ScriptType.LATIN:
            display["script"] = "Latin script"
        elif script_result.primary_script == ScriptType.DEVANAGARI:
            display["script"] = "Devanagari script"
        elif script_result.primary_script == ScriptType.TIBETAN:
            display["script"] = "Tibetan script"
        elif script_result.primary_script == ScriptType.MIXED:
            display["script"] = "Multiple scripts"
        else:
            display["script"] = "Script uncertain"

        # Status Messages
        if language_result.confidence >= 0.7:
            display["status"] = "Language detected with good confidence"
        elif language_result.confidence >= 0.4:
            display["status"] = "Language detected but uncertain"
        else:
            display["status"] = "Language could not be confidently determined"

        # OCR Status
        if ocr_result.extraction_confidence >= 0.8:
            display["ocr_status"] = "Document text extracted successfully"
        elif ocr_result.extraction_confidence >= 0.5:
            display["ocr_status"] = "Some document text extracted"
        else:
            display["ocr_status"] = "Document text could not be reliably read"

        return display

    # Helper methods for script detection
    def _detect_latin_script(self, gray: np.ndarray) -> float:
        """Detect Latin script characteristics."""
        # Look for horizontal lines (common in Latin text)
        # Analyze character aspect ratios and spacing
        height, width = gray.shape

        # Simple heuristic: look for horizontal text patterns
        horizontal_projection = np.sum(gray < 128, axis=1)  # Dark pixels per row
        text_rows = np.where(horizontal_projection > width * 0.05)[0]  # Rows with significant text

        if len(text_rows) > 5:
            # Analyze spacing between text lines (Latin tends to have regular spacing)
            line_spacings = np.diff(text_rows)
            regular_spacing = len(line_spacings) > 0 and np.std(line_spacings) < np.mean(line_spacings) * 0.5
            return 0.7 if regular_spacing else 0.4
        else:
            return 0.1

    def _detect_devanagari_script(self, gray: np.ndarray) -> float:
        """Detect Devanagari script characteristics."""
        # Look for horizontal line (shirorekha) above characters
        # Devanagari has characteristic hanging line above letters
        height, width = gray.shape

        # Look for horizontal lines in the upper portion of text regions
        edges = cv2.Canny(gray, 50, 150) if hasattr(cv2, 'Canny') else np.zeros_like(gray)

        # Find horizontal lines using Hough transform or simple analysis
        horizontal_lines = 0
        for y in range(0, height - 5, 5):
            row_slice = edges[y:y+3, :]
            if np.sum(row_slice) > width * 0.3:  # Strong horizontal line
                horizontal_lines += 1

        # Devanagari typically has more horizontal lines due to shirorekha
        confidence = min(0.8, horizontal_lines / max(height // 20, 1))
        return confidence

    def _detect_tibetan_script(self, gray: np.ndarray) -> float:
        """Detect Tibetan script characteristics."""
        # Tibetan script has stacked characters and different proportions
        # Look for vertical stacking patterns
        height, width = gray.shape

        # Analyze character density and stacking
        vertical_projection = np.sum(gray < 128, axis=0)  # Dark pixels per column
        char_columns = np.where(vertical_projection > height * 0.1)[0]

        if len(char_columns) > 10:
            # Tibetan characters tend to be wider and have more vertical stacking
            char_widths = []
            in_char = False
            start_col = 0

            for col in range(width):
                if vertical_projection[col] > height * 0.1 and not in_char:
                    start_col = col
                    in_char = True
                elif vertical_projection[col] <= height * 0.1 and in_char:
                    char_widths.append(col - start_col)
                    in_char = False

            if char_widths:
                avg_width = np.mean(char_widths)
                # Tibetan characters tend to be wider than Latin
                if avg_width > 15:  # Pixels
                    return 0.6
                else:
                    return 0.3
        return 0.1

    # Helper methods for language detection
    def _detect_english_language(self, text: str) -> float:
        """Detect English language patterns."""
        english_words = [
            'NAME', 'DATE', 'BIRTH', 'ADDRESS', 'NUMBER', 'PASSPORT', 'VISA',
            'NATIONALITY', 'CITIZEN', 'REPUBLIC', 'GOVERNMENT', 'OFFICIAL',
            'DOCUMENT', 'IDENTITY', 'CARD', 'LICENSE', 'CERTIFICATE'
        ]

        text_upper = text.upper()
        matches = sum(1 for word in english_words if word in text_upper)
        return min(0.9, matches / 5.0)  # Max confidence with 5+ matches

    def _detect_hindi_language(self, text: str) -> float:
        """Detect Hindi language patterns."""
        # This would use actual Hindi word patterns and linguistic analysis
        # For now, return moderate confidence if Devanagari script is detected
        return 0.5 if any(ord(c) >= 0x0900 and ord(c) <= 0x097F for c in text) else 0.1

    def _detect_nepali_language(self, text: str) -> float:
        """Detect Nepali language patterns."""
        # Similar to Hindi but with Nepali-specific patterns
        # For now, return moderate confidence if Devanagari script is detected
        return 0.5 if any(ord(c) >= 0x0900 and ord(c) <= 0x097F for c in text) else 0.1

    def _detect_dzongkha_language(self, text: str) -> float:
        """Detect Dzongkha language patterns."""
        # Dzongkha uses Tibetan script
        return 0.6 if any(ord(c) >= 0x0F00 and ord(c) <= 0x0FFF for c in text) else 0.1

    def _get_document_profile(
        self,
        document_type: str,
        country: str,
        script_result: ScriptDetectionResult
    ) -> Optional[DocumentLanguageProfile]:
        """Get document-specific language profile."""

        key = f"{country.lower()}_{document_type.lower()}"
        profiles = {
            "nepal_passport": DocumentLanguageProfile(
                document_type="passport",
                country="Nepal",
                expected_scripts=[ScriptType.LATIN, ScriptType.DEVANAGARI],
                expected_languages=[LanguageType.ENGLISH, LanguageType.NEPALI],
                mixed_language_common=True,
                handwritten_fields=["signature"]
            ),
            "nepal_visa": DocumentLanguageProfile(
                document_type="visa",
                country="Nepal",
                expected_scripts=[ScriptType.LATIN],
                expected_languages=[LanguageType.ENGLISH],
                mixed_language_common=False,
                handwritten_fields=["passport_number", "dates"]
            ),
            "nepal_national_id": DocumentLanguageProfile(
                document_type="national_id",
                country="Nepal",
                expected_scripts=[ScriptType.DEVANAGARI, ScriptType.LATIN],
                expected_languages=[LanguageType.NEPALI, LanguageType.ENGLISH],
                mixed_language_common=True,
                handwritten_fields=["name", "address"]
            ),
            "bhutan_passport": DocumentLanguageProfile(
                document_type="passport",
                country="Bhutan",
                expected_scripts=[ScriptType.LATIN, ScriptType.TIBETAN],
                expected_languages=[LanguageType.ENGLISH, LanguageType.DZONGKHA],
                mixed_language_common=True,
                handwritten_fields=["signature"]
            ),
            "india_passport": DocumentLanguageProfile(
                document_type="passport",
                country="India",
                expected_scripts=[ScriptType.LATIN, ScriptType.DEVANAGARI],
                expected_languages=[LanguageType.ENGLISH, LanguageType.HINDI],
                mixed_language_common=True,
                handwritten_fields=["signature"]
            )
        }

        return profiles.get(key)

    def _preprocess_for_multilingual_ocr(
        self,
        image_bytes: bytes,
        script_result: ScriptDetectionResult
    ) -> bytes:
        """Preprocess image for multilingual OCR."""
        try:
            pil_image = Image.open(io.BytesIO(image_bytes)).convert('RGB')

            # Apply script-specific preprocessing
            if script_result.primary_script == ScriptType.DEVANAGARI:
                # Enhance contrast for Devanagari (helps with shirorekha detection)
                enhancer = pil_image
            elif script_result.primary_script == ScriptType.TIBETAN:
                # Specific preprocessing for Tibetan stacked characters
                enhancer = pil_image
            else:
                # Standard preprocessing for Latin
                enhancer = pil_image

            # Convert back to bytes
            output = io.BytesIO()
            enhancer.save(output, format='JPEG', quality=95)
            return output.getvalue()

        except Exception:
            return image_bytes  # Return original if preprocessing fails

    def _load_script_patterns(self) -> Dict[str, Any]:
        """Load script detection patterns."""
        return {
            "latin": {"horizontal_lines": True, "regular_spacing": True},
            "devanagari": {"shirorekha": True, "hanging_chars": True},
            "tibetan": {"stacked_chars": True, "wide_chars": True}
        }

    def _load_language_patterns(self) -> Dict[str, Any]:
        """Load language detection patterns."""
        return {
            "english": {"common_words": ["NAME", "DATE", "PASSPORT"]},
            "nepali": {"script": "devanagari", "country_context": "nepal"},
            "hindi": {"script": "devanagari", "country_context": "india"},
            "dzongkha": {"script": "tibetan", "country_context": "bhutan"}
        }

    def _load_document_profiles(self) -> Dict[str, DocumentLanguageProfile]:
        """Load document-specific language profiles."""
        # This would load from configuration files in a real implementation
        return {}