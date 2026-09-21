package com.pramaanai.officer.data.vision

import android.graphics.Bitmap
import android.util.Log
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import com.google.mlkit.vision.text.devanagari.DevanagariTextRecognizerOptions
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import java.util.regex.Pattern

/** On-device OCR only — this never leaves the device and never touches
 * the network (ML Kit's on-device text recognizer, not the Cloud one).
 * Produces the exact `ocr_fields` dict keys the backend's cross-check
 * expects (see app/services/validation/cross_check.py): "name",
 * "passport_number", "document_number", "nationality", "date_of_birth", "date_of_expiry"
 * (last two as DD/MM/YYYY), plus the raw recognized text for the
 * server's own MRZ-line search (extract_mrz_lines already tolerates
 * noise and picks well-formed 44-char lines out of a larger blob, so
 * this doesn't need a separate MRZ-zone crop step — the same OCR pass
 * over the full document photo covers both). Field extraction here is
 * heuristic (label-keyword matching over recognized lines) and
 * genuinely uncertain — callers must let the officer review/correct
 * before submitting, never treat this as guaranteed-accurate. */
object DocumentOcrExtractor {

    enum class CheckStatus { PASS, WARNING, FAIL, NOT_AVAILABLE }

    data class VerificationCheck(
        val name: String,
        val status: CheckStatus,
        val detail: String,
    )

    data class MrzCheckDigitResult(
        val passportNumber: CheckStatus,
        val dateOfBirth: CheckStatus,
        val dateOfExpiry: CheckStatus,
        val personalNumber: CheckStatus,
        val composite: CheckStatus,
        val checks: List<VerificationCheck>,
    )

    data class ExtractionResult(
        val fields: Map<String, String>,
        val rawText: String,
        /** Proxy confidence: ML Kit's on-device recognizer doesn't expose
         * a single scalar confidence score, so this is the fraction of
         * the 5 target fields the heuristic mapper actually found —
         * documented as a proxy, not a claimed OCR-engine confidence. */
        val confidence: Float,
        /** Detected MRZ lines for server-side validation */
        val mrzLines: List<String>,
        /** The two normalized 44-char MRZ lines joined by a newline, or null
         * when no valid TD3 pair was found — sent to the backend as
         * `mrz_text` in place of the whole noisy OCR blob. */
        val mrzText: String?,
        /** Document type detected from text patterns */
        val detectedDocumentType: String?,
        /** On-device MRZ check-digit validation results (null if no MRZ found) */
        val mrzCheckDigits: MrzCheckDigitResult? = null,
        /** On-device verification checks gathered during extraction */
        val verificationChecks: List<VerificationCheck> = emptyList(),
    )

    private const val TAG = "DocumentOcrExtractor"

