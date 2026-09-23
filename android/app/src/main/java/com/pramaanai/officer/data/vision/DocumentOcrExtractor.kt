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
            val printedPpNum = get("passport_number")
            mrz?.let { putAll(it.fields) }
            // If MRZ and printed text passport numbers differ only in the first char
            // (common OCR-B misread like P↔R), prefer the printed text first letter
            // since printed text uses a more readable font.
            if (printedPpNum != null && mrz?.fields?.get("passport_number") != null) {
                val mrzPp = mrz.fields["passport_number"]!!
                if (printedPpNum.length == mrzPp.length && printedPpNum.substring(1) == mrzPp.substring(1) && printedPpNum[0] != mrzPp[0]) {
                    put("passport_number", printedPpNum)
                }
            }
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
        val hasDocNum = fields.keys.any { it in setOf("passport_number", "document_number", "aadhaar_number", "pan_number", "voter_id", "dl_number", "visa_number", "citizenship_number", "cid_number", "licence_number", "license_number", "permit_number") }
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
            // Bhutan passport specific
            "name of bearer", "bearer",
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
            // Bhutanese CID — Bhutan passports print "CITIZENSHIP ID NO"
            "cid no", "cid number", "citizen identity",
            "citizenship id no", "citizenship id", "citizenship id number",
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

    // Matches DD/MM/YYYY, DD.MM.YYYY, DD-MM-YYYY and also space-separated "DD MM YYYY"
    // (as used on Bhutan and Nepal passports, e.g. "02 04 1991")
    private val DATE_PATTERN = Regex("""(\d{1,2})[./\-\s](\d{1,2})[./\-\s](\d{4})""")
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
    // Nepal DL: DD-DD-DDDDDDDD (e.g., 28-49-26819815, 03-06-00354234)
    private val NEPAL_DL_PATTERN = Regex("""(?:D\.?L\.?\s*No\.?\s*[:/]?\s*)(\d{2}-\d{2}-\d{8})""", RegexOption.IGNORE_CASE)
    // Bhutan DL: X-DDDDD (e.g., G-18638, T-22358)
    private val BHUTAN_DL_PATTERN = Regex("""(?:License\s*No\.?\s*[:/]?\s*)([A-Z]-\d{5})""", RegexOption.IGNORE_CASE)

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
        if (lower.contains("सवारी चालक") || lower.contains("अनुमतिपत्र")) scores["DRIVING_LICENCE"] = (scores["DRIVING_LICENCE"] ?: 0) + 10
        if (lower.contains("d.l.no") || lower.contains("dl no")) scores["DRIVING_LICENCE"] = (scores["DRIVING_LICENCE"] ?: 0) + 8
        if (lower.contains("license office")) scores["DRIVING_LICENCE"] = (scores["DRIVING_LICENCE"] ?: 0) + 7
        if (lower.contains("license no") || lower.contains("licence no")) scores["DRIVING_LICENCE"] = (scores["DRIVING_LICENCE"] ?: 0) + 7
        if (lower.contains("category") && (lower.contains("a") || lower.contains("b"))) scores["DRIVING_LICENCE"] = (scores["DRIVING_LICENCE"] ?: 0) + 3
        if (lower.contains("f/h name")) scores["DRIVING_LICENCE"] = (scores["DRIVING_LICENCE"] ?: 0) + 6
        if (lower.contains("s/d/w of") || lower.contains("son/daughter/wife")) scores["DRIVING_LICENCE"] = (scores["DRIVING_LICENCE"] ?: 0) + 6
        if (lower.contains("validity") && (lower.contains("nt") || lower.contains("tr"))) scores["DRIVING_LICENCE"] = (scores["DRIVING_LICENCE"] ?: 0) + 7
        if (lower.contains("valid till")) scores["DRIVING_LICENCE"] = (scores["DRIVING_LICENCE"] ?: 0) + 7
        if (lower.contains("union of india") && lower.contains("driving")) scores["DRIVING_LICENCE"] = (scores["DRIVING_LICENCE"] ?: 0) + 10
        if (lower.contains("government of nepal") && lower.contains("driving")) scores["DRIVING_LICENCE"] = (scores["DRIVING_LICENCE"] ?: 0) + 10
        if (lower.contains("kingdom of bhutan") && lower.contains("driving")) scores["DRIVING_LICENCE"] = (scores["DRIVING_LICENCE"] ?: 0) + 10
        if (NEPAL_DL_PATTERN.containsMatchIn(text)) scores["DRIVING_LICENCE"] = (scores["DRIVING_LICENCE"] ?: 0) + 8
        if (BHUTAN_DL_PATTERN.containsMatchIn(text)) scores["DRIVING_LICENCE"] = (scores["DRIVING_LICENCE"] ?: 0) + 8
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
        // Nepal National Identity Card
        if (lower.contains("national identity card") || lower.contains("राष्ट्रिय परिचयपत्र")) scores["NATIONAL_ID"] = (scores["NATIONAL_ID"] ?: 0) + 10
        if (lower.contains("nin") && lower.contains("nepal")) scores["NATIONAL_ID"] = (scores["NATIONAL_ID"] ?: 0) + 9
        if (lower.contains("government of nepal") && lower.contains("identity")) scores["NATIONAL_ID"] = (scores["NATIONAL_ID"] ?: 0) + 9
        // Bhutan Citizenship Card
        if (lower.contains("citizenship card") || lower.contains("citizenship id no")) scores["NATIONAL_ID"] = (scores["NATIONAL_ID"] ?: 0) + 9
        if (lower.contains("kingdom of bhutan") && !lower.contains("driving")) scores["NATIONAL_ID"] = (scores["NATIONAL_ID"] ?: 0) + 7

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
        if (lower.contains("entry permit")) scores["PERMIT"] = (scores["PERMIT"] ?: 0) + 10
        if (lower.contains("travel permit")) scores["PERMIT"] = (scores["PERMIT"] ?: 0) + 10
        if (lower.contains("temporary travel permit")) scores["PERMIT"] = (scores["PERMIT"] ?: 0) + 10
        if (lower.contains("tourist permit")) scores["PERMIT"] = (scores["PERMIT"] ?: 0) + 10
        if (lower.contains("contract carriage permit")) scores["PERMIT"] = (scores["PERMIT"] ?: 0) + 10
        if (lower.contains("international driving permit")) scores["PERMIT"] = (scores["PERMIT"] ?: 0) + 10
        if (lower.contains("permit no") || lower.contains("permit number")) scores["PERMIT"] = (scores["PERMIT"] ?: 0) + 7
        if (lower.contains("purpose of visit")) scores["PERMIT"] = (scores["PERMIT"] ?: 0) + 7
        if (lower.contains("place of visit")) scores["PERMIT"] = (scores["PERMIT"] ?: 0) + 7
        if (lower.contains("valid from") || lower.contains("valid till") || lower.contains("valid until")) scores["PERMIT"] = (scores["PERMIT"] ?: 0) + 4
        if (lower.contains("non-bhutanese") || lower.contains("visiting bhutan")) scores["PERMIT"] = (scores["PERMIT"] ?: 0) + 9
        if (lower.contains("immigration office")) scores["PERMIT"] = (scores["PERMIT"] ?: 0) + 6
        if (lower.contains("अनुमति-पत्र") || lower.contains("अनुमतिपत्र")) scores["PERMIT"] = (scores["PERMIT"] ?: 0) + 10
        if (lower.contains("registration no") && lower.contains("permit")) scores["PERMIT"] = (scores["PERMIT"] ?: 0) + 8

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
        val isPassportDoc = isPassport(text)
        val isVisaDoc = isVisa(text)

        // Aadhaar 12-digit pattern must NOT run on passports/visas — MRZ digit
        // sequences produce false positives.
        if (!isPassportDoc && !isVisaDoc) {
            findBestAadhaarNumber(text)?.let { aadhaar ->
                result["document_number"] = aadhaar
                result["aadhaar_number"] = aadhaar
            }
        }

        if (!isPassportDoc && !isVisaDoc) {
            PAN_PATTERN.find(text)?.let { match ->
                result["document_number"] = match.groupValues[1]
                result["pan_number"] = match.groupValues[1]
            }
        }

        // Run passport-specific extraction first so G000000 / Z1234567 style
        // numbers are set before the generic [A-Z]\d{7} INDIAN_PASSPORT_PATTERN
        // can accidentally grab a 7-digit substring from the MRZ.
        if (isPassportDoc) {
            extractPassportFields(text, result)
        }

        // Only run the generic single-letter+7-digit pattern if we don't yet
        // have a passport number — prevents matching BTN9104026 → N9104026.
        if (!result.containsKey("passport_number")) {
            INDIAN_PASSPORT_PATTERN.find(text)?.let { match ->
                result["passport_number"] = match.groupValues[1]
                if (!result.containsKey("document_number")) result["document_number"] = match.groupValues[1]
            }
        }

        // Voter-ID pattern must NOT run on passports — VOTER_ID_PATTERN matches
        // 3-letter country codes like BTN/IND from the MRZ as false positives.
        if (!isPassportDoc) {
            VOTER_ID_PATTERN.find(text)?.let { match ->
                if (!result.containsKey("document_number")) result["document_number"] = match.groupValues[1]
                result["voter_id"] = match.groupValues[1]
            }
        }

        // DL number extraction — skip on passports/visas (MRZ false positives)
        if (!isPassportDoc && !isVisaDoc) {
            DL_NUMBER_PATTERN.find(text)?.let { match ->
                val dlNum = match.groupValues[1].replace(Regex("[\\s\\-]"), "")
                if (!result.containsKey("document_number")) result["document_number"] = dlNum
                result["dl_number"] = dlNum
            }
            if (!result.containsKey("dl_number")) {
                NEPAL_DL_PATTERN.find(text)?.let { match ->
                    val dlNum = match.groupValues[1]
                    if (!result.containsKey("document_number")) result["document_number"] = dlNum
                    result["dl_number"] = dlNum
                }
            }
            if (!result.containsKey("dl_number")) {
                BHUTAN_DL_PATTERN.find(text)?.let { match ->
                    val dlNum = match.groupValues[1]
                    if (!result.containsKey("document_number")) result["document_number"] = dlNum
                    result["dl_number"] = dlNum
                }
            }
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
        // extractPassportFields already called above for passports
        if (isVisa(text)) {
            extractVisaFields(text, result)
        }

        // Nepal NIN (National Identity Number): "393-384-5194" or "023-456-2130"
        if (!result.containsKey("document_number") || text.contains("NATIONAL IDENTITY", ignoreCase = true)) {
            val ninPattern = Regex("""(?:NIN|राष्ट्रिय परिचय नम्बर)\s*[:/]?\s*(\d{3}[-\s]?\d{3}[-\s]?\d{4})""", RegexOption.IGNORE_CASE)
            ninPattern.find(text)?.let {
                val nin = it.groupValues[1].replace(Regex("[\\s\\-]"), "")
                result["document_number"] = nin
                result["nin_number"] = nin
            }
            if (!result.containsKey("nin_number")) {
                // Standalone NIN pattern (3-3-4 with dashes)
                Regex("""\b(\d{3}-\d{3}-\d{4})\b""").find(text)?.let {
                    if (text.contains("NATIONAL IDENTITY", ignoreCase = true) || text.contains("परिचयपत्र")) {
                        val nin = it.groupValues[1].replace("-", "")
                        if (!result.containsKey("document_number")) result["document_number"] = nin
                        result["nin_number"] = nin
                    }
                }
            }
        }

        // Bhutan CID from "Name:value" format on Citizenship Card (not DL or permit)
        if ((text.contains("Citizenship Card", ignoreCase = true) ||
             (text.contains("KINGDOM OF BHUTAN", ignoreCase = true) && !isDrivingLicence(text) && !isPermit(text)))
        ) {
            extractBhutanCitizenshipCard(text, result)
        }

        // Nepal NID specific fields
        if (text.contains("NATIONAL IDENTITY CARD", ignoreCase = true) || text.contains("परिचयपत्र")) {
            extractNepalNidFields(text, result)
        }

        // Permit extraction
        if (isPermit(text)) {
            extractPermitFields(text, result)
        }

        extractCommonFields(text, result)

        return result
    }

    private fun isDrivingLicence(text: String): Boolean {
        val lower = text.lowercase()
        return lower.contains("driving licence") || lower.contains("driving license")
            || lower.contains("motor vehicle") || lower.contains("transport department")
            || lower.contains("सवारी चालक") || lower.contains("अनुमतिपत्र")
            || lower.contains("d.l.no") || lower.contains("dl no")
            || Regex("""\bRTO\b|\bRTA\b""", RegexOption.IGNORE_CASE).containsMatchIn(text)
    }

    private fun extractDrivingLicenceFields(text: String, result: MutableMap<String, String>) {
        val lines = text.lines().map { it.trim() }.filter { it.isNotEmpty() }

        // Name — "Name:" label (Indian & Nepal DL), or inline for Bhutan
        if (!result.containsKey("full_name")) {
            val namePattern = Regex("""(?:^|\n)\s*(?:Name|नाम)\s*[:/]?\s*(.+)""", RegexOption.IGNORE_CASE)
            namePattern.find(text)?.let {
                val candidate = it.groupValues[1].trim()
                if (candidate.isNotBlank() && isLikelyPersonName(candidate)) {
                    result["full_name"] = candidate.uppercase()
                }
            }
        }
        // Fallback: standalone person name line (Bhutan DL has name without label)
        if (!result.containsKey("full_name")) {
            for (line in lines) {
                if (isLikelyPersonName(line)) {
                    val lower = line.lowercase()
                    if (!lower.contains("transport") && !lower.contains("motor") &&
                        !lower.contains("union") && !lower.contains("state") &&
                        !lower.contains("kingdom") && !lower.contains("bhutan") &&
                        !lower.contains("driving") && !lower.contains("nepal") &&
                        !lower.contains("government") && !lower.contains("india") &&
                        !lower.contains("maharashtra") && !lower.contains("offence") &&
                        !lower.contains("signature") && !lower.contains("issued by") &&
                        !lower.contains("blood") && !lower.contains("category") &&
                        !lower.contains("validity") && !lower.contains("license")) {
                        result["full_name"] = line.trim().uppercase()
                        break
                    }
                }
            }
        }

        // DOB
        if (!result.containsKey("date_of_birth")) {
            val dobPattern = Regex("""(?:DOB|D\.?O\.?B\.?|Date\s*of\s*Birth|जन्म\s*(?:तिथि|दिनांक|मिति))\s*[:/]?\s*(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4})""", RegexOption.IGNORE_CASE)
            dobPattern.find(text)?.let { match ->
                normalizeDate(match.groupValues[1])?.let { result["date_of_birth"] = it }
            }
        }

        // Date of Issue — "DOI", "D.O.I.", "Issue Date", "Issued", "Date of Issue"
        if (!result.containsKey("date_of_issue")) {
            val issuePattern = Regex("""(?:D\.?O\.?I\.?|Issue\s*Date|Issued?\s*(?:On|Date)?|Date\s*of\s*Issue|जारी करने की तिथि|जारी मिति)\s*[:/]?\s*(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4})""", RegexOption.IGNORE_CASE)
            issuePattern.find(text)?.let { match ->
                normalizeDate(match.groupValues[1])?.let { result["date_of_issue"] = it }
            }
        }

        // Date of Expiry / Validity — "D.O.E.", "Valid Till", "Validity", "Validity (NT)"
        if (!result.containsKey("date_of_expiry")) {
            val expiryPattern = Regex("""(?:D\.?O\.?E\.?|Valid\s*Till|Validity\s*(?:\(NT\)|\(TR\))?|Date\s*of\s*Expiry|वैधता)\s*[:/]?\s*(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4})""", RegexOption.IGNORE_CASE)
            expiryPattern.find(text)?.let { match ->
                normalizeDate(match.groupValues[1])?.let { result["date_of_expiry"] = it }
            }
        }

        // Blood group
        if (!result.containsKey("blood_group")) {
            val bgPattern = Regex("""(?:Blood\s*Group|B\.?G\.?|रक्त\s*समूह)\s*[:/]?\s*([ABO]{1,2}[\s]?[+-]?\s*(?:Positive|Negative)?)\b""", RegexOption.IGNORE_CASE)
            bgPattern.find(text)?.let { result["blood_group"] = it.groupValues[1].trim() }
        }

        // Vehicle classes — LMV, MCWG, MCWOG, HMV, etc.
        if (!result.containsKey("vehicle_classes")) {
            val vcPattern = Regex("""\b(LMV|MCWG|MCWOG|HMV|HGV|LTV|MGV|HPMV|TRANS|AED)\b""")
            val classes = vcPattern.findAll(text).map { it.value }.toSet()
            if (classes.isNotEmpty()) result["vehicle_classes"] = classes.joinToString(", ")
        }

        // Category (Nepal DL): "Category: A,B"
        if (!result.containsKey("category")) {
            val catPattern = Regex("""Category\s*[:/]?\s*([A-Z](?:\s*,\s*[A-Z])*)""", RegexOption.IGNORE_CASE)
            catPattern.find(text)?.let { result["category"] = it.groupValues[1].trim() }
        }

        // Father/Husband name (Nepal DL): "F/H Name:" or "S/D/W of:" (Indian DL)
        if (!result.containsKey("fathers_name")) {
            val fhPattern = Regex("""(?:F/?H\s*Name|S/?D/?W\s*of|Son/?Daughter/?Wife\s*of|पिता/?पतिको?\s*नाम)\s*[:/]?\s*(.+)""", RegexOption.IGNORE_CASE)
            fhPattern.find(text)?.let {
                val candidate = it.groupValues[1].trim()
                if (candidate.isNotBlank() && isLikelyPersonName(candidate)) {
                    result["fathers_name"] = candidate.uppercase()
                }
            }
        }

        // Citizenship No (Nepal DL): "Citizenship No.: 92-87-62-14038"
        if (!result.containsKey("citizenship_number")) {
            val czPattern = Regex("""Citizenship\s*No\.?\s*[:/]?\s*([\d\-/]+)""", RegexOption.IGNORE_CASE)
            czPattern.find(text)?.let {
                val num = it.groupValues[1].trim()
                if (num.length >= 5) result["citizenship_number"] = num
            }
        }

        // License Office (Nepal DL)
        if (!result.containsKey("issuing_authority")) {
            val officePattern = Regex("""License\s*Office\s*[:/]?\s*(.+)""", RegexOption.IGNORE_CASE)
            officePattern.find(text)?.let {
                result["issuing_authority"] = it.groupValues[1].trim()
            }
        }
        // Issuing Authority (Indian DL): "Issuing Authority: MH03 2008261"
        if (!result.containsKey("issuing_authority")) {
            val iaPattern = Regex("""(?:Issuing|Licensing|Licencing)\s*Authority\s*[:/]?\s*(.+)""", RegexOption.IGNORE_CASE)
            iaPattern.find(text)?.let {
                result["issuing_authority"] = it.groupValues[1].trim()
            }
        }

        // Address: "Address:" or "Add:" (Indian DL)
        if (!result.containsKey("address")) {
            val addrPattern = Regex("""(?:Address|Add)\s*[:/]?\s*(.+)""", RegexOption.IGNORE_CASE)
            addrPattern.find(text)?.let {
                result["address"] = it.groupValues[1].trim()
            }
        }

        // CID for Bhutan DL
        if (!result.containsKey("cid_number")) {
            val cidPattern = Regex("""CID\s*[:/]?\s*(\d{11})""", RegexOption.IGNORE_CASE)
            cidPattern.find(text)?.let {
                result["cid_number"] = it.groupValues[1]
                if (!result.containsKey("document_number")) result["document_number"] = it.groupValues[1]
            }
        }

        // Sex/Gender
        if (!result.containsKey("sex")) {
            val sexPattern = Regex("""(?:Sex|Gender)\s*[:/]?\s*(M|F|Male|Female)""", RegexOption.IGNORE_CASE)
            sexPattern.find(text)?.let {
                result["sex"] = when (it.groupValues[1].uppercase().first()) {
                    'M' -> "M"; 'F' -> "F"; else -> it.groupValues[1].uppercase()
                }
            }
        }

        // Nationality inference
        if (!result.containsKey("nationality")) {
            val lower = text.lowercase()
            result["nationality"] = when {
                lower.contains("bhutan") || lower.contains("kingdom of bhutan") -> "BHUTANESE"
                lower.contains("nepal") || lower.contains("government of nepal") -> "NEPALI"
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

    private fun isPermit(text: String): Boolean {
        val lower = text.lowercase()
        return (lower.contains("permit") && !lower.contains("driving licence") && !lower.contains("driving license"))
            || lower.contains("entry permit") || lower.contains("travel permit")
            || lower.contains("tourist permit") || lower.contains("inner line permit")
            || lower.contains("अनुमति-पत्र") || lower.contains("अनुमतिपत्र")
            || lower.contains("contract carriage permit") || lower.contains("international driving permit")
    }

    private fun extractPermitFields(text: String, result: MutableMap<String, String>) {
        val lines = text.lines().map { it.trim() }.filter { it.isNotEmpty() }

        // Permit type detection
        if (!result.containsKey("permit_type")) {
            val lower = text.lowercase()
            result["permit_type"] = when {
                lower.contains("entry permit") -> "Entry Permit"
                lower.contains("temporary travel permit") -> "Temporary Travel Permit"
                lower.contains("tourist permit") || lower.contains("all india tourist permit") -> "Tourist Permit"
                lower.contains("contract carriage permit") -> "Contract Carriage Permit"
                lower.contains("international driving permit") -> "International Driving Permit"
                lower.contains("inner line permit") || lower.contains("ilp") -> "Inner Line Permit"
                lower.contains("अनुमति-पत्र") || lower.contains("अनुमतिपत्र") -> "Vehicle Permit"
                else -> "Permit"
            }
        }

        // Permit number: "Permit No:", "Permit No.:", "Ref. No.:", "#"
        if (!result.containsKey("permit_number")) {
            val pnPattern = Regex("""(?:Permit\s*No\.?\s*|अनुमति\s*पत्र\s*नं?\.?\s*)[:/]?\s*([A-Z0-9/\-]+\d+[A-Z0-9/\-]*)""", RegexOption.IGNORE_CASE)
            pnPattern.find(text)?.let {
                result["permit_number"] = it.groupValues[1].trim()
                if (!result.containsKey("document_number")) result["document_number"] = it.groupValues[1].trim()
            }
        }

        // Ref number
        if (!result.containsKey("ref_number")) {
            val refPattern = Regex("""(?:Ref\.?\s*No\.?|Reference\s*No\.?)\s*[:/]?\s*(\d+)""", RegexOption.IGNORE_CASE)
            refPattern.find(text)?.let { result["ref_number"] = it.groupValues[1].trim() }
        }

        // Registration No (vehicle permits)
        if (!result.containsKey("registration_no")) {
            val regPattern = Regex("""Registration\s*(?:No\.?|Mark)\s*[:/]?\s*([A-Z0-9]+)""", RegexOption.IGNORE_CASE)
            regPattern.find(text)?.let { result["registration_no"] = it.groupValues[1].trim() }
        }

        // Owner Name / Name
        if (!result.containsKey("full_name")) {
            val namePatterns = listOf(
                Regex("""(?:Owner\s*Name|Name\s*(?:\(Gender\))?)\s*[:/]?\s*(.+)""", RegexOption.IGNORE_CASE),
                Regex("""(?:Name\s*Of\s*(?:The\s*)?Permit\s*Holder)\s*[:/]?\s*(.+)""", RegexOption.IGNORE_CASE),
            )
            for (pat in namePatterns) {
                pat.find(text)?.let {
                    val candidate = it.groupValues[1].trim().replace(Regex("""\(.*\)"""), "").trim()
                    if (candidate.isNotBlank() && isLikelyPersonName(candidate)) {
                        result["full_name"] = candidate.uppercase()
                    }
                }
                if (result.containsKey("full_name")) break
            }
        }

        // Nationality
        if (!result.containsKey("nationality")) {
            val natPattern = Regex("""Nationality\s*[:/]?\s*(\w+)""", RegexOption.IGNORE_CASE)
            natPattern.find(text)?.let { result["nationality"] = it.groupValues[1].trim().uppercase() }
        }

        // Purpose of Visit
        if (!result.containsKey("purpose")) {
            val purposePattern = Regex("""Purpose\s*(?:of\s*Visit)?\s*[:/]?\s*(.+)""", RegexOption.IGNORE_CASE)
            purposePattern.find(text)?.let { result["purpose"] = it.groupValues[1].trim() }
        }

        // Place of Visit
        if (!result.containsKey("place_of_visit")) {
            val placePattern = Regex("""Place\s*(?:of\s*Visit)?\s*[:/]?\s*(.+)""", RegexOption.IGNORE_CASE)
            placePattern.find(text)?.let { result["place_of_visit"] = it.groupValues[1].trim() }
        }

        // Valid From / Date of Issue
        if (!result.containsKey("date_of_issue")) {
            val fromPatterns = listOf(
                Regex("""(?:Valid\s*From|Date\s*of\s*Issue|Issued?\s*(?:Date)?)\s*[:/]?\s*(.+)""", RegexOption.IGNORE_CASE),
            )
            for (pat in fromPatterns) {
                pat.find(text)?.let {
                    normalizeDate(it.groupValues[1].trim())?.let { d -> result["date_of_issue"] = d }
                }
                if (result.containsKey("date_of_issue")) break
            }
        }

        // Valid Till / Until / Date of Expiry
        if (!result.containsKey("date_of_expiry")) {
            val tillPatterns = listOf(
                Regex("""(?:Valid\s*(?:Till|Until|upto)|Date\s*of\s*Expiry)\s*[:/]?\s*(.+)""", RegexOption.IGNORE_CASE),
            )
            for (pat in tillPatterns) {
                pat.find(text)?.let {
                    normalizeDate(it.groupValues[1].trim())?.let { d -> result["date_of_expiry"] = d }
                }
                if (result.containsKey("date_of_expiry")) break
            }
        }

        // Place of Issue
        if (!result.containsKey("place_of_issue")) {
            val poiPattern = Regex("""Place\s*(?:of\s*Issue)?\s*[:/]?\s*(.+)""", RegexOption.IGNORE_CASE)
            poiPattern.find(text)?.let { result["place_of_issue"] = it.groupValues[1].trim() }
        }

        // Issuing Authority
        if (!result.containsKey("issuing_authority")) {
            val iaPattern = Regex("""(?:Issuing\s*Authority|Immigration\s*Office[r]?)\s*[:/]?\s*(.+)""", RegexOption.IGNORE_CASE)
            iaPattern.find(text)?.let { result["issuing_authority"] = it.groupValues[1].trim() }
        }

        // Address
        if (!result.containsKey("address")) {
            val addrPattern = Regex("""(?:Complete\s*)?Address\s*(?:in\s*\w+)?\s*[:/]?\s*(.+)""", RegexOption.IGNORE_CASE)
            addrPattern.find(text)?.let { result["address"] = it.groupValues[1].trim() }
        }

        // Sex/Gender from "(male)" or "(female)"
        if (!result.containsKey("sex")) {
            val sexPattern = Regex("""\((male|female)\)""", RegexOption.IGNORE_CASE)
            sexPattern.find(text)?.let {
                result["sex"] = if (it.groupValues[1].uppercase().startsWith("M")) "M" else "F"
            }
        }
    }

    private val VISA_NUMBER_PATTERN = Regex("""(?:Visa\s*(?:N[os]\.?\s*)?(?:No\.?|Number)?\s*(?:IB)?\s*[:/]?\s*)(\d{4,10})""", RegexOption.IGNORE_CASE)
    private val ETA_NUMBER_PATTERN = Regex("""(?:ETA\s*(?:No\.?|Number)\s*[:/]?\s*)([A-Z0-9]{6,20})""", RegexOption.IGNORE_CASE)
    // Bhutan passports label it "CITIZENSHIP ID NO" not "CID NO"
    private val BHUTAN_CID_PATTERN = Regex("""(?:(?:CITIZENSHIP\s*ID\s*(?:NO\.?|NUMBER)?|CID\s*(?:No\.?|Number)?)\s*[:/]?\s*)(\d{11})""", RegexOption.IGNORE_CASE)
    private val NEPAL_CITIZENSHIP_PATTERN = Regex("""(?:(?:Citizenship|Na\.?\s*Pra\.?)\s*(?:No\.?|Number)?\s*[:/]?\s*)(\d{2}[-/]\d{2}[-/]\d{2}[-/]\d{4,6})""", RegexOption.IGNORE_CASE)

    private fun extractPassportFields(text: String, result: MutableMap<String, String>) {
        val lines = text.lines().map { it.trim() }.filter { it.isNotEmpty() }

        // Passport number from printed text (not just MRZ).
        // Bhutan passports: "PASSPORT NO  G000000" — label + value on same or next line.
        // India: Z1234567 (1 letter + 7 digits), Bhutan: G000000 (1 letter + 6 digits).
        if (!result.containsKey("passport_number")) {
            val ppPatterns = listOf(
                // Explicit label match — most reliable
                Regex("""(?:PASSPORT\s*NO\.?|Passport\s*(?:No\.?|Number))\s*[:/]?\s*([A-Z]{1,2}\d{5,8})""", RegexOption.IGNORE_CASE),
                Regex("""(?:No\.?\s*du\s*passeport|राहदानी\s*नं\.?\s*[:/]?\s*)([A-Z]{1,2}\d{5,8})""", RegexOption.IGNORE_CASE),
                // Label on one line, value on next (Bhutan passport layout)
            )
            // First try label-based patterns
            for (p in ppPatterns) {
                val m = p.find(text) ?: continue
                result["passport_number"] = m.groupValues[1]
                if (!result.containsKey("document_number")) result["document_number"] = m.groupValues[1]
                break
            }
            // If still not found, look for label on its own line then value on next
            if (!result.containsKey("passport_number")) {
                val ls = text.lines().map { it.trim() }
                val ppLabelIdx = ls.indexOfFirst { it.contains("PASSPORT NO", ignoreCase = true) && it.length < 30 }
                if (ppLabelIdx >= 0) {
                    val afterLabel = ls[ppLabelIdx].uppercase().substringAfter("PASSPORT NO").trim().trimStart(':', '.', ' ')
                    val nextLine = ls.getOrNull(ppLabelIdx + 1)?.trim() ?: ""
                    val candidate = afterLabel.ifBlank { nextLine }
                    Regex("""([A-Z]{1,2}\d{5,8})""").find(candidate)?.let { m ->
                        result["passport_number"] = m.groupValues[1]
                        if (!result.containsKey("document_number")) result["document_number"] = m.groupValues[1]
                    }
                }
            }
        }
        // Fallback: any [A-Z]\d{5,8} standalone token that isn't from the MRZ
        if (!result.containsKey("passport_number")) {
            Regex("""\b([A-Z]{1,2}\d{5,8})\b""").findAll(text).forEach { m ->
                val v = m.groupValues[1]
                // Skip tokens that appear inside the MRZ line (MRZ starts with P<)
                val inMrz = text.lines().any { it.contains("P<") && it.contains(v) }
                if (!inMrz) {
                    result["passport_number"] = v
                    if (!result.containsKey("document_number")) result["document_number"] = v
                    return@forEach
                }
            }
        }

        // Place of birth — same-line or next-line (bilingual Indian passports)
        if (!result.containsKey("place_of_birth")) {
            val pobRegex = Regex("""(?:Place\s*of\s*Birth|POB|जन्म\s*स्थान)\s*[:/]?\s*([A-Za-z\s,]+)""", RegexOption.IGNORE_CASE)
            pobRegex.find(text)?.let {
                val place = it.groupValues[1].trim().take(50)
                if (place.length >= 2) result["place_of_birth"] = place
            }
            if (!result.containsKey("place_of_birth")) {
                val pobIdx = lines.indexOfFirst {
                    it.contains("PLACE OF BIRTH", ignoreCase = true) || it.contains("जन्म स्थान", ignoreCase = false)
                }
                if (pobIdx >= 0) {
                    val nextLine = lines.getOrNull(pobIdx + 1)?.trim()
                    if (nextLine != null && nextLine.length in 2..50 && !isLabelOnlyLine(nextLine) &&
                        nextLine.any { it.isLetter() }) {
                        result["place_of_birth"] = nextLine.replace(Regex("""[/\\].*"""), "").trim()
                    }
                }
            }
        }

        // Place of issue — same-line or next-line
        if (!result.containsKey("place_of_issue")) {
            val poiRegex = Regex("""(?:Place\s*of\s*Issue|जारी\s*(?:करने\s*का\s*)?स्थान)\s*[:/]?\s*([A-Za-z\s,]+)""", RegexOption.IGNORE_CASE)
            poiRegex.find(text)?.let {
                val place = it.groupValues[1].trim().take(50)
                if (place.length >= 2) result["place_of_issue"] = place
            }
            if (!result.containsKey("place_of_issue")) {
                val poiIdx = lines.indexOfFirst {
                    it.contains("PLACE OF ISSUE", ignoreCase = true) || it.contains("जारी", ignoreCase = false) && it.contains("स्थान", ignoreCase = false)
                }
                if (poiIdx >= 0) {
                    val nextLine = lines.getOrNull(poiIdx + 1)?.trim()
                    if (nextLine != null && nextLine.length in 2..50 && !isLabelOnlyLine(nextLine) &&
                        nextLine.any { it.isLetter() }) {
                        result["place_of_issue"] = nextLine.replace(Regex("""[/\\].*"""), "").trim()
                    }
                }
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
            BHUTAN_CID_PATTERN.find(text)?.let {
                result["cid_number"] = it.groupValues[1]
                if (!result.containsKey("document_number")) result["citizenship_id"] = it.groupValues[1]
            }
        }

        // Bhutan passport: "NAME OF BEARER" and "SURNAME" are on separate
        // lines with their respective values on the NEXT non-label line.
        // OCR may read: "SURNAME\nDOE\nNAME OF BEARER\nJOHN" or vice versa.
        // Skip any line that IS a label when looking for the value.
        if (!result.containsKey("name")) {
            val labelLines = setOf("surname", "name of bearer", "name of beafer", "nationality",
                "sex", "date of birth", "date of expiry", "date of issue",
                "place of birth", "place of issue", "passport no", "type",
                "country code", "citizenship id no", "authority", "issuing authority")

            fun valueAfterLabel(labelIdx: Int): String? {
                if (labelIdx < 0) return null
                // First check text after label on the same line
                val sameLine = lines[labelIdx]
                val labelText = sameLine.trim()
                // If the label line also contains a value (e.g. "PASSPORT NO G000000")
                val afterColon = sameLine.substringAfter(":", "").trim()
                    .ifBlank { sameLine.substringAfterLast("  ", "").trim() }
                if (afterColon.isNotBlank() && !labelLines.contains(afterColon.lowercase())) {
                    return afterColon
                }
                // Look at following lines, skip any that are themselves labels
                for (offset in 1..3) {
                    val nextIdx = labelIdx + offset
                    if (nextIdx >= lines.size) break
                    val nextLine = lines[nextIdx].trim()
                    val nextLower = nextLine.lowercase()
                    if (labelLines.any { nextLower == it || nextLower.startsWith("$it ") }) continue
                    if (nextLine.isBlank()) continue
                    return nextLine
                }
                return null
            }

            val nameOfBearerIdx = lines.indexOfFirst {
                it.contains("NAME OF BEARER", ignoreCase = true) ||
                it.contains("NAME OF BEAFER", ignoreCase = true) ||
                it.contains("GIVEN NAME", ignoreCase = true)
            }
            val surnameIdx = lines.indexOfFirst {
                it.contains("SURNAME", ignoreCase = true) &&
                !it.contains("NAME OF BEARER", ignoreCase = true) &&
                !it.contains("GIVEN NAME", ignoreCase = true)
            }
            val givenName = valueAfterLabel(nameOfBearerIdx)?.takeIf { isLikelyPersonName(it) }
            val surname = valueAfterLabel(surnameIdx)?.takeIf { isLikelyPersonName(it) }
            when {
                givenName != null && surname != null -> result["name"] = "$givenName $surname"
                givenName != null -> result["name"] = givenName
                surname != null -> result["name"] = surname
            }
        }

        // Passport dates: "30 JUL 1983" (Nepal), "02 04 1991" (Bhutan),
        // or "15/11/1990" (India). Try named-month first, then numeric.
        fun extractDateNearLabel(labelKeywords: List<String>): String? {
            val idx = lines.indexOfFirst { line -> labelKeywords.any { line.contains(it, ignoreCase = true) } }
            if (idx < 0) return null
            for (offset in 0..2) {
                val candidate = lines.getOrNull(idx + offset) ?: continue
                normalizeDate(candidate)?.let { return it }
            }
            return null
        }
        if (!result.containsKey("date_of_birth")) {
            extractDateNearLabel(listOf("DATE OF BIRTH", "जन्म तिथि", "जन्म दिनांक", "जन्म मिति"))?.let {
                result["date_of_birth"] = it
            }
        }
        if (!result.containsKey("date_of_expiry")) {
            extractDateNearLabel(listOf("DATE OF EXPIRY", "अन्तिम तिथि", "म्याद सकिने"))?.let {
                result["date_of_expiry"] = it
            }
        }
        if (!result.containsKey("date_of_issue")) {
            extractDateNearLabel(listOf("DATE OF ISSUE", "जारी करने की तिथि", "जारी तिथि", "जारी मिति"))?.let {
                result["date_of_issue"] = it
            }
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

    private fun extractBhutanCitizenshipCard(text: String, result: MutableMap<String, String>) {
        val lines = text.lines().map { it.trim() }.filter { it.isNotEmpty() }

        // CID number: 11 digits (e.g., 10712002883)
        if (!result.containsKey("document_number")) {
            val cidPattern = Regex("""\b(\d{11})\b""")
            for (line in lines) {
                if (line.contains("CID", ignoreCase = true) || line.contains("Citizenship", ignoreCase = true)) {
                    cidPattern.find(line)?.let {
                        result["document_number"] = it.groupValues[1]
                        result["cid_number"] = it.groupValues[1]
                    }
                }
            }
            if (!result.containsKey("cid_number")) {
                for (line in lines) {
                    cidPattern.find(line)?.let {
                        if (it.groupValues[1].length == 11) {
                            result["document_number"] = it.groupValues[1]
                            result["cid_number"] = it.groupValues[1]
                            return@let
                        }
                    }
                }
            }
        }

        // Inline "Name: Phuntsho Tashi" pattern
        val nameInlinePattern = Regex("""(?:Name|NAME)\s*[:\-]\s*(.+)""", RegexOption.IGNORE_CASE)
        if (!result.containsKey("full_name")) {
            for (line in lines) {
                nameInlinePattern.find(line)?.let {
                    val candidate = it.groupValues[1].trim()
                    if (isLikelyPersonName(candidate)) {
                        result["full_name"] = candidate.uppercase()
                    }
                }
            }
        }

        // Dzongkhag (district)
        val dzongkhagPattern = Regex("""(?:Dzongkhag|District)\s*[:\-]\s*(.+)""", RegexOption.IGNORE_CASE)
        for (line in lines) {
            dzongkhagPattern.find(line)?.let {
                result["place_of_birth"] = it.groupValues[1].trim()
            }
        }

        // Sex/Gender
        if (!result.containsKey("sex")) {
            val sexPattern = Regex("""(?:Sex|Gender)\s*[:\-]\s*(M|F|Male|Female)""", RegexOption.IGNORE_CASE)
            for (line in lines) {
                sexPattern.find(line)?.let {
                    result["sex"] = when (it.groupValues[1].uppercase().first()) {
                        'M' -> "M"
                        'F' -> "F"
                        else -> it.groupValues[1].uppercase()
                    }
                }
            }
        }

        // Date of birth, date of issue
        for ((i, line) in lines.withIndex()) {
            val lower = line.lowercase()
            if (lower.contains("date of birth") || lower.contains("dob")) {
                for (offset in 0..2) {
                    normalizeDate(lines.getOrElse(i + offset) { "" })?.let {
                        result["date_of_birth"] = it
                        return@let
                    }
                    if (result.containsKey("date_of_birth")) break
                }
            }
            if (lower.contains("date of issue")) {
                for (offset in 0..2) {
                    normalizeDate(lines.getOrElse(i + offset) { "" })?.let {
                        result["date_of_issue"] = it
                        return@let
                    }
                    if (result.containsKey("date_of_issue")) break
                }
            }
        }
    }

    private fun extractNepalNidFields(text: String, result: MutableMap<String, String>) {
        val lines = text.lines().map { it.trim() }.filter { it.isNotEmpty() }

        // Full name from "FULL NAME" / "पूरा नाम" label
        for ((i, line) in lines.withIndex()) {
            val lower = line.lowercase()
            if (lower.contains("full name") || line.contains("पूरा नाम")) {
                // Value might be on same line after label or next line
                val afterLabel = line.substringAfter("FULL NAME", line)
                    .substringAfter("पूरा नाम", "")
                    .replace(Regex("^[:\\-/\\s]+"), "").trim()
                if (afterLabel.isNotBlank() && isLikelyPersonName(afterLabel)) {
                    result["full_name"] = afterLabel.uppercase()
                } else {
                    val nextLine = lines.getOrNull(i + 1)
                    if (nextLine != null && isLikelyPersonName(nextLine)) {
                        result["full_name"] = nextLine.uppercase()
                    }
                }
                break
            }
        }

        // Surname / Given Name
        for ((i, line) in lines.withIndex()) {
            val lower = line.lowercase()
            if ((lower.contains("surname") || lower.contains("थर")) && !result.containsKey("surname")) {
                val afterLabel = line.replace(Regex("""(?i)(surname|थर)\s*[:\-/]?\s*"""), "").trim()
                if (afterLabel.isNotBlank() && isLikelyPersonName(afterLabel)) {
                    result["surname"] = afterLabel.uppercase()
                } else {
                    lines.getOrNull(i + 1)?.let {
                        if (isLikelyPersonName(it)) result["surname"] = it.uppercase()
                    }
                }
            }
            if ((lower.contains("given name") || lower.contains("नाम")) &&
                !lower.contains("full name") && !lower.contains("पूरा") &&
                !lower.contains("surname") && !lower.contains("father") && !lower.contains("mother") &&
                !result.containsKey("given_name")) {
                val afterLabel = line.replace(Regex("""(?i)(given\s*names?|नाम)\s*[:\-/]?\s*"""), "").trim()
                if (afterLabel.isNotBlank() && isLikelyPersonName(afterLabel)) {
                    result["given_name"] = afterLabel.uppercase()
                } else {
                    lines.getOrNull(i + 1)?.let {
                        if (isLikelyPersonName(it)) result["given_name"] = it.uppercase()
                    }
                }
            }
        }

        // Father's name / Mother's name
        for ((i, line) in lines.withIndex()) {
            val lower = line.lowercase()
            if ((lower.contains("father") || line.contains("बाबुको नाम")) && !result.containsKey("fathers_name")) {
                val afterLabel = line.replace(Regex("""(?i)(father'?s?\s*name|बाबुको नाम)\s*[:\-/]?\s*"""), "").trim()
                if (afterLabel.isNotBlank() && isLikelyPersonName(afterLabel)) {
                    result["fathers_name"] = afterLabel.uppercase()
                } else {
                    lines.getOrNull(i + 1)?.let {
                        if (isLikelyPersonName(it)) result["fathers_name"] = it.uppercase()
                    }
                }
            }
            if ((lower.contains("mother") || line.contains("आमाको नाम")) && !result.containsKey("mothers_name")) {
                val afterLabel = line.replace(Regex("""(?i)(mother'?s?\s*name|आमाको नाम)\s*[:\-/]?\s*"""), "").trim()
                if (afterLabel.isNotBlank() && isLikelyPersonName(afterLabel)) {
                    result["mothers_name"] = afterLabel.uppercase()
                } else {
                    lines.getOrNull(i + 1)?.let {
                        if (isLikelyPersonName(it)) result["mothers_name"] = it.uppercase()
                    }
                }
            }
        }

        // Date of birth (YYYY-MM-DD format common on Nepal NID)
        for ((i, line) in lines.withIndex()) {
            val lower = line.lowercase()
            if ((lower.contains("date of birth") || lower.contains("जन्म मिति") || lower.contains("dob")) &&
                !result.containsKey("date_of_birth")) {
                for (offset in 0..2) {
                    normalizeDate(lines.getOrElse(i + offset) { "" })?.let {
                        result["date_of_birth"] = it
                        return@let
                    }
                    if (result.containsKey("date_of_birth")) break
                }
            }
        }

        // Date of issue
        for ((i, line) in lines.withIndex()) {
            val lower = line.lowercase()
            if ((lower.contains("date of issue") || lower.contains("जारी मिति")) && !result.containsKey("date_of_issue")) {
                for (offset in 0..2) {
                    normalizeDate(lines.getOrElse(i + offset) { "" })?.let {
                        result["date_of_issue"] = it
                        return@let
                    }
                    if (result.containsKey("date_of_issue")) break
                }
            }
        }

        // Sex/Gender
        if (!result.containsKey("sex")) {
            for (line in lines) {
                val sexMatch = Regex("""(?:Sex|Gender|लिङ्ग)\s*[:\-]\s*(M|F|Male|Female|पुरुष|महिला)""", RegexOption.IGNORE_CASE).find(line)
                if (sexMatch != null) {
                    val v = sexMatch.groupValues[1].uppercase()
                    result["sex"] = when {
                        v.startsWith("M") || v.contains("पुरुष") -> "M"
                        v.startsWith("F") || v.contains("महिला") -> "F"
                        else -> v
                    }
                    break
                }
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

        // Validity dates — handle both "27/12/2016" and "15 MAY 2025"
        val visaLines = text.lines().map { it.trim() }.filter { it.isNotEmpty() }
        fun visaDateNearLabel(keywords: List<String>): String? {
            val idx = visaLines.indexOfFirst { line -> keywords.any { line.contains(it, ignoreCase = true) } }
            if (idx < 0) return null
            for (offset in 0..1) {
                val candidate = visaLines.getOrNull(idx + offset) ?: continue
                normalizeDate(candidate)?.let { return it }
            }
            return null
        }
        if (!result.containsKey("date_of_issue")) {
            visaDateNearLabel(listOf("Date of Issue", "Issued on", "Issue Date", "Valid From", "जारी"))?.let {
                result["date_of_issue"] = it
            }
        }
        if (!result.containsKey("date_of_expiry")) {
            visaDateNearLabel(listOf("Date of Expiry", "Visa Expiration", "Expiry", "Valid Until", "Valid Till"))?.let {
                result["date_of_expiry"] = it
            }
        }

        // Nepal visa: "Issued at" = place of issue
        if (!result.containsKey("issuing_authority")) {
            val issuedAtPattern = Regex("""(?:Issued\s*at)\s*[:/]?\s*([A-Za-z\s,]+)""", RegexOption.IGNORE_CASE)
            issuedAtPattern.find(text)?.let {
                val place = it.groupValues[1].trim().take(50)
                if (place.length >= 2) result["issuing_authority"] = place
            }
        }

        // Nepal visa: "Passport No :" on visa sticker
        if (!result.containsKey("passport_number")) {
            val ppOnVisa = Regex("""Passport\s*No\.?\s*[:/]?\s*([A-Z]{1,2}\d{5,8})""", RegexOption.IGNORE_CASE)
            ppOnVisa.find(text)?.let { result["passport_number"] = it.groupValues[1] }
        }

        // Duration / validity period
        if (!result.containsKey("duration")) {
            val durPattern = Regex("""(\d+)\s*Days?\s*(?:Tourist\s*)?(?:Entry\s*)?Visa""", RegexOption.IGNORE_CASE)
            durPattern.find(text)?.let { result["duration"] = "${it.groupValues[1]} Days" }
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
        if (!result.containsKey("gender")) {
            // 1. Full-word match: Male/Female/MALE/FEMALE/Hindi equivalents
            AADHAAR_GENDER_PATTERN.find(text)?.let { match ->
                val g = match.value.lowercase()
                result["gender"] = when {
                    g == "male" || g == "पुरुष" -> "M"
                    g == "female" || g == "महिला" -> "F"
                    else -> match.value
                }
            }
        }
        if (!result.containsKey("gender")) {
            // 2. "SEX F" or "SEX M" on the same line (e.g. "SEX F DATE OF BIRTH")
            val sexInlinePattern = Regex("""(?:SEX|GENDER)\s+([MF])\b""", RegexOption.IGNORE_CASE)
            sexInlinePattern.find(text)?.let { result["gender"] = it.groupValues[1].uppercase() }
        }
        if (!result.containsKey("gender")) {
            // 3. Bhutan/Nepal passports: two-column OCR layout produces
            //    "F SEX" (value left, label right) OR "SEX\nF" (label line, value next line)
            val lines = text.lines().map { it.trim() }
            for ((idx, line) in lines.withIndex()) {
                val upper = line.uppercase()
                // "F SEX ..." or "M SEX ..." — value appears BEFORE the label
                val beforeSex = Regex("""^([MF])\s+(?:SEX|GENDER)\b""").find(upper)
                if (beforeSex != null) { result["gender"] = beforeSex.groupValues[1]; break }
                // "SEX\nF" or "SEX\nM" — label on this line, value on next
                if (upper == "SEX" || upper == "GENDER" || upper.endsWith(" SEX") || upper.endsWith(" GENDER")) {
                    val next = lines.getOrNull(idx + 1)?.trim()?.uppercase() ?: continue
                    val code = when {
                        next.startsWith("F") && (next.length == 1 || next[1].isWhitespace()) -> "F"
                        next.startsWith("M") && (next.length == 1 || next[1].isWhitespace()) -> "M"
                        next.startsWith("FEMALE") -> "F"
                        next.startsWith("MALE") -> "M"
                        else -> null
                    }
                    if (code != null) { result["gender"] = code; break }
                }
            }
        }
        if (!result.containsKey("gender")) {
            // 4. "Sex: F" or "Gender: M" with colon/separator on the same line
            val sexColonPattern = Regex("""(?:SEX|GENDER)\s*[:/]\s*([MF])\b""", RegexOption.IGNORE_CASE)
            sexColonPattern.find(text)?.let { result["gender"] = it.groupValues[1].uppercase() }
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
                    // Look at the next line, but skip it if it IS itself a known label
                    val nextLine = lines.getOrNull(index + 1)
                    if (nextLine != null && !containsAnyLabel(nextLine) && !isLabelOnlyLine(nextLine)) nextLine else ""
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
        val allLines = text.lines().map { it.trim() }.filter { it.isNotEmpty() }
        fun value(labels: String): String? {
            // First try same-line: "Surname: PAUL"
            text.lines().firstNotNullOfOrNull { line ->
                Regex("""(?i)^\s*(?:$labels)\s*[:\-]\s*(.+?)\s*$""").find(line)?.groupValues?.get(1)
            }?.let { return it }
            // Fallback: label on one line, value on the next (Indian bilingual passports)
            val labelRegex = Regex("""(?i)(?:$labels)""")
            for ((i, line) in allLines.withIndex()) {
                if (!labelRegex.containsMatchIn(line)) continue
                val afterLabel = line.substringAfter(labelRegex.find(line)!!.value).trim()
                    .removePrefix("/").removePrefix(":").removePrefix("-").trim()
                if (afterLabel.isNotBlank() && isLikelyPersonName(afterLabel)) return afterLabel
                val nextLine = allLines.getOrNull(i + 1) ?: continue
                if (isLikelyPersonName(nextLine)) return nextLine
            }
            return null
        }
        val surname = value("surname|last name|family name")
        val given = value("given names?|first names?|name of bearer|name of beafer")
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
     * filler. Only applied to candidate lines, never to normal text.
     * Spaces become `<` (OCR commonly reads `<` as space). */
    private fun normalizeMrzLine(raw: String): String =
        raw.uppercase()
            .map { c -> when {
                c in 'A'..'Z' || c in '0'..'9' || c == '<' -> c
                c.isWhitespace() -> '<'
                else -> '<'
            }}
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
        // Try line-based parsing first (standard case)
        val normalized = text.lines().map { normalizeMrzLine(it) }
        Log.d(TAG, "MRZ: ${normalized.size} lines, lengths=${normalized.map { it.length }}")
        for (line in normalized) {
            if (line.contains('<') || line.length > 30) Log.d(TAG, "MRZ candidate: [${line.length}] $line")
        }
        for (i in 0 until normalized.size - 1) {
            val rawL1 = normalized[i]
            val l2 = normalized[i + 1]
            if (l2.length !in 28..50 || rawL1.length !in 15..50) continue
            Log.d(TAG, "MRZ trying pair: L1[${rawL1.length}]=$rawL1 L2[${l2.length}]=$l2")
            val result = tryParseMrzPair(rawL1, l2)
            if (result != null) {
                Log.d(TAG, "MRZ parsed! lines=${result.lines.size} fields=${result.fields.keys}")
                return result
            }
        }
        // Fallback 1: try non-adjacent lines (OCR may insert blank/short
        // lines between the two MRZ rows)
        // Collect all P</V< lines (potential L1) and long alphanumeric lines (potential L2)
        val l1Candidates = normalized.indices.filter { idx ->
            val l = normalized[idx]
            l.length in 15..50 && (l[0] == 'P' || l[0] == 'V') && l.getOrNull(1)?.let { it == '<' || it.isLetter() } == true
        }
        val l2Candidates = normalized.indices.filter { normalized[it].length in 28..50 }
        for (i in l1Candidates) {
            for (j in l2Candidates) {
                if (j <= i) continue
                Log.d(TAG, "MRZ wide trying L1[$i]+L2[$j]: ${normalized[i].take(20)}... + ${normalized[j].take(20)}...")
                val result = tryParseMrzPair(normalized[i], normalized[j])
                if (result != null) {
                    Log.d(TAG, "MRZ wide parsed! lines=${result.lines.size} fields=${result.fields.keys}")
                    return result
                }
            }
        }
        // Fallback 2: search for P< pattern in flat text — handles cases
        // where OCR merges MRZ lines with surrounding text.
        val flat = normalizeMrzLine(text.replace("\n", " "))
        // Find L1 start: P<XXX followed by name characters
        val l1Match = Regex("""P<[A-Z]{3}[A-Z<]{8,}""").find(flat) ?: return null
        val l1Raw = flat.substring(l1Match.range.first)
        val l1 = l1Raw.take(44)
        if (l1.length < 44) return null
        // L2 starts after L1 — skip any filler `<` between the lines
        val afterL1 = l1Raw.substring(44).trimStart('<')
        // L2 starts with a document number (alphanumeric), look for it
        val l2Start = Regex("""[A-Z0-9]{2}[A-Z0-9<]{26,}""").find(afterL1) ?: return null
        val l2Candidate = afterL1.substring(l2Start.range.first).take(44)
        if (l2Candidate.length >= 28) {
            val result = tryParseMrzPair(l1, l2Candidate)
            if (result != null) return result
        }
        return null
    }

    private fun tryParseMrzPair(rawL1: String, rawL2: String): MrzParse? {
        val l1 = rawL1.padEnd(44, '<').take(44)
        var l2 = rawL2.padEnd(44, '<').take(44)
        if (l1[0] != 'P' && l1[0] != 'V') return null
        if (l1[1] != '<' && !l1[1].isLetter()) return null
        if (l2.length < 28) return null
        // Fix OCR artifact: extra < between check digit (pos 9) and nationality (pos 10-12).
        // If pos 10 is < but pos 11-13 are letters (nationality), remove the extra <.
        if (l2[10] == '<' && l2.length > 13 && l2[11].isLetter() && l2[12].isLetter() && l2[13].isLetter()) {
            l2 = (l2.substring(0, 10) + l2.substring(11)).padEnd(44, '<').take(44)
            Log.d(TAG, "MRZ L2 fixed extra <: $l2")
        }
        if (l2[20] != 'M' && l2[20] != 'F' && l2[20] != '<') return null
        val dob = mrzDate(fixDigits(l2.substring(13, 19)), isBirth = true)
        val exp = mrzDate(fixDigits(l2.substring(21, 27)), isBirth = false)
        if (dob == null && exp == null) return null

        val nameParts = l1.substring(5).split("<<")
        val surname = nameParts.firstOrNull().orEmpty().replace('<', ' ').trim()
        val given = nameParts.drop(1).joinToString(" ").replace('<', ' ').trim().replace(Regex("\\s+"), " ")
        val fields = LinkedHashMap<String, String>()
        listOf(given, surname).filter { it.isNotBlank() }.joinToString(" ").takeIf { it.isNotBlank() }
            ?.let { fields["name"] = it }
        l2.substring(0, 9).replace("<", "").takeIf { it.isNotBlank() }?.let { raw ->
            fields["passport_number"] = raw[0] + fixDigits(raw.substring(1))
        }
        l2.substring(10, 13).takeIf { it.all { c -> c.isLetter() } }?.let { fields["nationality"] = NATIONALITY_BY_ICAO[it] ?: it }
        dob?.let { fields["date_of_birth"] = it }
        exp?.let { fields["date_of_expiry"] = it }
        when (l2[20]) { 'M' -> fields["gender"] = "M"; 'F' -> fields["gender"] = "F" }
        val checkDigits = if (rawL2.length >= 44) validateMrzCheckDigits(rawL2) else null
        return MrzParse(listOf(l1, l2), fields, checkDigits)
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

    private val LABEL_ONLY_PATTERNS = setOf(
        "surname", "name of bearer", "name of beafer", "given name", "given names",
        "nationality", "sex", "date of birth", "date of expiry", "date of issue",
        "place of birth", "place of issue", "passport no", "passport number",
        "type", "country code", "citizenship id no", "authority", "issuing authority",
        "personal no", "holder's signature", "holder signature",
        "permit number", "permit no", "purpose of visit", "place of visit",
        "valid from", "valid till", "valid until", "valid upto",
        "driving licence", "driving license", "license no", "licence no",
        "blood group", "vehicle classes", "category", "address",
        "registration no", "owner name", "father's name", "mother's name",
    )

    private fun isLabelOnlyLine(line: String): Boolean {
        val trimmed = line.trim().lowercase()
        return LABEL_ONLY_PATTERNS.any { trimmed == it || trimmed.startsWith("$it ") || trimmed.startsWith("$it:") }
    }

    private val MONTH_NAMES = mapOf(
        "jan" to 1, "feb" to 2, "mar" to 3, "apr" to 4, "may" to 5, "jun" to 6,
        "jul" to 7, "aug" to 8, "sep" to 9, "oct" to 10, "nov" to 11, "dec" to 12,
        "january" to 1, "february" to 2, "march" to 3, "april" to 4,
        "june" to 6, "july" to 7, "august" to 8, "september" to 9,
        "october" to 10, "november" to 11, "december" to 12,
    )
    private val NAMED_MONTH_DATE = Regex("""(\d{1,2})\s+(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s+(\d{4})""", RegexOption.IGNORE_CASE)

    private val ISO_DATE = Regex("""(\d{4})-(\d{2})-(\d{2})""")

    private fun normalizeDate(text: String): String? {
        // Try "DD MON YYYY" first (Nepal passports: "30 JUL 1983")
        NAMED_MONTH_DATE.find(text)?.let { m ->
            val day = m.groupValues[1].toIntOrNull() ?: return@let
            val month = MONTH_NAMES[m.groupValues[2].lowercase()] ?: return@let
            val year = m.groupValues[3]
            if (day in 1..31 && month in 1..12) return "%02d/%02d/%s".format(day, month, year)
        }
        // Try ISO YYYY-MM-DD (Nepal NID: "1987-09-26")
        ISO_DATE.find(text)?.let { m ->
            val year = m.groupValues[1]
            val month = m.groupValues[2].toIntOrNull() ?: return@let
            val day = m.groupValues[3].toIntOrNull() ?: return@let
            if (day in 1..31 && month in 1..12 && year.toInt() in 1900..2100)
                return "%02d/%02d/%s".format(day, month, year)
        }
        // Then try numeric DD/MM/YYYY, DD.MM.YYYY, DD-MM-YYYY, DD MM YYYY
        val match = DATE_PATTERN.find(text) ?: return null
        val (a, b, year) = match.destructured
        val (day, month) = if (a.toInt() > 31 && b.toInt() <= 31) b to a else a to b
        val dayInt = day.toInt()
        val monthInt = month.toInt()
        if (dayInt !in 1..31 || monthInt !in 1..12) return null
        return "%02d/%02d/%s".format(dayInt, monthInt, year)
    }
}
