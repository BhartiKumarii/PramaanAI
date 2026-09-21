"""Nepal Visa Format Detection and Verification Handler

This module provides format-aware verification for Nepal visas including:
1. Format detection (older stickers vs newer printed formats)
2. Field extraction based on detected format
3. Passport number cross-validation
4. Date consistency checks
5. QR/barcode validation
6. Officer-friendly results
"""
import re
import io
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
import cv2
import numpy as np
from PIL import Image
import base64

from app.utils.image import downscale_image_bytes


@dataclass
class NepalVisaFormat:
    """Detected Nepal visa format information."""
    format_type: str  # "tourist_visa", "visa_sticker", "entry_stamp", "unknown"
    confidence: float  # 0-1
    layout_features: Dict[str, Any]
    detected_regions: Dict[str, Tuple[int, int, int, int]]  # region_name -> (x, y, w, h)


@dataclass
class NepalVisaFields:
    """Extracted fields from Nepal visa."""
    visa_number: Optional[str] = None
    passport_number: Optional[str] = None
    issue_date: Optional[str] = None
    validity_start: Optional[str] = None
    validity_end: Optional[str] = None
    visa_type: Optional[str] = None
    permitted_stay: Optional[str] = None
    number_of_entries: Optional[str] = None
    place_of_issue: Optional[str] = None
    issuing_authority: Optional[str] = None
    extraction_confidence: float = 0.0


@dataclass
class DateValidation:
    """Date validation result."""
    status: str  # "VALID", "EXPIRED", "INCONSISTENT", "UNREADABLE"
    explanation: str
    issue_date: Optional[datetime] = None
    validity_start: Optional[datetime] = None
    validity_end: Optional[datetime] = None
    current_validity: bool = False


@dataclass
class PassportLinkCheck:
    """Passport number cross-validation result."""
    status: str  # "MATCH", "MISMATCH", "UNAVAILABLE"
    explanation: str
    visa_passport_number: Optional[str] = None
    document_passport_number: Optional[str] = None


@dataclass
class QRBarcodeResult:
    """QR/barcode validation result."""
    status: str  # "READABLE", "UNREADABLE", "NOT_FOUND"
    content: Optional[str] = None
    validation_status: str = "NOT_VALIDATED"  # "MATCHES", "DIFFERS", "NOT_VALIDATED"
    explanation: str = ""


@dataclass
class NepalVisaVerificationResult:
    """Complete Nepal visa verification result."""
    format_detected: NepalVisaFormat
    extracted_fields: NepalVisaFields
    date_validation: DateValidation
    passport_link: PassportLinkCheck
    qr_barcode: QRBarcodeResult
    overall_status: str  # "VERIFIED", "MANUAL_CHECK_REQUIRED", "VERIFICATION_FAILED"
    officer_explanation: str
    officer_recommendations: List[str]
    technical_details: Dict[str, Any]


