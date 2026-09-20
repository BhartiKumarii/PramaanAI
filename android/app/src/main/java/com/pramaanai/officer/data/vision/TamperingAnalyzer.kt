package com.pramaanai.officer.data.vision

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import com.pramaanai.officer.data.model.TamperingFindingItem
import com.pramaanai.officer.data.model.TamperingResult
import java.io.ByteArrayOutputStream
import kotlin.math.abs
import kotlin.math.sqrt

/**
 * On-device Error Level Analysis (ELA) — mirrors the backend's
 * app/services/tampering/pillow_provider.py. Re-compresses the image
 * at a lower JPEG quality and measures the per-block error between
 * original and re-compressed: regions that were previously edited
 * and re-saved show different error levels from untouched regions.
 *
 * Returns the same TamperingResult shape the backend expects in
 * ScreeningSubmission.tampering_result so the risk engine can score it.
 */
object TamperingAnalyzer {

    private const val ELA_QUALITY = 75
    private const val BLOCK_SIZE = 16
    private const val ANOMALY_THRESHOLD = 1.8

    fun analyze(bitmap: Bitmap): TamperingResult {
        val width = bitmap.width
        val height = bitmap.height
        if (width < BLOCK_SIZE * 2 || height < BLOCK_SIZE * 2) {
            return TamperingResult(
                tamperingRisk = 0.0,
                findings = listOf(
                    TamperingFindingItem(
                        type = "IMAGE_TOO_SMALL",
                        confidence = 0.0,
                        reason = "Image too small for ELA analysis (${width}x${height})",
                    )
                ),
            )
        }

        val originalGray = toGrayscale(bitmap)
        val recompressed = recompress(bitmap, ELA_QUALITY)
        val recompressedGray = toGrayscale(recompressed)
        recompressed.recycle()

        val blocksX = width / BLOCK_SIZE
        val blocksY = height / BLOCK_SIZE
        val blockErrors = DoubleArray(blocksX * blocksY)

        for (by in 0 until blocksY) {
            for (bx in 0 until blocksX) {
                var errorSum = 0.0
                val y0 = by * BLOCK_SIZE
                val x0 = bx * BLOCK_SIZE
                for (dy in 0 until BLOCK_SIZE) {
                    for (dx in 0 until BLOCK_SIZE) {
                        val idx = (y0 + dy) * width + (x0 + dx)
                        val diff = abs(originalGray[idx] - recompressedGray[idx])
                        errorSum += diff
                    }
                }
                blockErrors[by * blocksX + bx] = errorSum / (BLOCK_SIZE * BLOCK_SIZE)
            }
        }

        val meanError = blockErrors.average()
        val stdError = calculateStdDev(blockErrors, meanError)
        val threshold = meanError + ANOMALY_THRESHOLD * stdError

        var anomalousBlocks = 0
        var maxError = 0.0
        var maxBx = 0
        var maxBy = 0
        for (by in 0 until blocksY) {
            for (bx in 0 until blocksX) {
                val err = blockErrors[by * blocksX + bx]
                if (err > threshold) anomalousBlocks++
                if (err > maxError) {
                    maxError = err
                    maxBx = bx
                    maxBy = by
                }
            }
        }

        val totalBlocks = blocksX * blocksY
        val anomalyRatio = if (totalBlocks > 0) anomalousBlocks.toDouble() / totalBlocks else 0.0
        val tamperingRisk = (anomalyRatio * 0.6 + (maxError / 50.0).coerceAtMost(1.0) * 0.4)
            .coerceIn(0.0, 1.0)

        val findings = mutableListOf<TamperingFindingItem>()

        findings.add(
            TamperingFindingItem(
                type = "ELA_BLOCK_ANALYSIS",
                confidence = tamperingRisk,
                reason = "ELA over ${totalBlocks} blocks: mean_error=%.2f, std=%.2f, anomalous=%d/%d (%.1f%%), max_block_error=%.2f at block (%d,%d)".format(
                    meanError, stdError, anomalousBlocks, totalBlocks, anomalyRatio * 100, maxError, maxBx, maxBy
                ),
            )
        )

        if (anomalyRatio > 0.15) {
            findings.add(
                TamperingFindingItem(
                    type = "HIGH_ANOMALY_REGION",
                    confidence = anomalyRatio.coerceAtMost(1.0),
                    reason = "%.1f%% of image blocks show anomalous ELA error — possible localized editing".format(
                        anomalyRatio * 100
                    ),
                )
            )
        }

        return TamperingResult(
            tamperingRisk = tamperingRisk,
            findings = findings,
        )
    }

    private fun recompress(bitmap: Bitmap, quality: Int): Bitmap {
        val stream = ByteArrayOutputStream()
        bitmap.compress(Bitmap.CompressFormat.JPEG, quality, stream)
        val bytes = stream.toByteArray()
        return BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
    }

    private fun toGrayscale(bitmap: Bitmap): FloatArray {
        val w = bitmap.width
        val h = bitmap.height
        val pixels = IntArray(w * h)
        bitmap.getPixels(pixels, 0, w, 0, 0, w, h)
        return FloatArray(w * h) { i ->
            val p = pixels[i]
            0.299f * ((p shr 16) and 0xFF) + 0.587f * ((p shr 8) and 0xFF) + 0.114f * (p and 0xFF)
        }
    }

    private fun calculateStdDev(values: DoubleArray, mean: Double): Double {
        if (values.isEmpty()) return 0.0
        var sum = 0.0
        for (v in values) {
            val d = v - mean
            sum += d * d
        }
        return sqrt(sum / values.size)
    }
}
