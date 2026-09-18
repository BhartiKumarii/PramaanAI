package com.pramaanai.officer.data.vision

import android.content.Context
import android.graphics.Bitmap
import android.graphics.PointF
import android.util.Log
import kotlin.math.abs

/**
 * OpenCV-based document detection and quality analysis.
 *
 * This provides on-device document edge detection, four-corner detection,
 * alignment checking, and quality metrics (blur, glare, lighting, shadows).
 *
 * In production, this would use OpenCV via JNI. For this build, we provide
 * a pure-Kotlin fallback using simple image analysis heuristics that
 * approximates the same outputs — suitable for demo/testing and as a
 * baseline before integrating the native OpenCV library.
 */
object OpenCVManager {
    private const val TAG = "OpenCVManager"

    /** Initialize OpenCV library. In this fallback, just logs readiness. */
    fun init(context: Context) {
        Log.i(TAG, "OpenCVManager initialized (pure-Kotlin fallback)")
    }

    /** Result of document detection. */
    data class DetectionResult(
        val corners: List<PointF>? = null,
        val alignmentScore: Float = 0f,
        val qualityMetrics: QualityMetrics? = null,
        val correctedBitmap: Bitmap? = null,
    )

    /** Quality metrics for the captured document image. */
    data class QualityMetrics(
        val blurScore: Float,
        val glareScore: Float,
        val lightingScore: Float,
        val shadowScore: Float,
    )

    /**
     * Detect document in bitmap and return corners, alignment score, quality metrics,
     * and a perspective-corrected bitmap.
     */
    fun detectDocument(bitmap: Bitmap): DetectionResult {
        val width = bitmap.width.toFloat()
        val height = bitmap.height.toFloat()

        // Simple heuristic: assume document occupies center 70% of frame
        // In real OpenCV implementation, this would use contour detection
        val marginX = width * 0.15f
        val marginY = height * 0.2f
        val corners = listOf(
            PointF(marginX, marginY),
            PointF(width - marginX, marginY),
            PointF(width - marginX, height - marginY),
            PointF(marginX, height - marginY),
        )

        // Compute quality metrics from pixel analysis
        val qualityMetrics = computeQualityMetrics(bitmap)

        // Alignment score based on how rectangular the detected corners are
        val alignmentScore = computeAlignmentScore(corners, width, height)

        // Create corrected (perspective-transformed) bitmap
        val correctedBitmap = createCorrectedBitmap(bitmap, corners)

        return DetectionResult(
            corners = corners,
            alignmentScore = alignmentScore,
            qualityMetrics = qualityMetrics,
            correctedBitmap = correctedBitmap,
        )
    }

    private fun computeQualityMetrics(bitmap: Bitmap): QualityMetrics {
        val width = bitmap.width
        val height = bitmap.height
        val pixels = IntArray(width * height)
        bitmap.getPixels(pixels, 0, width, 0, 0, width, height)

        var sumLuma = 0L
        var sumLumaSq = 0L
        var saturatedCount = 0
        var darkCount = 0
        val totalPixels = pixels.size.toLong()

        for (p in pixels) {
            val r = (p shr 16) and 0xFF
            val g = (p shr 8) and 0xFF
            val b = p and 0xFF
            val luma = (0.299 * r + 0.587 * g + 0.114 * b).toLong()
            sumLuma += luma
            sumLumaSq += luma * luma
            if (r > 240 && g > 240 && b > 240) saturatedCount++
            if (r < 30 && g < 30 && b < 30) darkCount++
        }

        val meanLuma = sumLuma.toDouble() / totalPixels
        val variance = (sumLumaSq.toDouble() / totalPixels) - (meanLuma * meanLuma)
        val stdDev = Math.sqrt(variance)

        // Blur: low variance = blurry (normalized 0-1, higher = sharper)
        val blurScore = (stdDev / 64.0).coerceIn(0.0, 1.0).toFloat()

        // Glare: high saturation ratio = glare (normalized 0-1, higher = more glare)
        val glareScore = (saturatedCount.toDouble() / totalPixels * 10).coerceIn(0.0, 1.0).toFloat()

        // Lighting: mean luminance in good range (normalized 0-1, higher = better)
        val lightingScore = (1.0 - abs(meanLuma - 128.0) / 128.0).coerceIn(0.0, 1.0).toFloat()

        // Shadows: dark pixel ratio (normalized 0-1, higher = more shadows)
        val shadowScore = (darkCount.toDouble() / totalPixels * 5).coerceIn(0.0, 1.0).toFloat()

        return QualityMetrics(
            blurScore = blurScore,
            glareScore = glareScore,
            lightingScore = lightingScore,
            shadowScore = shadowScore,
        )
    }

    private fun computeAlignmentScore(
        corners: List<PointF>,
        width: Float,
        height: Float,
    ): Float {
        if (corners.size != 4) return 0f

        // Check if corners form a roughly rectangular shape
        val c0 = corners[0]
        val c1 = corners[1]
        val c2 = corners[2]
        val c3 = corners[3]

        // Edge lengths
        val topEdge = distance(c0, c1)
        val rightEdge = distance(c1, c2)
        val bottomEdge = distance(c3, c2)
        val leftEdge = distance(c0, c3)

        // Aspect ratio consistency
        val hRatio = if (bottomEdge > 0) topEdge / bottomEdge else 0f
        val vRatio = if (rightEdge > 0) leftEdge / rightEdge else 0f

        val hScore = (1f - abs(hRatio - 1f)).coerceIn(0f, 1f)
        val vScore = (1f - abs(vRatio - 1f)).coerceIn(0f, 1f)

        // Check if document fills reasonable portion of frame
        val docWidth = (topEdge + bottomEdge) / 2
        val docHeight = (leftEdge + rightEdge) / 2
        val fillRatio = (docWidth * docHeight) / (width * height)
        val fillScore = if (fillRatio > 0.3 && fillRatio < 0.9) 1f else (fillRatio / 0.3).coerceIn(0.0, 1.0).toFloat()

        return (hScore + vScore + fillScore) / 3f
    }

    private fun distance(p1: PointF, p2: PointF): Float {
        val dx = p2.x - p1.x
        val dy = p2.y - p1.y
        return kotlin.math.sqrt(dx * dx + dy * dy).toFloat()
    }

    private fun createCorrectedBitmap(
        bitmap: Bitmap,
        corners: List<PointF>,
    ): Bitmap? {
        if (corners.size != 4) return null

        // Simple crop to the detected region (in production, use perspective transform)
        val minX = corners.minByOrNull { it.x }?.x?.toInt() ?: 0
        val maxX = corners.maxByOrNull { it.x }?.x?.toInt() ?: bitmap.width
        val minY = corners.minByOrNull { it.y }?.y?.toInt() ?: 0
        val maxY = corners.maxByOrNull { it.y }?.y?.toInt() ?: bitmap.height

        val cropWidth = (maxX - minX).coerceIn(1, bitmap.width)
        val cropHeight = (maxY - minY).coerceIn(1, bitmap.height)

        return try {
            Bitmap.createBitmap(bitmap, minX, minY, cropWidth, cropHeight)
        } catch (e: Exception) {
            Log.w(TAG, "Failed to create corrected bitmap", e)
            null
        }
    }
}