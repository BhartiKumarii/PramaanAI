package com.pramaanai.officer.data

import com.pramaanai.officer.data.model.ScreeningStatus

// ── Status labels ─────────────────────────────────────────────────────────────

fun ScreeningStatus.humanLabel(): String = when (this) {
    ScreeningStatus.PENDING        -> "Awaiting Submission"
    ScreeningStatus.CLEARED        -> "Verified"
    ScreeningStatus.DISPUTED       -> "Referred for Review"
    ScreeningStatus.SENT           -> "Submitted for Admin Review"
    ScreeningStatus.OFFLINE_QUEUED -> "Saved — will sync when online"
}

// ── Risk level labels ─────────────────────────────────────────────────────────

fun humanRiskLabel(level: String?): String = when (level) {
    "HIGH_RISK"   -> "High Risk — Review Required"
    "MEDIUM_RISK" -> "Review Recommended"
    "LOW_RISK"    -> "No Issues Detected"
    null          -> "Analysis Pending"
    else          -> level.replace("_", " ")
}

// ── Signal (check name) labels ────────────────────────────────────────────────

fun humanSignalTitle(signal: String): String = when (signal) {
    "checksum"           -> "Document Validity"
    "forensics"          -> "Document Appearance"
    "face_match"         -> "Photo Comparison"
    "face_detection"     -> "Photo Quality"
    "deepfake"           -> "Photo Authenticity"
    "liveness"           -> "Live Person Check"
    "blacklist"          -> "Security Records"
    "identity_graph"     -> "Identity Records"
    "duplicate_document" -> "Document History"
    "citizen_registry"   -> "Identity Database"
    else                 -> signal.replace("_", " ").replaceFirstChar { it.uppercase() }
}

// ── Top reason → plain language ───────────────────────────────────────────────

fun humanTopReason(raw: String?): String {
    if (raw.isNullOrBlank()) return "Analysis complete — review findings below"
    val lower = raw.lowercase()
    return when {
        lower.contains("expir") && lower.contains("expired") ->
            extractExpiryReason(raw)
        lower.contains("blacklist") || lower.contains("watchlist") ->
            "Security alert — document flagged in records"
        lower.contains("multi-identity") || lower.contains("cluster") ->
            "Similar identity found in other records"
        lower.contains("face") && lower.contains("mismatch") ->
            "Photo does not match document"
        lower.contains("cosine similarity") || lower.contains("similarity") && lower.contains("threshold") ->
            humaniseSimilarityReason(raw)
        lower.contains("hologram") ->
            "Document security feature appears altered"
        lower.contains("stamp opacity") || lower.contains("ink application") ->
            "Document stamp or ink appears inconsistent"
        lower.contains("character misalign") || lower.contains("text editing") ->
            "Text irregularity detected on document"
        lower.contains("font inconsistenc") || lower.contains("font") ->
            "Document font inconsistency detected"
        lower.contains("mrz") && lower.contains("fail") ->
            "Machine-readable zone check failed"
        lower.contains("check digit") && lower.contains("fail") ->
            "Document data contains an error — check digit failed"
        lower.contains("no face") || lower.contains("no faces") ->
            "No face detected in photo — retake required"
        lower.contains("multiple face") ->
            "Multiple faces in photo — retake with one person only"
        lower.contains("deepfake") || lower.contains("synthetic") ->
            "Photo authenticity concern — may need retake"
        lower.contains("liveness") || lower.contains("spoof") ->
            "Live person check concern — retake photo directly"
        lower.contains("duplic") ->
            "This document number was already seen in another case"
        lower.contains("mismatch") ->
            "Document details do not match records"
        lower.contains("revoked") ->
            "Document has been cancelled or revoked"
        lower.contains("hard override") ->
            humanTopReason(raw.substringAfter("hard override:").trim())
        else -> shortenRawReason(raw)
    }
}

private fun extractExpiryReason(raw: String): String {
    val dateRegex = Regex("""(\d{4}-\d{2}-\d{2})""")
    val dates = dateRegex.findAll(raw).map { it.value }.toList()
    return if (dates.isNotEmpty()) {
        val expiry = dates[0]
        val parts = expiry.split("-")
        if (parts.size == 3) "Document expired ${parts[2]}/${parts[1]}/${parts[0]}"
        else "Document has expired"
    } else "Document has expired"
}

private fun humaniseSimilarityReason(raw: String): String {
    val sim = Regex("""similarity\s+([\d.]+)""").find(raw)?.groupValues?.getOrNull(1)?.toDoubleOrNull()
    return if (sim != null) {
        val pct = (sim * 100).toInt()
        when {
            pct >= 75 -> "Photo matches document ($pct% match strength)"
            pct >= 50 -> "Partial photo match ($pct%) — manual check recommended"
            else      -> "Photo does not match document ($pct% similarity)"
        }
    } else "Photo comparison concern"
}

private fun shortenRawReason(raw: String): String {
    // Strip technical prefixes and truncate to readable length
    val cleaned = raw
        .removePrefix("hard override: ")
        .removePrefix("forensics: ")
        .removePrefix("checksum: ")
        .removePrefix("blacklist: ")
        .replaceFirstChar { it.uppercase() }
    return if (cleaned.length > 80) cleaned.take(77) + "…" else cleaned
}

// ── Signal reason → plain language ───────────────────────────────────────────

