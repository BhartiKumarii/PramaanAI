package com.pramaanai.officer.data.vision

import android.graphics.Bitmap
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
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

    private val recognizer by lazy { TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS) }

    suspend fun recognize(bitmap: Bitmap): ExtractionResult {
        val image = InputImage.fromBitmap(bitmap, 0)
        val text = suspendCancellableCoroutine { cont ->
            recognizer.process(image)
                .addOnSuccessListener { result -> cont.resume(result.text) }
                .addOnFailureListener { e -> cont.resumeWithException(e) }
        }
        val mrz = parseTd3Mrz(text)
        // The MRZ is machine-printed with check digits — far more reliable
        // than label-keyword guessing over free text — so where it exists it
        // wins over the heuristic fields for the values it carries.
        val fields = LinkedHashMap(mapFields(text)).apply {
            // "Surname:" and "Given Names:" are separate printed fields — the
            // generic label pass keeps only one of them, so join both.
            joinedLabelledName(text)?.let { put("name", it) }
            mrz?.let { putAll(it.fields) }
        }
        val mrzLines = mrz?.lines ?: emptyList()
        val docType = detectDocumentType(text)
        val confidence = calculateConfidence(fields, mrzLines, docType)
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
        ),
        "passport_number" to listOf(
            "passport no", "passport number", "passport no.", "passport #",
            "document no", "document number", "doc no", "doc number",
            "passport:", "passport no:", "passport number:",
        ),
        "document_number" to listOf(
            "document no", "document number", "doc no", "doc number",
            "id no", "id number", "identity no", "identity number",
            "aadhaar no", "aadhar no", "aadhaar number", "pan no", "pan number",
            "licence no", "license no", "licence number", "license number", "dl no",
            "permit no", "permit number", "visa no", "visa number",
        ),
        "nationality" to listOf(
            "nationality", "nationality:", "citizenship", "country",
            "nationality/citizenship", "nationalité", "nacionalidad",
        ),
        "date_of_birth" to listOf(
            "date of birth", "birth", "dob", "d.o.b.", "born",
            "date of birth:", "birth date", "birthday",
        ),
        "date_of_expiry" to listOf(
            "date of expiry", "expiry", "expiration", "expires",
            "valid until", "valid till", "expiry date", "date of expiration",
        ),
        // Canonical key is "gender" (not "sex") to match the backend's
        // OCR field-extraction and cross-check keys (see
        // app/services/ocr/field_extraction.py and
        // app/services/validation/cross_check.py's cross_check_gender).
        "gender" to listOf(
            "sex", "gender", "m/f", "male/female",
        ),
        "place_of_birth" to listOf(
            "place of birth", "birth place", "pob", "place of birth:",
        ),
        "date_of_issue" to listOf(
            "date of issue", "issue date", "issued", "date of issue:",
        ),
        "issuing_authority" to listOf(
            "issuing authority", "authority", "issued by", "issuing office",
        ),
    )

    private val DATE_PATTERN = Regex("""(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})""")
    private val MRZ_PATTERN = Pattern.compile("""^[A-Z0-9<]{44}$""")
    private val PASSPORT_MRZ_PATTERN = Pattern.compile("""^P[A-Z0-9<]{43}$""")
    private val ID_CARD_MRZ_PATTERN = Pattern.compile("""^I[A-Z0-9<]{43}$""")

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
            lower.contains("passport") -> "PASSPORT"
            lower.contains("visa") -> "VISA"
            lower.contains("aadhaar") || lower.contains("aadhar") -> "NATIONAL_ID"
            lower.contains("driving licence") || lower.contains("driver") -> "DRIVING_LICENCE"
            lower.contains("permit") -> "PERMIT"
            lower.contains("identity card") || lower.contains("id card") -> "NATIONAL_ID"
            else -> null
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

        // First pass: try label-based extraction
        for ((field, labels) in LABELS) {
            for ((index, line) in lines.withIndex()) {
                val lower = line.lowercase()
                val matchedLabel = labels.firstOrNull { lower.contains(it) } ?: continue

                val afterLabel = line.substringAfter(matchedLabel, "")
                    .substringAfter(":", afterLabel(line, matchedLabel))
                    .trim(' ', ':', '-', '=')
                val candidate = afterLabel.ifBlank {
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

        // Third pass: pattern-based extraction for common formats
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
