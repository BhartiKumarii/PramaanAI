package com.pramaanai.officer.data.vision

import android.graphics.Bitmap

/**
 * Pre-OCR quality gate. Runs document detection + quality analysis and
 * decides whether the image is good enough for OCR and further processing.
 *
 * Returns an actionable verdict with specific guidance for the officer:
 * what to fix (hold steadier, reduce glare, improve lighting) rather
 * than a bare score.
 */
object ImageQualityGate {

    data class QualityVerdict(
        val pass: Boolean,
        val correctedBitmap: Bitmap?,
        val issues: List<String>,
        val metrics: OpenCVManager.QualityMetrics?,
        val alignmentScore: Float,
    )

    fun check(bitmap: Bitmap): QualityVerdict {
        val detection = OpenCVManager.detectDocument(bitmap)
        val metrics = detection.qualityMetrics
        val issues = mutableListOf<String>()

        if (metrics != null) {
            if (metrics.blurScore < 0.25f) {
                issues.add("Image is too blurry — hold the device steadier")
            }
            if (metrics.glareScore > 0.5f) {
                issues.add("Glare detected — tilt the document away from the light source")
            }
            if (metrics.lightingScore < 0.25f) {
                issues.add("Poor lighting — move to a brighter area or use the flash")
            }
            if (metrics.shadowScore > 0.6f) {
                issues.add("Heavy shadows on the document — adjust your position")
            }
        }

        if (detection.corners == null) {
            issues.add("Could not detect document edges — ensure the full document is visible")
        } else if (detection.alignmentScore < 0.3f) {
            issues.add("Document is tilted — try to keep it flat and centered")
        }

        val pass = issues.isEmpty()
        val useBitmap = if (pass && detection.correctedBitmap != null) {
            detection.correctedBitmap
        } else {
            null
        }

        return QualityVerdict(
            pass = pass,
            correctedBitmap = useBitmap,
            issues = issues,
            metrics = metrics,
            alignmentScore = detection.alignmentScore,
        )
    }
}