fun humanSignalReason(signal: String, raw: String?): String {
    if (raw.isNullOrBlank()) return "Check complete"
    val lower = raw.lowercase()
    return when (signal) {
        "forensics" -> when {
            lower.contains("hologram")              -> "Security hologram appears missing or altered"
            lower.contains("stamp opacity")         -> "Stamp ink appears inconsistent — possible alteration"
            lower.contains("character misalign")    -> "Text on document has irregularities"
            lower.contains("ela")                   -> "Document image analysis detected possible editing"
            lower.contains("authentic")             -> "Document appearance concern detected"
            else                                     -> "Document appearance requires physical examination"
        }
        "face_match" -> when {
            lower.contains("below threshold") || lower.contains("no match") ->
                humaniseSimilarityReason(raw)
            lower.contains("above threshold") || lower.contains("match") ->
                "Photo is consistent with document"
            else -> "Photo comparison inconclusive"
        }
        "deepfake" -> when {
            lower.contains("0.") && lower.contains("probability") -> {
                val score = Regex("""probability:\s*([\d.]+)""").find(raw)?.groupValues?.getOrNull(1)?.toDoubleOrNull()
                if (score != null && score > 0.5) "Photo authenticity concern" else "Photo appears authentic"
            }
            else -> "Photo authenticity check complete"
        }
        "liveness" -> when {
            lower.contains("spoof") || lower.contains("artificial") ->
                "Photo may be from a screen or printed image"
            lower.contains("live")  -> "Live person confirmed"
            else                    -> "Live person check result inconclusive"
        }
        "checksum" -> when {
            lower.contains("expir") -> extractExpiryReason(raw)
            lower.contains("pass")  -> "Document data checks passed"
            lower.contains("fail")  -> "Document data check failed"
            lower.contains("match") -> "Document field matches records"
            lower.contains("mismatch") -> "Document field does not match records"
            else                    -> shortenRawReason(raw)
        }
        "blacklist" -> when {
            lower.contains("no") && lower.contains("hit") -> "No security alerts found"
            lower.contains("hit") || lower.contains("found") ->
                "Security alert — document is flagged in records"
            else -> shortenRawReason(raw)
        }
        "identity_graph" -> when {
            lower.contains("cluster") ->
                "Similar identity found in ${extractClusterSize(raw)} other record(s)"
            lower.contains("no cluster") -> "No related identity records found"
            else -> shortenRawReason(raw)
        }
        "face_detection" -> when {
            lower.contains("no face") -> "No face detected in photo — retake required"
            lower.contains("multiple") -> "Multiple faces in photo — retake with one person only"
            lower.contains("single") || lower.contains("detected") -> "Face detected in photo"
            else -> shortenRawReason(raw)
        }
        "citizen_registry" -> when {
            lower.contains("match") && !lower.contains("mis") -> "Document details match our records"
            lower.contains("mismatch") -> "Document details do not match records"
            lower.contains("no record") -> "No record found in database"
            lower.contains("revoked") || lower.contains("expired") -> "Document status: cancelled or expired"
            else -> shortenRawReason(raw)
        }
        "duplicate_document" -> when {
            lower.contains("no") && lower.contains("match") -> "No duplicate document found"
            lower.contains("match") || lower.contains("seen") ->
                "This document number was already seen in another case"
            else -> shortenRawReason(raw)
        }
        else -> shortenRawReason(raw)
    }
}

private fun extractClusterSize(raw: String): String {
    val n = Regex("""(\d+)\s+face""").find(raw)?.groupValues?.getOrNull(1)
    return n ?: "multiple"
}

// ── Validation finding reason → plain language ──────────────────────────────

fun humanValidationReason(check: String, raw: String?): String {
    if (raw.isNullOrBlank()) return "Check complete"
    val lower = raw.lowercase()
    return when {
        lower.contains("expir") && lower.contains("expired") -> extractExpiryReason(raw)
        lower.contains("check digit") && lower.contains("fail") -> "Document data check failed — a digit does not match"
        lower.contains("mrz") && lower.contains("fail") -> "Machine-readable zone check failed"
        lower.contains("mrz") && lower.contains("pass") -> "Machine-readable zone verified"
        lower.contains("checksum") && lower.contains("fail") -> "Document data integrity check failed"
        lower.contains("checksum") && lower.contains("pass") -> "Document data integrity verified"
        lower.contains("mismatch") -> "Document field does not match expected value"
        lower.contains("match") && !lower.contains("mis") -> "Document field matches records"
        lower.contains("valid") && lower.contains("pass") -> "Document validity confirmed"
        lower.contains("revoked") || lower.contains("cancel") -> "Document has been cancelled or revoked"
        else -> shortenRawReason(raw)
    }
}

// ── Source label → plain language ────────────────────────────────────────────

fun humanSourceLabel(signal: String): String = when (signal) {
    "checksum" -> "Document Validity Check"
    "forensics" -> "Document Appearance Analysis"
    "deepfake" -> "Photo Authenticity Check"
    "liveness" -> "Live Person Verification"
    "blacklist" -> "Security Records Database"
    "face_match" -> "Photo Comparison Service"
    "identity_graph" -> "Identity Records Analysis"
    "face_detection" -> "Photo Quality Check"
    "citizen_registry" -> "Identity Database Lookup"
    "duplicate_document" -> "Document History Check"
    else -> signal.replace("_", " ").replaceFirstChar { it.uppercase() }
}
