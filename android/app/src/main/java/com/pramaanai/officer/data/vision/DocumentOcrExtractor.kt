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
        Log.d(TAG, "Extraction: ${fields.size} fields, confidence=$confidence, docType=$docType")
        return ExtractionResult(
            fields = fields,
            rawText = text,
            confidence = confidence,
            mrzLines = mrzLines,
            mrzText = mrz?.lines?.takeIf { it.isNotEmpty() }?.joinToString("\n"),
            detectedDocumentType = docType,
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

    /** Detect document type from text patterns */
    private fun detectDocumentType(text: String): String? {
        val lower = text.lowercase()
        return when {
            // Indian documents
            lower.contains("aadhaar") || lower.contains("aadhar") || lower.contains("आधार")
                || lower.contains("unique identification") -> "NATIONAL_ID"
            PAN_PATTERN.find(text) != null || lower.contains("permanent account number")
                || lower.contains("income tax") || lower.contains("pan card") -> "PAN_CARD"
            lower.contains("voter") || lower.contains("epic") || lower.contains("electoral")
                || lower.contains("election commission") || lower.contains("निर्वाचन") -> "VOTER_ID"
            lower.contains("driving licence") || lower.contains("driving license")
                || lower.contains("motor vehicle") || lower.contains("transport")
                || lower.contains("सारथी") || lower.contains("अनुज्ञापत्र") -> "DRIVING_LICENCE"

            // Passport (Indian, Nepali, Bhutanese)
            INDIAN_PASSPORT_PATTERN.find(text) != null && lower.contains("passport") -> "PASSPORT"
            lower.contains("passport") || lower.contains("पासपोर्ट") || lower.contains("राहदानी") -> "PASSPORT"

            // Visa
            lower.contains("visa") || lower.contains("वीसा") || lower.contains("वीजा") -> "VISA"

            // Permit
            lower.contains("permit") || lower.contains("अनुमति") -> "PERMIT"

            // Nepal
            lower.contains("नागरिकता") || lower.contains("citizenship certificate")
                || lower.contains("nepal") && lower.contains("citizenship") -> "CITIZENSHIP_CERTIFICATE"

            // Bhutan
            lower.contains("citizen identity") || lower.contains("cid")
                || lower.contains("bhutan") && lower.contains("identity") -> "NATIONAL_ID"

            lower.contains("identity card") || lower.contains("id card") -> "NATIONAL_ID"

            else -> null
        }
    }

    /** Extract Indian document numbers using regex patterns */
    private fun extractIndianDocumentNumbers(text: String): Map<String, String> {
        val result = mutableMapOf<String, String>()

        AADHAAR_PATTERN.find(text)?.let { match ->
            val aadhaar = match.groupValues[1].replace("\\s".toRegex(), "")
            if (aadhaar.length == 12) {
                result["document_number"] = aadhaar
                result["aadhaar_number"] = aadhaar
            }
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

        // Document-type-specific field extraction
        if (result.containsKey("aadhaar_number")) {
            extractAadhaarFields(text, result)
        }
        if (result.containsKey("pan_number")) {
            extractPanFields(text, result)
        }
        extractCommonFields(text, result)

        return result
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

    private val AADHAAR_DOB_PATTERN = Regex("""(?:DOB|D\.O\.B\.?|जन्म\s*तिथि)\s*[:/]\s*(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4})""", RegexOption.IGNORE_CASE)
    private val AADHAAR_GENDER_PATTERN = Regex("""(?:Male|Female|पुरुष|महिला|MALE|FEMALE)""")
    private val AADHAAR_NAME_LINE_PATTERN = Regex("""^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+$""")

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

        // Name: look for a line that matches "Firstname Lastname" in English
        // (typically the line right after the Hindi name on Aadhaar)
        if (!result.containsKey("name")) {
            for (line in lines) {
                if (AADHAAR_NAME_LINE_PATTERN.matches(line) &&
                    !line.contains("Government", true) &&
                    !line.contains("India", true) &&
                    !line.contains("Aadhaar", true) &&
                    !line.contains("proof", true)) {
                    result["name"] = line
                    break
                }
            }
        }

        // Aadhaar is Indian, so nationality is always INDIAN
        if (!result.containsKey("nationality")) {
            result["nationality"] = "INDIAN"
        }
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

    private data class MrzParse(val lines: List<String>, val fields: Map<String, String>)

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
            return MrzParse(if (complete) listOf(l1, l2) else emptyList(), fields)
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
