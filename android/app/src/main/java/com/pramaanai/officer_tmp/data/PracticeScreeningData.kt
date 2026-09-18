package com.bordershield.officer.data

import com.bordershield.officer.data.model.FaceMatchResult
import com.bordershield.officer.data.model.IdentityGraphResult
import com.bordershield.officer.data.model.OcrResult
import com.bordershield.officer.data.model.RegistryHit
import com.bordershield.officer.data.model.RiskResult
import com.bordershield.officer.data.model.RiskSignalBreakdown
import com.bordershield.officer.data.model.ScreeningQueueItem
import com.bordershield.officer.data.model.ScreeningStatus
import com.bordershield.officer.data.model.TamperingFindingItem
import com.bordershield.officer.data.model.TamperingResult
import com.bordershield.officer.data.model.ValidationFinding
import com.bordershield.officer.data.model.ValidationResult

/** Static synthetic data for the first-login practice run — never sent to
 * the backend and never written to the local queue store. Includes one
 * EXACT and one FUZZY registry hit specifically so the guided tour has a
 * concrete, side-by-side example of the distinction instead of describing
 * it in the abstract. */
object PracticeScreeningData {
    val sample = ScreeningQueueItem(
        id = "practice-sample",
        travelerName = "TRAINING SAMPLE TRAVELER",
        documentType = "passport",
        nationality = "INDIAN",
        checkpoint = CHECKPOINT,
        submittedAt = System.currentTimeMillis(),
        status = ScreeningStatus.PENDING,
        ocr = OcrResult(
            documentType = "passport",
            fields = mapOf(
                "name" to "TRAINING SAMPLE TRAVELER",
                "passport_number" to "T0000001",
                "nationality" to "INDIAN",
                "date_of_birth" to "1990-01-01",
                "date_of_expiry" to "2030-01-01",
            ),
            ocrConfidence = 0.93,
        ),
        validation = ValidationResult(
            status = "PASS",
            findings = listOf(
                ValidationFinding("mrz_checksum_composite", "PASS", "LOW", "MRZ composite check digit valid (sample data)"),
                ValidationFinding("expiry", "PASS", "LOW", "document expiry 2030-01-01: not expired"),
            ),
        ),
        tampering = TamperingResult(
            tamperingRisk = 0.08,
            findings = listOf(TamperingFindingItem("ela", 0.08, "no significant compression anomaly detected (sample data)")),
        ),
        face = FaceMatchResult(match = true, similarity = 0.96, confidence = 0.96, reason = "cosine similarity 0.96 vs threshold 0.75: match (sample data)"),
        identityGraph = IdentityGraphResult(status = "NO_CLUSTER", clusterSize = 1, members = emptyList(), reason = "embedding matches only its own declared identity (sample data)"),
        deepfakeStatus = "ANALYZED",
        deepfakeReason = "heuristic frequency/noise analysis: low risk (sample data)",
        livenessStatus = "LIVE",
        livenessReason = "axis-aligned frequency ratio and sharpness within live range (sample data)",
        registryHits = listOf(
            RegistryHit(
                documentNumber = "T0000001",
                fullName = "TRAINING SAMPLE TRAVELER",
                registryReason = "sample overstay record",
                severity = "HIGH",
                matchType = "EXACT",
                confidence = 1.0,
            ),
            RegistryHit(
                documentNumber = "T9999999",
                fullName = "TRAINING SAMPLE TRAVELER",
                registryReason = "sample watchlist name-only record",
                severity = "MEDIUM",
                matchType = "FUZZY",
                confidence = 0.88,
            ),
        ),
        risk = RiskResult(
            score = 62,
            level = "HIGH_RISK",
            decision = "MANUAL_REVIEW",
            topReason = "hard override: EXACT blacklist hit on document number (sample data)",
            breakdown = listOf(
                RiskSignalBreakdown("blacklist", 0.18, 1.0, 0.18, "EXACT match on document_number (sample data)", null),
                RiskSignalBreakdown("checksum", 0.18, 0.0, 0.0, "all validation checks passed (sample data)", null),
                RiskSignalBreakdown("forensics", 0.18, 0.08, 0.014, "no significant compression anomaly detected (sample data)", null),
                RiskSignalBreakdown("face_match", 0.14, 0.04, 0.006, "cosine similarity 0.96 vs threshold 0.75: match (sample data)", null),
                RiskSignalBreakdown("liveness", 0.12, 0.05, 0.006, "live capture, low spoof risk (sample data)", null),
            ),
        ),
    )
}
