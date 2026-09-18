package com.bordershield.officer.data

import com.bordershield.officer.data.model.LocationBox
import com.bordershield.officer.data.model.RegistryHit
import com.bordershield.officer.data.model.RiskResult
import com.bordershield.officer.data.model.RiskSignalBreakdown
import com.bordershield.officer.data.model.ScreeningQueueItem
import com.bordershield.officer.data.model.ScreeningStatus

/** Placeholder queue data for Phase 2 — matches the shape of the real
 * backend's /documents/screen response so Phase 3 only has to replace the
 * data source, not the UI or the domain model. */
object MockScreenings {

    val all: List<ScreeningQueueItem> = listOf(
        ScreeningQueueItem(
            id = "mock-1",
            travelerName = "Ravi Kumar Sharma",
            documentType = "passport",
            nationality = "INDIAN",
            checkpoint = "Attari-Wagah ICP",
            submittedAt = System.currentTimeMillis() - 1_000 * 60 * 4,
            status = ScreeningStatus.PENDING,
            risk = RiskResult(
                score = 14,
                level = "LOW_RISK",
                decision = "CLEAR",
                topReason = "forensics: no significant compression anomaly detected",
                breakdown = listOf(
                    RiskSignalBreakdown("checksum", 0.2353, 0.0, 0.0, "all validation checks passed", null),
                    RiskSignalBreakdown("forensics", 0.2353, 0.08, 0.0188, "grid cell (40,60)-(90,110) mean ELA intensity 0.21, z-score 0.6", LocationBox(40, 60, 90, 110)),
                    RiskSignalBreakdown("blacklist", 0.2353, 0.0, 0.0, "no registry hits", null),
                    RiskSignalBreakdown("face_match", 0.1765, 0.05, 0.0088, "cosine similarity 0.95 vs threshold 0.75: match", null),
                    RiskSignalBreakdown("identity_graph", 0.1176, 0.0, 0.0, "embedding matches only its own declared identity", null),
                ),
            ),
            registryHits = emptyList(),
        ),
        ScreeningQueueItem(
            id = "mock-2",
            travelerName = "Mohammed Asif Khan",
            documentType = "passport",
            nationality = "PAKISTANI",
            checkpoint = "Attari-Wagah ICP",
            submittedAt = System.currentTimeMillis() - 1_000 * 60 * 11,
            status = ScreeningStatus.PENDING,
            risk = RiskResult(
                score = 82,
                level = "HIGH_RISK",
                decision = "MANUAL_REVIEW",
                topReason = "hard override: EXACT blacklist hit on 'MOHAMMED ASIF KHAN' (overstay violation on prior crossing)",
                breakdown = listOf(
                    RiskSignalBreakdown("blacklist", 0.2353, 1.0, 0.2353, "EXACT match on document_number vs registry entry 'MOHAMMED ASIF KHAN' (overstay violation), confidence 1.0", null),
                    RiskSignalBreakdown("checksum", 0.2353, 0.0, 0.0, "all validation checks passed", null),
                    RiskSignalBreakdown("forensics", 0.2353, 0.12, 0.0282, "grid cell (200,140)-(250,190) mean ELA intensity 0.34, z-score 1.1", LocationBox(200, 140, 250, 190)),
                    RiskSignalBreakdown("face_match", 0.1765, 0.09, 0.0159, "cosine similarity 0.91 vs threshold 0.75: match", null),
                    RiskSignalBreakdown("identity_graph", 0.1176, 0.0, 0.0, "embedding matches only its own declared identity", null),
                ),
            ),
            registryHits = listOf(
                RegistryHit("X1122334", "MOHAMMED ASIF KHAN", "overstay violation on prior crossing", "HIGH", "EXACT", 1.0),
            ),
        ),
        ScreeningQueueItem(
            id = "mock-3",
            travelerName = "Sita Devi Thapa",
            documentType = "national_id",
            nationality = "NEPALI",
            checkpoint = "Raxaul ICP (visa-exempt)",
            submittedAt = System.currentTimeMillis() - 1_000 * 60 * 22,
            status = ScreeningStatus.PENDING,
            risk = RiskResult(
                score = 47,
                level = "MEDIUM_RISK",
                decision = "MANUAL_REVIEW",
                topReason = "blacklist: FUZZY match on full_name vs registry entry 'SITA DEVI THAPA' (watchlist), confidence 0.91",
                breakdown = listOf(
                    RiskSignalBreakdown("blacklist", 0.2353, 0.5, 0.1176, "FUZZY match on full_name vs registry entry 'SITA DEVI THAPA' (watchlist — prior smuggling investigation), confidence 0.91 (0.5x fuzzy multiplier applied)", null),
                    RiskSignalBreakdown("checksum", 0.2353, 0.3, 0.0706, "expiry: document expiry 2026-10-01 vs today: not expired — low severity note on stay-duration field", null),
                    RiskSignalBreakdown("forensics", 0.2353, 0.18, 0.0424, "grid cell (10,10)-(60,60) mean ELA intensity 0.4, z-score 1.4", LocationBox(10, 10, 60, 60)),
                    RiskSignalBreakdown("face_match", 0.1765, 0.15, 0.0265, "cosine similarity 0.85 vs threshold 0.75: match", null),
                    RiskSignalBreakdown("identity_graph", 0.1176, 0.0, 0.0, "embedding matches only its own declared identity", null),
                ),
            ),
            registryHits = listOf(
                RegistryHit("B9988001", "SITA DEVI THAPA", "watchlist — prior smuggling investigation", "HIGH", "FUZZY", 0.91),
            ),
        ),
        ScreeningQueueItem(
            id = "mock-4",
            travelerName = "John Michael Smith",
            documentType = "passport",
            nationality = "AMERICAN",
            checkpoint = "Petrapole ICP",
            submittedAt = System.currentTimeMillis() - 1_000 * 60 * 35,
            status = ScreeningStatus.CLEARED,
            risk = RiskResult(
                score = 8,
                level = "LOW_RISK",
                decision = "CLEAR",
                topReason = "checksum: all validation checks passed",
                breakdown = listOf(
                    RiskSignalBreakdown("checksum", 0.2353, 0.0, 0.0, "all validation checks passed, MRZ composite check digit valid", null),
                    RiskSignalBreakdown("forensics", 0.2353, 0.03, 0.007, "grid cell (5,5)-(50,50) mean ELA intensity 0.1, z-score 0.2", LocationBox(5, 5, 50, 50)),
                    RiskSignalBreakdown("blacklist", 0.2353, 0.0, 0.0, "no registry hits", null),
                    RiskSignalBreakdown("face_match", 0.1765, 0.02, 0.0035, "cosine similarity 0.98 vs threshold 0.75: match", null),
                    RiskSignalBreakdown("identity_graph", 0.1176, 0.0, 0.0, "embedding matches only its own declared identity", null),
                ),
            ),
            registryHits = emptyList(),
        ),
    )
}