    private val latinRecognizer by lazy { TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS) }
    private val devanagariRecognizer by lazy { TextRecognition.getClient(DevanagariTextRecognizerOptions.Builder().build()) }

    suspend fun recognize(bitmap: Bitmap): ExtractionResult {
        Log.d(TAG, "OCR input: ${bitmap.width}x${bitmap.height}, config=${bitmap.config}, recycled=${bitmap.isRecycled}")
        val image = InputImage.fromBitmap(bitmap, 0)

        // Run both Latin and Devanagari recognizers in parallel — Indian
        // identity documents (Aadhaar, PAN, voter ID) mix both scripts.
        val (latinText, devanagariText) = coroutineScope {
            val latinDeferred = async {
                suspendCancellableCoroutine { cont ->
                    latinRecognizer.process(image)
                        .addOnSuccessListener { result -> cont.resume(result.text) }
                        .addOnFailureListener { e ->
                            Log.w(TAG, "Latin recognizer failed", e)
                            cont.resume("")
                        }
                }
            }
            val devDeferred = async {
                suspendCancellableCoroutine { cont ->
                    devanagariRecognizer.process(image)
                        .addOnSuccessListener { result -> cont.resume(result.text) }
                        .addOnFailureListener { e ->
                            Log.w(TAG, "Devanagari recognizer failed", e)
                            cont.resume("")
                        }
                }
            }
            latinDeferred.await() to devDeferred.await()
        }

        // Merge: use the longer/richer text as the primary, supplement with
        // the other. The Devanagari recognizer also reads Latin script, so
        // it often produces a superset.
        val text = if (devanagariText.length > latinText.length) {
            Log.d(TAG, "Using Devanagari result (${devanagariText.length} chars) over Latin (${latinText.length} chars)")
            devanagariText
        } else {
            Log.d(TAG, "Using Latin result (${latinText.length} chars) over Devanagari (${devanagariText.length} chars)")
            latinText
        }
        val supplementaryText = if (text === devanagariText) latinText else devanagariText
        Log.d(TAG, "OCR raw text:\n$text")
        // Try MRZ from both texts (Latin is often better for MRZ since it's
        // strictly A-Z/0-9)
        val mrz = parseTd3Mrz(text) ?: parseTd3Mrz(supplementaryText)
        val combinedText = "$text\n$supplementaryText"
        val fields = LinkedHashMap(mapFields(text)).apply {
            // Fill gaps from the supplementary recognizer
            val suppFields = mapFields(supplementaryText)
            for ((k, v) in suppFields) {
                if (!containsKey(k)) put(k, v)
            }
            putAll(extractIndianDocumentNumbers(combinedText))
            joinedLabelledName(combinedText)?.let { put("name", it) }
            mrz?.let { putAll(it.fields) }
        }
        val mrzLines = mrz?.lines ?: emptyList()
        val docType = detectDocumentType(combinedText)
        val confidence = calculateConfidence(fields, mrzLines, docType)

        // Build on-device verification checks
        val checks = mutableListOf<VerificationCheck>()
        // MRZ check-digit results
        mrz?.checkDigits?.checks?.let { checks.addAll(it) }
        // MRZ ↔ printed-field consistency
        if (mrz != null) {
            checks.addAll(mrzFieldConsistencyChecks(mrz.fields, fields))
        }
        // Document type detection check
        if (docType != null) {
            checks.add(VerificationCheck("Document type detection", CheckStatus.PASS, "Detected as ${docType.replace("_", " ")}"))
        } else {
            checks.add(VerificationCheck("Document type detection", CheckStatus.WARNING, "Could not determine document type from text patterns"))
        }
        // Field completeness check
        val criticalFields = listOf("name", "date_of_birth")
        val missingCritical = criticalFields.filter { !fields.containsKey(it) || fields[it].isNullOrBlank() }
        if (missingCritical.isEmpty()) {
            checks.add(VerificationCheck("Critical field extraction", CheckStatus.PASS, "Name and date of birth extracted"))
        } else {
            checks.add(VerificationCheck("Critical field extraction", CheckStatus.WARNING, "Missing: ${missingCritical.joinToString(", ").replace("_", " ")}"))
        }
        // Document number presence
        val hasDocNum = fields.keys.any { it in setOf("passport_number", "document_number", "aadhaar_number", "pan_number", "voter_id", "dl_number", "visa_number") }
        if (hasDocNum) {
            checks.add(VerificationCheck("Document number extraction", CheckStatus.PASS, "Document number found"))
        } else {
            checks.add(VerificationCheck("Document number extraction", CheckStatus.WARNING, "No document number detected"))
        }
        // Expiry check
        fields["date_of_expiry"]?.let { expStr ->
            val expCheck = checkExpiry(expStr)
            if (expCheck != null) checks.add(expCheck)
        }

        Log.d(TAG, "Extraction: ${fields.size} fields, confidence=$confidence, docType=$docType, checks=${checks.size}")
        return ExtractionResult(
            fields = fields,
            rawText = text,
            confidence = confidence,
            mrzLines = mrzLines,
            mrzText = mrz?.lines?.takeIf { it.isNotEmpty() }?.joinToString("\n"),
            detectedDocumentType = docType,
            mrzCheckDigits = mrz?.checkDigits,
            verificationChecks = checks,
        )
    }

    private val LABELS = mapOf(
        "name" to listOf(
            "given name", "surname", "name", "full name",
            "nom", "nombre", "nome", "name:", "given", "surname:",
            // Hindi/Indian labels
            "नाम", "पूरा नाम", "नाम:", "पिता का नाम", "father", "father name", "father's name",
            // Nepali labels
            "पुरा नाम", "थर",
            // Bhutanese / Dzongkha
            "མིང་",
        ),
        "passport_number" to listOf(
            "passport no", "passport number", "passport no.", "passport #",
            "document no", "document number", "doc no", "doc number",
            "passport:", "passport no:", "passport number:",
            "पासपोर्ट नं", "राहदानी नं",
        ),
        "document_number" to listOf(
            "document no", "document number", "doc no", "doc number",
            "id no", "id number", "identity no", "identity number",
            // Indian documents
            "aadhaar no", "aadhar no", "aadhaar number", "aadhaar", "आधार संख्या", "आधार नं", "आधार",
            "pan no", "pan number", "permanent account number", "पैन", "पैन नं",
            "licence no", "license no", "licence number", "license number", "dl no",
            "driving licence", "driving license", "अनुज्ञापत्र",
            "permit no", "permit number", "visa no", "visa number",
            // Voter ID
            "voter id", "voter no", "epic no", "electoral roll", "मतदाता",
            // Nepali citizenship certificate
            "नागरिकता नं", "प्रमाणपत्र नं", "na. pra. no",
            // Bhutanese CID
            "cid no", "cid number", "citizen identity",
        ),
        "nationality" to listOf(
            "nationality", "nationality:", "citizenship", "country",
            "nationality/citizenship", "nationalité", "nacionalidad",
            "राष्ट्रियता", "नागरिकता",
        ),
        "date_of_birth" to listOf(
            "date of birth", "birth", "dob", "d.o.b.", "born",
            "date of birth:", "birth date", "birthday",
            // Hindi labels
            "जन्म तिथि", "जन्म दिनांक", "जन्मतारीख", "जन्म",
            // Nepali
            "जन्म मिति",
        ),
        "date_of_expiry" to listOf(
            "date of expiry", "expiry", "expiration", "expires",
            "valid until", "valid till", "expiry date", "date of expiration",
            // Hindi/Nepali
            "वैधता", "अन्तिम तिथि", "म्याद सकिने",
        ),
        "gender" to listOf(
            "sex", "gender", "m/f", "male/female",
            "लिंग", "जेंडर", "पुरुष", "महिला", "male", "female",
        ),
        "place_of_birth" to listOf(
            "place of birth", "birth place", "pob", "place of birth:",
            "जन्म स्थान",
        ),
        "date_of_issue" to listOf(
            "date of issue", "issue date", "issued", "date of issue:",
            "जारी मिति", "जारी तिथि",
        ),
        "issuing_authority" to listOf(
            "issuing authority", "authority", "issued by", "issuing office",
        ),
    )

    private val DATE_PATTERN = Regex("""(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})""")
    private val MRZ_PATTERN = Pattern.compile("""^[A-Z0-9<]{44}$""")
    private val PASSPORT_MRZ_PATTERN = Pattern.compile("""^P[A-Z0-9<]{43}$""")
    private val ID_CARD_MRZ_PATTERN = Pattern.compile("""^I[A-Z0-9<]{43}$""")

    // Indian document patterns
    private val AADHAAR_PATTERN = Regex("""(\d{4}\s?\d{4}\s?\d{4})""") // 12 digits with optional spaces
    private val PAN_PATTERN = Regex("""([A-Z]{5}\d{4}[A-Z])""") // 5 letters + 4 digits + 1 letter
    private val INDIAN_PASSPORT_PATTERN = Regex("""([A-Z]\d{7})""") // 1 letter + 7 digits
    private val VOTER_ID_PATTERN = Regex("""([A-Z]{3}\d{7})""") // 3 letters + 7 digits
    // Indian DL number: state code (2 letters) + RTO code (2 digits) + space/dash + year (4 digits) + space/dash + serial (7 digits)
    // e.g., KA01 2015 0001234, DL-0520190001234, MH12 20210001234
    private val DL_NUMBER_PATTERN = Regex("""([A-Z]{2}[\s\-]?\d{2}[\s\-]?\d{4}[\s\-]?\d{7})""")

    // Verhoeff checksum for on-device Aadhaar number validation — picks
    // the correct 12-digit candidate when OCR finds multiple on the card.
    private val VERHOEFF_D = arrayOf(
        intArrayOf(0,1,2,3,4,5,6,7,8,9), intArrayOf(1,2,3,4,0,6,7,8,9,5),
        intArrayOf(2,3,4,0,1,7,8,9,5,6), intArrayOf(3,4,0,1,2,8,9,5,6,7),
        intArrayOf(4,0,1,2,3,9,5,6,7,8), intArrayOf(5,9,8,7,6,0,4,3,2,1),
        intArrayOf(6,5,9,8,7,1,0,4,3,2), intArrayOf(7,6,5,9,8,2,1,0,4,3),
        intArrayOf(8,7,6,5,9,3,2,1,0,4), intArrayOf(9,8,7,6,5,4,3,2,1,0),
    )
    private val VERHOEFF_P = arrayOf(
        intArrayOf(0,1,2,3,4,5,6,7,8,9), intArrayOf(1,5,7,6,2,8,3,0,9,4),
        intArrayOf(5,8,0,3,7,9,6,1,4,2), intArrayOf(8,9,1,6,0,4,3,5,2,7),
        intArrayOf(9,4,5,3,1,2,6,8,7,0), intArrayOf(4,2,8,6,5,7,3,9,0,1),
        intArrayOf(2,7,9,3,8,0,6,4,1,5), intArrayOf(7,0,4,6,9,1,3,2,5,8),
    )

    private fun verhoeffCheck(number: String): Boolean {
        if (number.length != 12 || !number.all { it.isDigit() }) return false
        var c = 0
        val digits = number.reversed().map { it - '0' }
        for (i in digits.indices) {
            c = VERHOEFF_D[c][VERHOEFF_P[i % 8][digits[i]]]
        }
        return c == 0
    }

    private fun findBestAadhaarNumber(text: String): String? {
        val candidates = mutableListOf<String>()
        var match = AADHAAR_PATTERN.find(text)
        while (match != null) {
            val raw = match.groupValues[1].replace("\\s".toRegex(), "")
            if (raw.length == 12) {
                val before = if (match.range.first > 0) text[match.range.first - 1] else ' '
                val afterIdx = match.range.last + 1
                val after = if (afterIdx < text.length) text[afterIdx] else ' '
                if (!before.isDigit() && !after.isDigit()) {
                    candidates.add(raw)
                }
            }
            match = match.next()
        }
        if (candidates.isEmpty()) return null
        Log.d(TAG, "Aadhaar candidates: $candidates, Verhoeff: ${candidates.map { verhoeffCheck(it) }}")
        return candidates.firstOrNull { verhoeffCheck(it) } ?: candidates.last()
    }

    /** Calculate confidence based on fields found, MRZ lines, and document type detection */
    private fun calculateConfidence(
        fields: Map<String, String>,
        mrzLines: List<String>,
        docType: String?,
    ): Float {
        var score = 0f
        // Base score from field extraction
        score += (fields.size / 10f).coerceAtMost(1f) * 0.4f
        // Bonus for MRZ lines
        score += if (mrzLines.isNotEmpty()) 0.3f else 0f
        // Bonus for document type detection
        score += if (docType != null) 0.2f else 0f
        // Bonus for critical fields
        if (fields.containsKey("name")) score += 0.05f
        if (fields.containsKey("passport_number") || fields.containsKey("document_number")) score += 0.05f
        if (fields.containsKey("date_of_birth")) score += 0.05f
        if (fields.containsKey("date_of_expiry")) score += 0.05f
        return score.coerceIn(0f, 1f)
    }

    /** Detect document type from text patterns — uses a scoring system
     * so that a document with multiple signals wins over an ambiguous one. */
    private fun detectDocumentType(text: String): String? {
        val lower = text.lowercase()
        val scores = mutableMapOf<String, Int>()

        // --- Driving Licence signals (strong) ---
        if (lower.contains("driving licence") || lower.contains("driving license")) scores["DRIVING_LICENCE"] = (scores["DRIVING_LICENCE"] ?: 0) + 10
        if (lower.contains("motor vehicle")) scores["DRIVING_LICENCE"] = (scores["DRIVING_LICENCE"] ?: 0) + 8
        if (Regex("""\bRTO\b""", RegexOption.IGNORE_CASE).containsMatchIn(text)) scores["DRIVING_LICENCE"] = (scores["DRIVING_LICENCE"] ?: 0) + 8
        if (Regex("""\bRTA\b""", RegexOption.IGNORE_CASE).containsMatchIn(text)) scores["DRIVING_LICENCE"] = (scores["DRIVING_LICENCE"] ?: 0) + 8
        if (lower.contains("transport department") || lower.contains("transport authority")) scores["DRIVING_LICENCE"] = (scores["DRIVING_LICENCE"] ?: 0) + 8
        if (lower.contains("vehicle class") || lower.contains("vehicle classes")) scores["DRIVING_LICENCE"] = (scores["DRIVING_LICENCE"] ?: 0) + 7
        if (Regex("""\bLMV\b""").containsMatchIn(text)) scores["DRIVING_LICENCE"] = (scores["DRIVING_LICENCE"] ?: 0) + 6
        if (Regex("""\bMCWG\b""").containsMatchIn(text)) scores["DRIVING_LICENCE"] = (scores["DRIVING_LICENCE"] ?: 0) + 6
        if (lower.contains("licencing authority") || lower.contains("licensing authority")) scores["DRIVING_LICENCE"] = (scores["DRIVING_LICENCE"] ?: 0) + 7
        if (lower.contains("blood group")) scores["DRIVING_LICENCE"] = (scores["DRIVING_LICENCE"] ?: 0) + 5
        if (lower.contains("सारथी") || lower.contains("अनुज्ञापत्र")) scores["DRIVING_LICENCE"] = (scores["DRIVING_LICENCE"] ?: 0) + 8
        if (DL_NUMBER_PATTERN.containsMatchIn(text)) scores["DRIVING_LICENCE"] = (scores["DRIVING_LICENCE"] ?: 0) + 6
        if (lower.contains("rsta") || lower.contains("road safety")) scores["DRIVING_LICENCE"] = (scores["DRIVING_LICENCE"] ?: 0) + 7
        // "transport" alone (without "department") is weaker — could appear in visa text
        if (lower.contains("transport") && !lower.contains("visa") && !lower.contains("passport")) scores["DRIVING_LICENCE"] = (scores["DRIVING_LICENCE"] ?: 0) + 3

        // --- National ID / Aadhaar signals ---
        if (lower.contains("aadhaar") || lower.contains("aadhar") || lower.contains("आधार")) scores["NATIONAL_ID"] = (scores["NATIONAL_ID"] ?: 0) + 10
        if (lower.contains("unique identification")) scores["NATIONAL_ID"] = (scores["NATIONAL_ID"] ?: 0) + 10
        if (lower.contains("uidai")) scores["NATIONAL_ID"] = (scores["NATIONAL_ID"] ?: 0) + 10
        if (lower.contains("enrol") && lower.contains("no")) scores["NATIONAL_ID"] = (scores["NATIONAL_ID"] ?: 0) + 5
        if (lower.contains("citizen identity") || lower.contains("cid")) scores["NATIONAL_ID"] = (scores["NATIONAL_ID"] ?: 0) + 7
        if (lower.contains("bhutan") && lower.contains("identity")) scores["NATIONAL_ID"] = (scores["NATIONAL_ID"] ?: 0) + 8
        if (lower.contains("identity card") || lower.contains("id card")) scores["NATIONAL_ID"] = (scores["NATIONAL_ID"] ?: 0) + 4

        // --- PAN Card signals ---
        if (PAN_PATTERN.find(text) != null) scores["PAN_CARD"] = (scores["PAN_CARD"] ?: 0) + 6
        if (lower.contains("permanent account number")) scores["PAN_CARD"] = (scores["PAN_CARD"] ?: 0) + 10
        if (lower.contains("income tax")) scores["PAN_CARD"] = (scores["PAN_CARD"] ?: 0) + 8
        if (lower.contains("pan card")) scores["PAN_CARD"] = (scores["PAN_CARD"] ?: 0) + 10

        // --- Voter ID signals ---
        if (lower.contains("voter") || lower.contains("epic")) scores["VOTER_ID"] = (scores["VOTER_ID"] ?: 0) + 8
        if (lower.contains("electoral") || lower.contains("election commission")) scores["VOTER_ID"] = (scores["VOTER_ID"] ?: 0) + 9
        if (lower.contains("निर्वाचन")) scores["VOTER_ID"] = (scores["VOTER_ID"] ?: 0) + 9

        // --- Passport signals ---
        if (lower.contains("passport")) scores["PASSPORT"] = (scores["PASSPORT"] ?: 0) + 8
        if (lower.contains("पासपोर्ट") || lower.contains("राहदानी")) scores["PASSPORT"] = (scores["PASSPORT"] ?: 0) + 9
        if (lower.contains("republic of india") && lower.contains("type") && lower.contains("country code")) scores["PASSPORT"] = (scores["PASSPORT"] ?: 0) + 8
        if (Regex("""P<[A-Z]{3}""").containsMatchIn(text)) scores["PASSPORT"] = (scores["PASSPORT"] ?: 0) + 10

        // --- Visa signals ---
        if (lower.contains("visa") && !lower.contains("driving")) scores["VISA"] = (scores["VISA"] ?: 0) + 7
        if (lower.contains("e-visa") || lower.contains("evisa")) scores["VISA"] = (scores["VISA"] ?: 0) + 10
        if (lower.contains("electronic travel authorization")) scores["VISA"] = (scores["VISA"] ?: 0) + 10
        if (lower.contains("tourist visa")) scores["VISA"] = (scores["VISA"] ?: 0) + 10
        if (lower.contains("visa no") || lower.contains("visa type") || lower.contains("eta number")) scores["VISA"] = (scores["VISA"] ?: 0) + 7
        if (lower.contains("bureau of immigration")) scores["VISA"] = (scores["VISA"] ?: 0) + 8
        if (lower.contains("वीसा") || lower.contains("वीजा")) scores["VISA"] = (scores["VISA"] ?: 0) + 8

        // --- Permit signals ---
        if (lower.contains("permit") && !lower.contains("driving")) scores["PERMIT"] = (scores["PERMIT"] ?: 0) + 6
        if (lower.contains("अनुमति")) scores["PERMIT"] = (scores["PERMIT"] ?: 0) + 8
        if (lower.contains("inner line permit") || lower.contains("ilp")) scores["PERMIT"] = (scores["PERMIT"] ?: 0) + 10

        // --- Nepal citizenship ---
        if (lower.contains("नागरिकता")) scores["CITIZENSHIP_CERTIFICATE"] = (scores["CITIZENSHIP_CERTIFICATE"] ?: 0) + 10
        if (lower.contains("citizenship certificate")) scores["CITIZENSHIP_CERTIFICATE"] = (scores["CITIZENSHIP_CERTIFICATE"] ?: 0) + 10
        if (lower.contains("nepal") && lower.contains("citizenship")) scores["CITIZENSHIP_CERTIFICATE"] = (scores["CITIZENSHIP_CERTIFICATE"] ?: 0) + 9

        // Pick the highest-scoring type; require a minimum threshold
        val best = scores.maxByOrNull { it.value }
        Log.d(TAG, "Document type scores: $scores → ${best?.key}")
        return if (best != null && best.value >= 6) best.key else null
    }

    /** Extract Indian document numbers using regex patterns */
    private fun extractIndianDocumentNumbers(text: String): Map<String, String> {
        val result = mutableMapOf<String, String>()

        findBestAadhaarNumber(text)?.let { aadhaar ->
            result["document_number"] = aadhaar
            result["aadhaar_number"] = aadhaar
        }

        PAN_PATTERN.find(text)?.let { match ->
            result["document_number"] = match.groupValues[1]
            result["pan_number"] = match.groupValues[1]
        }

        INDIAN_PASSPORT_PATTERN.find(text)?.let { match ->
            result["passport_number"] = match.groupValues[1]
            result["document_number"] = match.groupValues[1]
        }

        VOTER_ID_PATTERN.find(text)?.let { match ->
            result["document_number"] = match.groupValues[1]
            result["voter_id"] = match.groupValues[1]
        }

        // DL number extraction
        DL_NUMBER_PATTERN.find(text)?.let { match ->
            val dlNum = match.groupValues[1].replace(Regex("[\\s\\-]"), "")
            if (!result.containsKey("document_number")) result["document_number"] = dlNum
            result["dl_number"] = dlNum
        }

        // Document-type-specific field extraction
        if (result.containsKey("aadhaar_number")) {
            extractAadhaarFields(text, result)
        }
        if (result.containsKey("pan_number")) {
            extractPanFields(text, result)
        }
        if (result.containsKey("dl_number") || isDrivingLicence(text)) {
            extractDrivingLicenceFields(text, result)
        }
        if (isPassport(text)) {
            extractPassportFields(text, result)
        }
        if (isVisa(text)) {
            extractVisaFields(text, result)
        }
        extractCommonFields(text, result)

        return result
    }

    private fun isDrivingLicence(text: String): Boolean {
        val lower = text.lowercase()
        return lower.contains("driving licence") || lower.contains("driving license")
            || lower.contains("motor vehicle") || lower.contains("transport department")
            || Regex("""\bRTO\b|\bRTA\b""", RegexOption.IGNORE_CASE).containsMatchIn(text)
    }

    private fun extractDrivingLicenceFields(text: String, result: MutableMap<String, String>) {
        val lines = text.lines().map { it.trim() }.filter { it.isNotEmpty() }

        // DOB — look for "DOB" label or date_of_birth pattern
        if (!result.containsKey("date_of_birth")) {
            val dobPattern = Regex("""(?:DOB|D\.?O\.?B\.?|Date\s*of\s*Birth|जन्म\s*(?:तिथि|दिनांक))\s*[:/]?\s*(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4})""", RegexOption.IGNORE_CASE)
            dobPattern.find(text)?.let { match ->
                normalizeDate(match.groupValues[1])?.let { result["date_of_birth"] = it }
            }
        }

        // Blood group
        if (!result.containsKey("blood_group")) {
            val bgPattern = Regex("""(?:Blood\s*Group|रक्त\s*समूह)\s*[:/]?\s*([ABO]{1,2}[\s]?[+-]?\s*(?:Positive|Negative|positive|negative)?)\b""", RegexOption.IGNORE_CASE)
            bgPattern.find(text)?.let { result["blood_group"] = it.groupValues[1].trim() }
        }

        // Vehicle classes — LMV, MCWG, MCWOG, HMV, etc.
        if (!result.containsKey("vehicle_classes")) {
            val vcPattern = Regex("""\b(LMV|MCWG|MCWOG|HMV|HGV|LTV|MGV|HPMV|TRANS)\b""")
            val classes = vcPattern.findAll(text).map { it.value }.toSet()
            if (classes.isNotEmpty()) result["vehicle_classes"] = classes.joinToString(", ")
        }

        // Validity / Date of Expiry
        if (!result.containsKey("date_of_expiry")) {
            val validPattern = Regex("""(?:Valid|Validity|Date\s*of\s*Expiry|NT|Non[\s\-]?Transport)\s*[:/]?\s*(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4})""", RegexOption.IGNORE_CASE)
            validPattern.find(text)?.let { match ->
                normalizeDate(match.groupValues[1])?.let { result["date_of_expiry"] = it }
            }
        }

        // Issued date
        if (!result.containsKey("date_of_issue")) {
            val issuePattern = Regex("""(?:Issued?\s*(?:On|Date)?|Date\s*of\s*Issue)\s*[:/]?\s*(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4})""", RegexOption.IGNORE_CASE)
            issuePattern.find(text)?.let { match ->
                normalizeDate(match.groupValues[1])?.let { result["date_of_issue"] = it }
            }
        }

        // Name — person name on DL is usually after the DL number line
        if (!result.containsKey("name")) {
            for (line in lines) {
                if (isLikelyPersonName(line)) {
                    val lower = line.lowercase()
                    if (!lower.contains("transport") && !lower.contains("motor") &&
                        !lower.contains("union") && !lower.contains("state") &&
                        !lower.contains("kingdom") && !lower.contains("bhutan") &&
                        !lower.contains("driving")) {
                        result["name"] = line.trim()
                        break
                    }
                }
            }
        }

        // CID for Bhutan DL
        if (!result.containsKey("document_number")) {
            val cidPattern = Regex("""CID\s*[:/]?\s*(\d{11})""", RegexOption.IGNORE_CASE)
            cidPattern.find(text)?.let { result["document_number"] = it.groupValues[1] }
        }

        // Nationality inference
        if (!result.containsKey("nationality")) {
            val lower = text.lowercase()
            result["nationality"] = when {
                lower.contains("bhutan") || lower.contains("kingdom of bhutan") -> "BHUTANESE"
                lower.contains("nepal") -> "NEPALI"
                else -> "INDIAN"
            }
        }
    }

    private fun isPassport(text: String): Boolean {
        val lower = text.lowercase()
        return lower.contains("passport") || lower.contains("पासपोर्ट")
            || lower.contains("राहदानी") || Regex("""P<[A-Z]{3}""").containsMatchIn(text)
    }

    private fun isVisa(text: String): Boolean {
        val lower = text.lowercase()
        return (lower.contains("visa") && !lower.contains("driving"))
            || lower.contains("e-visa") || lower.contains("tourist visa")
            || lower.contains("electronic travel authorization")
            || lower.contains("bureau of immigration")
    }

    private val VISA_NUMBER_PATTERN = Regex("""(?:Visa\s*(?:No\.?|Number)\s*[:/]?\s*)([A-Z0-9]{6,20})""", RegexOption.IGNORE_CASE)
    private val ETA_NUMBER_PATTERN = Regex("""(?:ETA\s*(?:No\.?|Number)\s*[:/]?\s*)([A-Z0-9]{6,20})""", RegexOption.IGNORE_CASE)
    private val BHUTAN_CID_PATTERN = Regex("""(?:CID\s*(?:No\.?|Number)?\s*[:/]?\s*)(\d{11})""", RegexOption.IGNORE_CASE)
    private val NEPAL_CITIZENSHIP_PATTERN = Regex("""(?:(?:Citizenship|Na\.?\s*Pra\.?)\s*(?:No\.?|Number)?\s*[:/]?\s*)(\d{2}[-/]\d{2}[-/]\d{2}[-/]\d{4,6})""", RegexOption.IGNORE_CASE)

    private fun extractPassportFields(text: String, result: MutableMap<String, String>) {
        val lines = text.lines().map { it.trim() }.filter { it.isNotEmpty() }

        // Passport number from printed text (not just MRZ)
        if (!result.containsKey("passport_number")) {
            val ppPatterns = listOf(
                Regex("""(?:Passport\s*(?:No\.?|Number)\s*[:/]?\s*)([A-Z]\d{6,8})""", RegexOption.IGNORE_CASE),
                Regex("""(?:No\.?\s*du\s*passeport|राहदानी\s*नं\.?\s*[:/]?\s*)([A-Z]\d{6,8})""", RegexOption.IGNORE_CASE),
                Regex("""\b([A-Z]\d{7})\b"""),
            )
            for (p in ppPatterns) {
                p.find(text)?.let {
                    result["passport_number"] = it.groupValues[1]
                    if (!result.containsKey("document_number")) result["document_number"] = it.groupValues[1]
                    return@let
                }
                if (result.containsKey("passport_number")) break
            }
        }

        // Place of birth
        if (!result.containsKey("place_of_birth")) {
            val pobPatterns = listOf(
                Regex("""(?:Place\s*of\s*Birth|POB|जन्म\s*स्थान)\s*[:/]?\s*([A-Za-z\s,]+)""", RegexOption.IGNORE_CASE),
            )
            for (p in pobPatterns) {
                p.find(text)?.let {
                    val place = it.groupValues[1].trim().take(50)
                    if (place.length >= 2) result["place_of_birth"] = place
                }
                if (result.containsKey("place_of_birth")) break
            }
        }

        // Place of issue
        if (!result.containsKey("place_of_issue")) {
            val poiPatterns = listOf(
                Regex("""(?:Place\s*of\s*Issue|जारी\s*स्थान)\s*[:/]?\s*([A-Za-z\s,]+)""", RegexOption.IGNORE_CASE),
            )
            for (p in poiPatterns) {
                p.find(text)?.let {
                    val place = it.groupValues[1].trim().take(50)
                    if (place.length >= 2) result["place_of_issue"] = place
                }
                if (result.containsKey("place_of_issue")) break
            }
        }

        // Issuing authority
        if (!result.containsKey("issuing_authority")) {
            val authPatterns = listOf(
                Regex("""(?:(?:Issuing\s*)?Authority|Issued\s*by)\s*[:/]?\s*(.+)""", RegexOption.IGNORE_CASE),
            )
            for (p in authPatterns) {
                p.find(text)?.let {
                    val auth = it.groupValues[1].trim().take(60)
                    if (auth.length >= 3 && !auth.lowercase().contains("signature")) result["issuing_authority"] = auth
                }
                if (result.containsKey("issuing_authority")) break
            }
        }

        // Bhutan passport: CID number
        if (!result.containsKey("cid_number")) {
            BHUTAN_CID_PATTERN.find(text)?.let { result["cid_number"] = it.groupValues[1] }
        }

        // Nepal passport: citizenship reference number
        if (!result.containsKey("citizenship_number")) {
            NEPAL_CITIZENSHIP_PATTERN.find(text)?.let { result["citizenship_number"] = it.groupValues[1] }
        }

        // Nationality inference from passport text
        if (!result.containsKey("nationality")) {
            val lower = text.lowercase()
            result["nationality"] = when {
                lower.contains("kingdom of bhutan") || lower.contains("bhutan") -> "BHUTANESE"
                lower.contains("government of nepal") || lower.contains("nepal") || lower.contains("नेपाल") -> "NEPALI"
                lower.contains("republic of india") || lower.contains("india") || lower.contains("भारत") -> "INDIAN"
                lower.contains("bangladesh") -> "BANGLADESHI"
                else -> "UNKNOWN"
            }
        }
    }

    private fun extractVisaFields(text: String, result: MutableMap<String, String>) {
        // Visa number
        if (!result.containsKey("visa_number")) {
            VISA_NUMBER_PATTERN.find(text)?.let {
                result["visa_number"] = it.groupValues[1]
                if (!result.containsKey("document_number")) result["document_number"] = it.groupValues[1]
            }
        }
        if (!result.containsKey("visa_number")) {
            ETA_NUMBER_PATTERN.find(text)?.let {
                result["visa_number"] = it.groupValues[1]
                if (!result.containsKey("document_number")) result["document_number"] = it.groupValues[1]
            }
        }

        // Visa type
        if (!result.containsKey("visa_type")) {
            val typePatterns = listOf(
                Regex("""(?:Visa\s*(?:Type|Category)|Type\s*of\s*Visa)\s*[:/]?\s*([A-Za-z\s\-]+)""", RegexOption.IGNORE_CASE),
                Regex("""(?:Category)\s*[:/]?\s*(Tourist|Business|Employment|Student|Transit|Diplomatic|Official|Medical|Conference|Entry)""", RegexOption.IGNORE_CASE),
            )
            for (p in typePatterns) {
                p.find(text)?.let {
                    result["visa_type"] = it.groupValues[1].trim().take(30)
                }
                if (result.containsKey("visa_type")) break
            }
        }

        // Number of entries
        if (!result.containsKey("entries")) {
            val entryPattern = Regex("""(?:(?:No\.?\s*of\s*)?Entries|Entry)\s*[:/]?\s*(Single|Multiple|Double|\d+)""", RegexOption.IGNORE_CASE)
            entryPattern.find(text)?.let { result["entries"] = it.groupValues[1].trim() }
        }

        // Port of entry / arrival
        if (!result.containsKey("port_of_entry")) {
            val portPattern = Regex("""(?:Port\s*of\s*(?:Entry|Arrival)|POE)\s*[:/]?\s*([A-Za-z\s]+)""", RegexOption.IGNORE_CASE)
            portPattern.find(text)?.let {
                val port = it.groupValues[1].trim().take(40)
                if (port.length >= 2) result["port_of_entry"] = port
            }
        }

        // Passport number referenced in visa
        if (!result.containsKey("passport_number")) {
            val ppRef = Regex("""(?:Passport\s*(?:No\.?|Number)\s*[:/]?\s*)([A-Z]\d{6,8})""", RegexOption.IGNORE_CASE)
            ppRef.find(text)?.let { result["passport_number"] = it.groupValues[1] }
        }

        // Validity dates
        if (!result.containsKey("date_of_issue")) {
            val issueP = Regex("""(?:(?:Date\s*of\s*)?Issue(?:d)?|Valid\s*From|From)\s*[:/]?\s*(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4})""", RegexOption.IGNORE_CASE)
            issueP.find(text)?.let { normalizeDate(it.groupValues[1])?.let { d -> result["date_of_issue"] = d } }
        }
        if (!result.containsKey("date_of_expiry")) {
            val expiryP = Regex("""(?:(?:Date\s*of\s*)?Expiry|Valid\s*(?:Until|Till)|Until|To)\s*[:/]?\s*(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4})""", RegexOption.IGNORE_CASE)
            expiryP.find(text)?.let { normalizeDate(it.groupValues[1])?.let { d -> result["date_of_expiry"] = d } }
        }

        // Nationality inference from visa
        if (!result.containsKey("nationality")) {
            val lower = text.lowercase()
            result["nationality"] = when {
                lower.contains("nepal") || lower.contains("nepali") || lower.contains("नेपाल") -> "NEPALI"
                lower.contains("bhutan") || lower.contains("bhutanese") -> "BHUTANESE"
                lower.contains("india") || lower.contains("indian") || lower.contains("भारत") -> "INDIAN"
                lower.contains("bangladesh") || lower.contains("bangladeshi") -> "BANGLADESHI"
                else -> "UNKNOWN"
            }
        }
    }

    private fun extractPanFields(text: String, result: MutableMap<String, String>) {
        val lines = text.lines().map { it.trim() }.filter { it.isNotEmpty() }
        // PAN card name is usually the line right after "Name" or the
        // prominent printed name (all caps on the card)
        if (!result.containsKey("name")) {
            for (line in lines) {
                if (line.matches(Regex("^[A-Z ]{4,40}$")) &&
                    !line.contains("INCOME", true) &&
                    !line.contains("TAX", true) &&
                    !line.contains("GOVT", true) &&
                    !line.contains("INDIA", true) &&
                    !line.contains("PERMANENT", true) &&
                    !line.contains("ACCOUNT", true)) {
                    result["name"] = line.trim()
                    break
                }
            }
        }
        if (!result.containsKey("nationality")) {
            result["nationality"] = "INDIAN"
        }
    }

    private fun extractCommonFields(text: String, result: MutableMap<String, String>) {
        // Gender from standalone "Male"/"Female" or Hindi equivalents
        if (!result.containsKey("gender")) {
            AADHAAR_GENDER_PATTERN.find(text)?.let { match ->
                val g = match.value.lowercase()
                result["gender"] = when {
                    g == "male" || g == "पुरुष" -> "M"
                    g == "female" || g == "महिला" -> "F"
                    else -> match.value
                }
            }
        }
        // DOB from common patterns across document types
        if (!result.containsKey("date_of_birth")) {
            AADHAAR_DOB_PATTERN.find(text)?.let { match ->
                normalizeDate(match.groupValues[1])?.let { result["date_of_birth"] = it }
            }
        }
    }

    private val AADHAAR_DOB_PATTERN = Regex("""(?:DOB|D\.O\.B\.?|जन्म\s*तिथि)\s*[:/]?\s*(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4})""", RegexOption.IGNORE_CASE)
    private val AADHAAR_GENDER_PATTERN = Regex("""(?:Male|Female|पुरुष|महिला|MALE|FEMALE)""")
    private val AADHAAR_NAME_EXCLUDE = setOf(
        "government", "india", "unique", "identification", "authority",
        "aadhaar", "aadhar", "enrolment", "enrollment", "resident",
        "address", "proof", "identity", "download", "uidai",
        "income", "tax", "department", "republic", "ministry",
        "male", "female", "birth", "validity", "issue", "help",
        "driving", "licence", "license", "motor", "vehicle", "transport",
        "union", "state", "kingdom", "bhutan", "nepal", "passport",
        "visa", "tourist", "immigration", "bureau", "electronic",
        "blood", "group", "class", "offence", "signature",
    )

    private fun isLikelyPersonName(line: String): Boolean {
        val trimmed = line.trim()
        if (trimmed.length < 3 || trimmed.length > 60) return false
        val words = trimmed.split(Regex("\\s+"))
        if (words.isEmpty()) return false
        if (!words.all { w -> w.length >= 2 && w.all { it.isLetter() } }) return false
        val allCaps = words.all { w -> w.all { it.isUpperCase() } }
        val titleCase = words.all { w -> w[0].isUpperCase() && w.drop(1).all { it.isLowerCase() } }
        if (!allCaps && !titleCase) return false
        val lower = trimmed.lowercase()
        return AADHAAR_NAME_EXCLUDE.none { lower.contains(it) }
    }

    private fun extractAadhaarFields(text: String, result: MutableMap<String, String>) {
        val lines = text.lines().map { it.trim() }.filter { it.isNotEmpty() }

        // DOB from "जन्म तिथि / DOB : 31/10/2004" or similar
        if (!result.containsKey("date_of_birth")) {
            AADHAAR_DOB_PATTERN.find(text)?.let { match ->
                normalizeDate(match.groupValues[1])?.let { result["date_of_birth"] = it }
            }
        }

        // Gender from "महिला / Female" or "Male" etc.
        if (!result.containsKey("gender")) {
            AADHAAR_GENDER_PATTERN.find(text)?.let { match ->
                val g = match.value.lowercase()
                result["gender"] = when {
                    g == "male" || g == "पुरुष" -> "M"
                    g == "female" || g == "महिला" -> "F"
                    else -> match.value
                }
            }
        }

        if (!result.containsKey("name")) {
            for (line in lines) {
                if (isLikelyPersonName(line)) {
                    result["name"] = line.trim()
                    break
                }
            }
        }

        // Aadhaar is Indian, so nationality is always INDIAN
        if (!result.containsKey("nationality")) {
            result["nationality"] = "INDIAN"
        }
    }

    private fun mrzFieldConsistencyChecks(mrzFields: Map<String, String>, printedFields: Map<String, String>): List<VerificationCheck> {
        val checks = mutableListOf<VerificationCheck>()
        fun compare(fieldKey: String, label: String) {
            val mrzVal = mrzFields[fieldKey]?.uppercase()?.trim()
            val printedVal = printedFields[fieldKey]?.uppercase()?.trim()
            if (mrzVal == null || printedVal == null) return
            if (mrzVal == printedVal) {
                checks.add(VerificationCheck("MRZ ↔ printed $label", CheckStatus.PASS, "Match: $printedVal"))
            } else {
                val mrzNorm = mrzVal.replace(Regex("[\\s\\-/.]"), "")
                val printedNorm = printedVal.replace(Regex("[\\s\\-/.]"), "")
                if (mrzNorm == printedNorm) {
                    checks.add(VerificationCheck("MRZ ↔ printed $label", CheckStatus.PASS, "Match after normalization"))
                } else {
                    checks.add(VerificationCheck("MRZ ↔ printed $label", CheckStatus.WARNING,
                        "MRZ reads \"$mrzVal\" but printed text reads \"$printedVal\""))
                }
            }
        }
        compare("name", "name")
        compare("date_of_birth", "date of birth")
        compare("date_of_expiry", "date of expiry")
        compare("nationality", "nationality")
        compare("gender", "gender")
        return checks
    }

    private fun checkExpiry(dateStr: String): VerificationCheck? {
        return try {
            val parts = dateStr.split("/")
            if (parts.size != 3) return null
            val day = parts[0].toInt()
            val month = parts[1].toInt()
            val year = parts[2].toInt()
            val cal = java.util.Calendar.getInstance()
            val expiryCalendar = java.util.Calendar.getInstance().apply {
                set(year, month - 1, day)
            }
            if (expiryCalendar.before(cal)) {
                VerificationCheck("Document expiry", CheckStatus.FAIL, "Document expired on $dateStr")
            } else {
                val daysLeft = ((expiryCalendar.timeInMillis - cal.timeInMillis) / (1000 * 60 * 60 * 24)).toInt()
                if (daysLeft < 90) {
                    VerificationCheck("Document expiry", CheckStatus.WARNING, "Expires in $daysLeft days ($dateStr)")
                } else {
                    VerificationCheck("Document expiry", CheckStatus.PASS, "Valid until $dateStr")
                }
            }
        } catch (_: Exception) { null }
    }

    /** Best-effort line-based heuristic: for each target field, scan
     * recognized lines for a known label keyword, then take either the
     * remainder of that same line (after a separator) or the next
     * non-empty line as the value. Dates are normalized to DD/MM/YYYY
     * (the format the backend's cross-check regex requires); anything
     * that doesn't parse as a date is left out of the map rather than
     * sent in a format the server would reject as malformed. */
    private fun mapFields(rawText: String): Map<String, String> {
        val lines = rawText.lines().map { it.trim() }.filter { it.isNotEmpty() }
        val result = LinkedHashMap<String, String>()

        for ((field, labels) in LABELS) {
            for ((index, line) in lines.withIndex()) {
                val lower = line.lowercase()
                val matchedLabel = labels.firstOrNull { lower.contains(it) } ?: continue

                // Find the label position case-insensitively, then take text after it
                val labelIdx = lower.indexOf(matchedLabel)
                val textAfterLabel = if (labelIdx >= 0) {
                    line.substring(labelIdx + matchedLabel.length)
                } else ""
                val afterSeparator = textAfterLabel
                    .trimStart()
                    .removePrefix("/").removePrefix(":").removePrefix("-").removePrefix("=")
                    .trim()
                val candidate = afterSeparator.ifBlank {
                    lines.getOrNull(index + 1)?.takeIf { !containsAnyLabel(it) }.orEmpty()
                }
                if (candidate.isBlank()) continue

                if (field == "date_of_birth" || field == "date_of_expiry" || field == "date_of_issue") {
                    val normalized = normalizeDate(candidate) ?: continue
                    result[field] = normalized
                } else {
                    result[field] = candidate.trim()
                }
                break
            }
        }

        extractFromPatterns(rawText, result)
        return result
    }

    private fun joinedLabelledName(text: String): String? {
        fun value(labels: String): String? = text.lines().firstNotNullOfOrNull { line ->
            Regex("""(?i)^\s*(?:$labels)\s*[:\-]\s*(.+?)\s*$""").find(line)?.groupValues?.get(1)
        }
        val surname = value("surname|last name|family name")
        val given = value("given names?|first names?")
        if (surname.isNullOrBlank() || given.isNullOrBlank()) return null
        return "$given $surname".uppercase().replace(Regex("\\s+"), " ")
    }

    private data class MrzParse(val lines: List<String>, val fields: Map<String, String>, val checkDigits: MrzCheckDigitResult? = null)

    // ICAO 3-letter codes → the demonym the backend's cross-check and
    // registries use (see app/services/validation/cross_check.py). Unknown
    // codes pass through unchanged rather than being guessed at.
    private val NATIONALITY_BY_ICAO = mapOf(
        "IND" to "INDIAN", "NPL" to "NEPALI", "BTN" to "BHUTANESE", "BGD" to "BANGLADESHI",
        "PAK" to "PAKISTANI", "LKA" to "SRI LANKAN", "USA" to "AMERICAN", "GBR" to "BRITISH",
    )

    /** OCR reads the MRZ's filler `<` as everything from `K` to `(` and
     * inserts spaces; anything outside the MRZ alphabet is treated as a
     * filler. Only applied to candidate lines, never to normal text. */
    private fun normalizeMrzLine(raw: String): String =
        raw.uppercase().filterNot { it.isWhitespace() }
            .map { c -> if (c in 'A'..'Z' || c in '0'..'9' || c == '<') c else '<' }
            .joinToString("")

    /** In numeric MRZ fields a letter can only be a misread digit. */
    private fun fixDigits(s: String): String = s.map { c ->
        when (c) { 'O', 'Q', 'D' -> '0'; 'I', 'L' -> '1'; 'B' -> '8'; 'S' -> '5'; 'Z' -> '2'; else -> c }
    }.joinToString("")

    private fun mrzDate(yymmdd: String, isBirth: Boolean): String? {
        if (yymmdd.length != 6 || !yymmdd.all { it.isDigit() }) return null
        val yy = yymmdd.substring(0, 2).toInt()
        val mm = yymmdd.substring(2, 4).toInt()
        val dd = yymmdd.substring(4, 6).toInt()
        if (mm !in 1..12 || dd !in 1..31) return null
        val currentYY = java.util.Calendar.getInstance().get(java.util.Calendar.YEAR) % 100
        // A birth year ahead of "now" is last century; passports expire in this one.
        val year = if (isBirth && yy > currentYY) 1900 + yy else 2000 + yy
        return "%02d/%02d/%04d".format(dd, mm, year)
    }

    // ICAO 9303 check-digit weights cycle 7-3-1
    private val MRZ_WEIGHTS = intArrayOf(7, 3, 1)
    private fun mrzCharValue(c: Char): Int = when {
        c == '<' -> 0
        c in '0'..'9' -> c - '0'
        c in 'A'..'Z' -> c - 'A' + 10
        else -> 0
    }

    private fun mrzCheckDigit(field: String): Int {
        var sum = 0
        for (i in field.indices) {
            sum += mrzCharValue(field[i]) * MRZ_WEIGHTS[i % 3]
        }
        return sum % 10
    }

    private fun validateMrzCheckDigits(l2: String): MrzCheckDigitResult {
        val checks = mutableListOf<VerificationCheck>()
        // TD3 line 2 layout (ICAO 9303 Part 4):
        // [0-8]   passport number
        // [9]     passport number check digit
        // [10-12] nationality
        // [13-18] date of birth YYMMDD
        // [19]    DOB check digit
        // [20]    sex
        // [21-26] date of expiry YYMMDD
        // [27]    expiry check digit
        // [28-41] personal number / optional data
        // [42]    personal number check digit
        // [43]    composite check digit over positions 0-9, 13-19, 21-42

        fun fieldCheck(name: String, field: String, expectedDigit: Char): CheckStatus {
            val computed = mrzCheckDigit(field)
            val expected = if (expectedDigit.isDigit()) expectedDigit - '0' else -1
            return if (expected == computed) {
                checks.add(VerificationCheck(name, CheckStatus.PASS, "Check digit $expected verified (field: ${field.take(9)})"))
                CheckStatus.PASS
            } else {
                checks.add(VerificationCheck(name, CheckStatus.FAIL, "Expected check digit $computed but MRZ has $expectedDigit"))
                CheckStatus.FAIL
            }
        }

        val passportNum = if (l2.length >= 10) fieldCheck("MRZ passport number checksum", l2.substring(0, 9), l2[9])
            else CheckStatus.NOT_AVAILABLE.also { checks.add(VerificationCheck("MRZ passport number checksum", it, "MRZ line too short")) }

        val dob = if (l2.length >= 20) fieldCheck("MRZ date of birth checksum", l2.substring(13, 19), l2[19])
            else CheckStatus.NOT_AVAILABLE.also { checks.add(VerificationCheck("MRZ date of birth checksum", it, "MRZ line too short")) }

        val expiry = if (l2.length >= 28) fieldCheck("MRZ date of expiry checksum", l2.substring(21, 27), l2[27])
            else CheckStatus.NOT_AVAILABLE.also { checks.add(VerificationCheck("MRZ date of expiry checksum", it, "MRZ line too short")) }

        val personal = if (l2.length >= 43) fieldCheck("MRZ personal number checksum", l2.substring(28, 42), l2[42])
            else CheckStatus.NOT_AVAILABLE.also { checks.add(VerificationCheck("MRZ personal number checksum", it, "MRZ line too short")) }

        val composite = if (l2.length >= 44) {
            val compositeField = l2.substring(0, 10) + l2.substring(13, 20) + l2.substring(21, 43)
            fieldCheck("MRZ composite checksum", compositeField, l2[43])
        } else CheckStatus.NOT_AVAILABLE.also { checks.add(VerificationCheck("MRZ composite checksum", it, "MRZ line too short")) }

        return MrzCheckDigitResult(passportNum, dob, expiry, personal, composite, checks)
    }

    /** Finds a TD3 (passport / MRV-A visa, 2 × 44 chars) MRZ pair anywhere in
     * the recognized text and reads its fields. Check digits are *not*
     * enforced here — the backend runs the real ICAO 9303 checksums and
     * reports exactly which digit failed; this only extracts. */
    private fun parseTd3Mrz(text: String): MrzParse? {
        // Line 2 (numbers + check digits) is read reliably and is exactly 44
        // characters. Line 1 ends in a long run of `<` filler that OCR often
        // miscounts, so it's accepted at a near-44 length and refitted.
        val normalized = text.lines().map { normalizeMrzLine(it) }
        for (i in 0 until normalized.size - 1) {
            val rawL1 = normalized[i]
            val l2 = normalized[i + 1]
            // Every field this reads sits in the first 28 characters of line
            // 2, so a tail truncated by OCR still yields reliable fields.
            if (l2.length !in 28..50 || rawL1.length !in 36..50) continue
            val l1 = rawL1.padEnd(44, '<').take(44)
            if (l1[0] != 'P' && l1[0] != 'V') continue
            if (l1[1] != '<' && !l1[1].isLetter()) continue
            if (l2[20] != 'M' && l2[20] != 'F' && l2[20] != '<') continue
            val dob = mrzDate(fixDigits(l2.substring(13, 19)), isBirth = true)
            val exp = mrzDate(fixDigits(l2.substring(21, 27)), isBirth = false)
            if (dob == null && exp == null) continue

            val nameParts = l1.substring(5).split("<<")
            val surname = nameParts.firstOrNull().orEmpty().replace('<', ' ').trim()
            val given = nameParts.drop(1).joinToString(" ").replace('<', ' ').trim().replace(Regex("\\s+"), " ")
            val fields = LinkedHashMap<String, String>()
            listOf(given, surname).filter { it.isNotBlank() }.joinToString(" ").takeIf { it.isNotBlank() }
                ?.let { fields["name"] = it }
            l2.substring(0, 9).replace("<", "").takeIf { it.isNotBlank() }?.let { fields["passport_number"] = it }
            l2.substring(10, 13).takeIf { it.all { c -> c.isLetter() } }?.let { fields["nationality"] = NATIONALITY_BY_ICAO[it] ?: it }
            dob?.let { fields["date_of_birth"] = it }
            exp?.let { fields["date_of_expiry"] = it }
            when (l2[20]) { 'M' -> fields["gender"] = "M"; 'F' -> fields["gender"] = "F" }
            // MRZ *lines* are only reported when both were read at their full
            // 44 characters — a padded or truncated line would make the
            // backend's check-digit validation fail on OCR loss, not on the
            // document, and would be shown as if it were the real MRZ.
            val complete = rawL1.length == 44 && l2.length == 44
            val checkDigits = if (l2.length >= 44) validateMrzCheckDigits(l2) else null
            return MrzParse(if (complete) listOf(l1, l2) else emptyList(), fields, checkDigits)
        }
        return null
    }

    /** Extract fields using regex patterns */
    private fun extractFromPatterns(text: String, result: MutableMap<String, String>) {
        // Passport number patterns
        if (!result.containsKey("passport_number") && !result.containsKey("document_number")) {
            val passportPatterns = listOf(
                Regex("""(?i)passport\s*[:#]?\s*([A-Z0-9]{6,12})"""),
                Regex("""(?i)passport\s+no\.?\s*[:#]?\s*([A-Z0-9]{6,12})"""),
                Regex("""\b[A-Z]{1,2}[0-9]{6,8}\b"""), // Common passport format
            )
            for (pattern in passportPatterns) {
                val match = pattern.find(text)
                if (match != null && match.groupValues.size > 1) {
                    result["passport_number"] = match.groupValues[1]
                    break
                }
            }
        }

        // Nationality patterns
        if (!result.containsKey("nationality")) {
            val natPatterns = listOf(
                Regex("""(?i)nationality\s*[:#]?\s*([A-Z]{3}|[A-Za-z\s]+)"""),
                Regex("""(?i)citizenship\s*[:#]?\s*([A-Z]{3}|[A-Za-z\s]+)"""),
            )
            for (pattern in natPatterns) {
                val match = pattern.find(text)
                if (match != null && match.groupValues.size > 1) {
                    result["nationality"] = match.groupValues[1].trim().uppercase()
                    break
                }
            }
        }

        // Date patterns for any remaining dates
        val dateMatches = DATE_PATTERN.findAll(text).toList()
        if (dateMatches.size >= 2 && !result.containsKey("date_of_birth")) {
            // Assume first date is DOB, second is expiry (common in passports)
            val dobMatch = dateMatches[0]
            val (a, b, year) = dobMatch.destructured
            val (day, month) = if (a.toInt() > 31 && b.toInt() <= 31) b to a else a to b
            if (day.toInt() in 1..31 && month.toInt() in 1..12) {
                result["date_of_birth"] = "%02d/%02d/%s".format(day.toInt(), month.toInt(), year)
            }
        }
        if (dateMatches.size >= 2 && !result.containsKey("date_of_expiry")) {
            val expMatch = dateMatches[1]
            val (a, b, year) = expMatch.destructured
            val (day, month) = if (a.toInt() > 31 && b.toInt() <= 31) b to a else a to b
            if (day.toInt() in 1..31 && month.toInt() in 1..12) {
                result["date_of_expiry"] = "%02d/%02d/%s".format(day.toInt(), month.toInt(), year)
            }
        }
    }

    private fun afterLabel(line: String, label: String): String {
        val idx = line.lowercase().indexOf(label)
        return if (idx < 0) "" else line.substring(idx + label.length)
    }

    private fun containsAnyLabel(line: String): Boolean {
        val lower = line.lowercase()
        return LABELS.values.any { labels -> labels.any { lower.contains(it) } }
    }

    private fun normalizeDate(text: String): String? {
        val match = DATE_PATTERN.find(text) ?: return null
        val (a, b, year) = match.destructured
        // Heuristic only: if the first group can't be a day (>31) but the
        // second can, assume MM/DD input and swap — otherwise assume the
        // already-correct DD/MM order. Genuinely ambiguous without a
        // locale hint; documented as a best-effort guess.
        val (day, month) = if (a.toInt() > 31 && b.toInt() <= 31) b to a else a to b
        val dayInt = day.toInt()
        val monthInt = month.toInt()
        if (dayInt !in 1..31 || monthInt !in 1..12) return null
        return "%02d/%02d/%s".format(dayInt, monthInt, year)
    }
}