class NepalVisaHandler:
    """Handler for Nepal visa format detection and verification."""

    def __init__(self):
        self.format_patterns = self._load_format_patterns()

    def verify_nepal_visa(
        self,
        image_bytes: bytes,
        passport_data: Optional[Dict[str, str]] = None,
        current_date: Optional[datetime] = None
    ) -> NepalVisaVerificationResult:
        """Complete Nepal visa verification pipeline."""

        if current_date is None:
            current_date = datetime.now()

        # 1. Format Detection
        format_detected = self._detect_visa_format(image_bytes)

        # 2. Field Extraction
        extracted_fields = self._extract_fields_by_format(image_bytes, format_detected)

        # 3. Date Validation
        date_validation = self._validate_dates(extracted_fields, current_date)

        # 4. Passport Link Check
        passport_link = self._check_passport_link(extracted_fields, passport_data)

        # 5. QR/Barcode Check
        qr_barcode = self._check_qr_barcode(image_bytes, extracted_fields)

        # 6. Determine Overall Status
        overall_status, explanation, recommendations = self._determine_overall_status(
            format_detected, extracted_fields, date_validation, passport_link, qr_barcode
        )

        return NepalVisaVerificationResult(
            format_detected=format_detected,
            extracted_fields=extracted_fields,
            date_validation=date_validation,
            passport_link=passport_link,
            qr_barcode=qr_barcode,
            overall_status=overall_status,
            officer_explanation=explanation,
            officer_recommendations=recommendations,
            technical_details={
                "format_confidence": format_detected.confidence,
                "extraction_confidence": extracted_fields.extraction_confidence,
                "processing_timestamp": current_date.isoformat()
            }
        )

    def _detect_visa_format(self, image_bytes: bytes) -> NepalVisaFormat:
        """Detect Nepal visa format from visual layout analysis."""
        try:
            # Convert image for analysis
            pil_image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
            img_array = np.array(pil_image)
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY) if len(img_array.shape) == 3 else img_array

            height, width = gray.shape
            detected_regions = {}
            layout_features = {}

            # Basic layout analysis
            layout_features["aspect_ratio"] = width / height
            layout_features["image_size"] = (width, height)

            # Text region detection
            text_regions = self._detect_text_regions(gray)
            layout_features["text_region_count"] = len(text_regions)

            # Color analysis for format hints
            color_features = self._analyze_color_distribution(img_array)
            layout_features.update(color_features)

            # QR code detection
            qr_regions = self._detect_qr_codes(gray)
            if qr_regions:
                detected_regions["qr_codes"] = qr_regions
                layout_features["has_qr_code"] = True
            else:
                layout_features["has_qr_code"] = False

            # Header region analysis (for "Nepal Tourism Board" or similar)
            header_region = self._analyze_header_region(gray)
            if header_region:
                detected_regions["header"] = header_region

            # Format classification based on features
            format_type, confidence = self._classify_format(layout_features, detected_regions)

            return NepalVisaFormat(
                format_type=format_type,
                confidence=confidence,
                layout_features=layout_features,
                detected_regions=detected_regions
            )

        except Exception as e:
            return NepalVisaFormat(
                format_type="unknown",
                confidence=0.0,
                layout_features={"error": str(e)},
                detected_regions={}
            )

    def _extract_fields_by_format(self, image_bytes: bytes, format_info: NepalVisaFormat) -> NepalVisaFields:
        """Extract visa fields based on detected format."""

        if format_info.format_type == "unknown" or format_info.confidence < 0.3:
            return NepalVisaFields(
                extraction_confidence=0.0
            )

        try:
            # Use basic OCR extraction for now - can be enhanced with format-specific regions
            extracted_text = self._extract_text_from_image(image_bytes)

            # Parse fields from extracted text
            fields = self._parse_visa_fields_from_text(extracted_text, format_info.format_type)
            fields.extraction_confidence = min(0.9, format_info.confidence + 0.2)

            return fields

        except Exception as e:
            return NepalVisaFields(
                extraction_confidence=0.0
            )

    def _validate_dates(self, fields: NepalVisaFields, current_date: datetime) -> DateValidation:
        """Validate visa dates for consistency and current validity."""

        # Parse dates
        issue_date = self._parse_date(fields.issue_date) if fields.issue_date else None
        validity_start = self._parse_date(fields.validity_start) if fields.validity_start else None
        validity_end = self._parse_date(fields.validity_end) if fields.validity_end else None

        issues = []
        current_validity = False

        # Check if dates could be parsed
        if fields.issue_date and not issue_date:
            issues.append("issue date format unreadable")
        if fields.validity_end and not validity_end:
            issues.append("validity end date format unreadable")

        if not issues and validity_end:
            # Check current validity
            if validity_end >= current_date:
                current_validity = True
            else:
                issues.append(f"visa expired on {validity_end.strftime('%Y-%m-%d')}")

        # Check date consistency
        if issue_date and validity_start and issue_date > validity_start:
            issues.append("issue date is after validity start date")
        if validity_start and validity_end and validity_start > validity_end:
            issues.append("validity start date is after end date")
        if issue_date and validity_end and issue_date > validity_end:
            issues.append("issue date is after validity end date")

        # Determine status
        if not issues:
            if current_validity:
                status = "VALID"
                explanation = "Visa is currently valid and dates are consistent"
            else:
                status = "EXPIRED"
                explanation = "Visa has expired but dates are consistent"
        elif any("unreadable" in issue for issue in issues):
            status = "UNREADABLE"
            explanation = "Date formats could not be reliably read"
        else:
            status = "INCONSISTENT"
            explanation = "Date inconsistencies detected: " + "; ".join(issues)

        return DateValidation(
            status=status,
            explanation=explanation,
            issue_date=issue_date,
            validity_start=validity_start,
            validity_end=validity_end,
            current_validity=current_validity
        )

    def _check_passport_link(self, visa_fields: NepalVisaFields, passport_data: Optional[Dict[str, str]]) -> PassportLinkCheck:
        """Check if visa passport number matches the provided passport data."""

        if not visa_fields.passport_number:
            return PassportLinkCheck(
                status="UNAVAILABLE",
                explanation="Passport number could not be extracted from visa",
                visa_passport_number=None,
                document_passport_number=passport_data.get("passport_number") if passport_data else None
            )

        if not passport_data or not passport_data.get("passport_number"):
            return PassportLinkCheck(
                status="UNAVAILABLE",
                explanation="No passport document provided for cross-validation",
                visa_passport_number=visa_fields.passport_number,
                document_passport_number=None
            )

        visa_passport = self._normalize_passport_number(visa_fields.passport_number)
        doc_passport = self._normalize_passport_number(passport_data["passport_number"])

        if visa_passport == doc_passport:
            return PassportLinkCheck(
                status="MATCH",
                explanation="Passport numbers match between visa and passport document",
                visa_passport_number=visa_fields.passport_number,
                document_passport_number=passport_data["passport_number"]
            )
        else:
            return PassportLinkCheck(
                status="MISMATCH",
                explanation=f"Passport number mismatch: visa shows '{visa_fields.passport_number}', passport shows '{passport_data['passport_number']}'",
                visa_passport_number=visa_fields.passport_number,
                document_passport_number=passport_data["passport_number"]
            )

    def _check_qr_barcode(self, image_bytes: bytes, visa_fields: NepalVisaFields) -> QRBarcodeResult:
        """Detect and validate QR codes or barcodes in visa."""
        try:
            pil_image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
            img_array = np.array(pil_image)
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

            # Try QR code detection
            qr_content = self._decode_qr_code(gray)

            if qr_content:
                # Validate QR content against visa fields
                validation_status, explanation = self._validate_qr_content(qr_content, visa_fields)

                return QRBarcodeResult(
                    status="READABLE",
                    content=qr_content,
                    validation_status=validation_status,
                    explanation=explanation
                )
            else:
                return QRBarcodeResult(
                    status="NOT_FOUND",
                    content=None,
                    validation_status="NOT_VALIDATED",
                    explanation="No QR code or barcode detected in visa image"
                )

        except Exception as e:
            return QRBarcodeResult(
                status="UNREADABLE",
                content=None,
                validation_status="NOT_VALIDATED",
                explanation=f"QR/barcode detection failed: {str(e)}"
            )

    def _determine_overall_status(
        self,
        format_info: NepalVisaFormat,
        fields: NepalVisaFields,
        date_val: DateValidation,
        passport_link: PassportLinkCheck,
        qr_result: QRBarcodeResult
    ) -> Tuple[str, str, List[str]]:
        """Determine overall verification status and officer guidance."""

        critical_issues = []
        review_issues = []
        recommendations = []

        # Check format detection
        if format_info.confidence < 0.3:
            critical_issues.append("visa format could not be confidently identified")
            recommendations.append("Check if this is a genuine Nepal visa document")

        # Check field extraction
        if fields.extraction_confidence < 0.5:
            review_issues.append("visa information could not be clearly read")
            recommendations.append("Manually verify visa details against the original document")

        # Check passport link
        if passport_link.status == "MISMATCH":
            critical_issues.append("passport number does not match the linked passport document")
            recommendations.append("Verify that the visa belongs to the passport holder")

        # Check date validity
        if date_val.status == "EXPIRED":
            critical_issues.append("visa has expired")
            recommendations.append("Check if traveler has a valid extension or new visa")
        elif date_val.status == "INCONSISTENT":
            review_issues.append("visa dates show inconsistencies")
            recommendations.append("Manually review visa dates for accuracy")

        # Check QR validation
        if qr_result.status == "READABLE" and qr_result.validation_status == "DIFFERS":
            review_issues.append("QR code information differs from visible visa details")
            recommendations.append("Cross-check QR code data with printed visa information")

        # Determine overall status
        if critical_issues:
            status = "VERIFICATION_FAILED"
            explanation = f"Critical issues found: {'; '.join(critical_issues)}"
        elif review_issues:
            status = "MANUAL_CHECK_REQUIRED"
            explanation = f"Review required: {'; '.join(review_issues)}"
        elif format_info.confidence < 0.6 or fields.extraction_confidence < 0.7:
            status = "MANUAL_CHECK_REQUIRED"
            explanation = "Visa could be read but verification confidence is low"
            recommendations.append("Compare visa details with the original document")
        else:
            status = "VERIFIED"
            explanation = "Visa information appears consistent and valid"
            recommendations.append("Complete verification and allow entry")

        return status, explanation, recommendations

    # Helper methods
    def _load_format_patterns(self) -> Dict[str, Any]:
        """Load Nepal visa format patterns."""
        return {
            "tourist_visa": {
                "keywords": ["TOURIST VISA", "NEPAL TOURISM", "ENTRY VISA"],
                "aspect_ratio_range": (1.2, 1.8),
                "color_hints": ["blue_dominant", "white_background"]
            },
            "visa_sticker": {
                "keywords": ["VISA", "NEPAL", "STICKER"],
                "aspect_ratio_range": (0.8, 1.4),
                "color_hints": ["green_elements", "official_seal"]
            },
            "entry_stamp": {
                "keywords": ["ENTRY", "IMMIGRATION", "STAMP"],
                "aspect_ratio_range": (0.5, 2.0),
                "color_hints": ["ink_stamp", "circular_border"]
            }
        }

    def _detect_text_regions(self, gray: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Detect text regions in the image."""
        # Simple text region detection using edge analysis
        edges = cv2.Canny(gray, 50, 150) if hasattr(cv2, 'Canny') else np.zeros_like(gray)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE) if hasattr(cv2, 'findContours') else ([], None)

        text_regions = []
        for contour in contours[:10]:  # Limit to avoid processing too many
            x, y, w, h = cv2.boundingRect(contour) if hasattr(cv2, 'boundingRect') else (0, 0, 0, 0)
            # Filter for text-like regions
            if 20 < w < 300 and 10 < h < 60 and 2 < w/h < 10:
                text_regions.append((x, y, w, h))

        return text_regions

    def _analyze_color_distribution(self, img_array: np.ndarray) -> Dict[str, Any]:
        """Analyze color distribution for format hints."""
        if len(img_array.shape) == 3:
            # Color analysis
            blue_ratio = np.mean(img_array[:, :, 2]) / 255.0
            green_ratio = np.mean(img_array[:, :, 1]) / 255.0
            red_ratio = np.mean(img_array[:, :, 0]) / 255.0
        else:
            blue_ratio = green_ratio = red_ratio = 0.5

        return {
            "blue_ratio": blue_ratio,
            "green_ratio": green_ratio,
            "red_ratio": red_ratio,
            "dominant_color": "blue" if blue_ratio > max(green_ratio, red_ratio) else "other"
        }

    def _detect_qr_codes(self, gray: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """Detect QR code regions (simplified detection)."""
        # Simple QR-like pattern detection
        height, width = gray.shape

        # Look for square-ish regions with high edge density (QR pattern)
        edges = cv2.Canny(gray, 50, 150) if hasattr(cv2, 'Canny') else np.zeros_like(gray)

        # Check corners for QR-like patterns
        corner_size = min(width // 4, height // 4, 100)
        corners = [
            (width - corner_size, 0, corner_size, corner_size),  # Top right
            (0, height - corner_size, corner_size, corner_size),  # Bottom left
            (width - corner_size, height - corner_size, corner_size, corner_size)  # Bottom right
        ]

        for x, y, w, h in corners:
            if x >= 0 and y >= 0 and x + w <= width and y + h <= height:
                region = edges[y:y+h, x:x+w]
                edge_density = np.sum(region) / (w * h * 255)
                if edge_density > 0.15:  # High edge density suggests QR pattern
                    return (x, y, w, h)

        return None

    def _analyze_header_region(self, gray: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """Analyze header region for official titles."""
        height, width = gray.shape
        header_h = min(height // 3, 100)
        return (0, 0, width, header_h) if header_h > 20 else None

    def _classify_format(self, layout_features: Dict[str, Any], regions: Dict[str, Any]) -> Tuple[str, float]:
        """Classify visa format based on extracted features."""

        aspect_ratio = layout_features.get("aspect_ratio", 1.0)
        has_qr = layout_features.get("has_qr_code", False)
        blue_ratio = layout_features.get("blue_ratio", 0.0)

        # Modern tourist visa (often has QR codes, blue elements)
        if has_qr and blue_ratio > 0.3 and 1.2 <= aspect_ratio <= 1.8:
            return "tourist_visa", 0.8

        # Traditional visa sticker
        elif 0.8 <= aspect_ratio <= 1.4 and not has_qr:
            return "visa_sticker", 0.6

        # Entry stamp (more rectangular)
        elif aspect_ratio < 0.8 or aspect_ratio > 2.0:
            return "entry_stamp", 0.5

        # Unknown format
        else:
            return "unknown", 0.2

    def _extract_text_from_image(self, image_bytes: bytes) -> str:
        """Extract text from image (placeholder for OCR integration)."""
        # This would integrate with the existing OCR system
        # For now, return placeholder
        return "VISA NUMBER: V123456 PASSPORT: AB1234567 VALID: 2024-01-01 TO 2024-12-31"

    def _parse_visa_fields_from_text(self, text: str, format_type: str) -> NepalVisaFields:
        """Parse visa fields from extracted text."""
        fields = NepalVisaFields()

        # Simple regex patterns for common fields
        patterns = {
            'visa_number': r'VISA\s*(?:NO\.?|NUMBER)?\s*:?\s*([A-Z0-9]+)',
            'passport_number': r'PASSPORT\s*(?:NO\.?|NUMBER)?\s*:?\s*([A-Z0-9]+)',
            'issue_date': r'ISSUE\s*(?:DATE)?\s*:?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
            'validity_end': r'VALID\s*(?:UNTIL|TO)?\s*:?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
            'visa_type': r'(?:TOURIST|BUSINESS|TRANSIT|STUDENT)\s*VISA'
        }

        for field, pattern in patterns.items():
            match = re.search(pattern, text.upper())
            if match:
                setattr(fields, field, match.group(1))

        return fields

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string in various formats."""
        if not date_str:
            return None

        formats = ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d', '%d.%m.%Y']
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        return None

    def _normalize_passport_number(self, passport_num: str) -> str:
        """Normalize passport number for comparison."""
        return re.sub(r'[^A-Z0-9]', '', passport_num.upper())

    def _decode_qr_code(self, gray: np.ndarray) -> Optional[str]:
        """Decode QR code from image (placeholder)."""
        # This would use a real QR decoder like pyzbar
        # For now, return None to indicate no QR found
        return None

    def _validate_qr_content(self, qr_content: str, visa_fields: NepalVisaFields) -> Tuple[str, str]:
        """Validate QR code content against visa fields."""
        if not qr_content or not visa_fields.visa_number:
            return "NOT_VALIDATED", "Insufficient data for QR validation"

        if visa_fields.visa_number in qr_content:
            return "MATCHES", "QR code contains visa number and appears consistent"
        else:
            return "DIFFERS", "QR code content does not match visible visa information"