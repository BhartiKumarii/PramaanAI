package com.pramaanai.officer.data.vision

import android.graphics.Bitmap
import com.pramaanai.officer.data.remote.DeepfakeResult
import kotlin.math.abs
import kotlin.math.sqrt

/**
 * On-device deepfake/synthetic-image heuristic — mirrors the backend's
 * app/services/deepfake/heuristic_provider.py. Without an FFT library
 * on Android, this uses:
 *
 * 1. Laplacian variance per block as a proxy for frequency-domain energy
 *    distribution (real photos have uneven high-frequency content across
 *    regions; GAN outputs tend toward more uniform frequency profiles).
 * 2. Noise-residual uniformity: subtract a smoothed version of the image
 *    from the original, then measure block-wise std-dev of the residual
 *    (real sensor noise is spatially non-uniform; synthetic noise is
 *    often more homogeneous).
 *
 * Returns the same DeepfakeResult shape the backend expects in
 * ScreeningSubmission.deepfake_result.
 */
object DeepfakeAnalyzer {

    private const val BLOCK_SIZE = 16

    fun analyze(bitmap: Bitmap): DeepfakeResult {
        val width = bitmap.width
        val height = bitmap.height
        if (width < BLOCK_SIZE * 3 || height < BLOCK_SIZE * 3) {
            return DeepfakeResult(
                status = "ANALYZED",
                score = null,
                reason = "Image too small for frequency analysis (${width}x${height})",
            )
        }

        val gray = toGrayscale(bitmap, width, height)

        val freqScore = frequencyUniformityScore(gray, width, height)
        val noiseScore = noiseResidualScore(gray, width, height)

        val combinedRisk = (0.55 * freqScore + 0.45 * noiseScore).coerceIn(0.0, 1.0)

        val reason = buildString {
            append("On-device frequency+noise heuristic: ")
            append("frequency_uniformity=%.3f ".format(freqScore))
            append("(%.1f%% block Laplacian CV), ".format(freqScore * 100))
            append("noise_uniformity=%.3f ".format(noiseScore))
            append("(residual std-dev CV). ")
            append("Combined deepfake risk=%.3f. ".format(combinedRisk))
            if (combinedRisk < 0.3) append("Low synthetic-image risk.")
            else if (combinedRisk < 0.6) append("Moderate — officer review recommended.")
            else append("Elevated synthetic-image indicators.")
        }

        return DeepfakeResult(
            status = "ANALYZED",
            score = combinedRisk,
            reason = reason,
        )
    }

    /**
     * Measure how uniform the high-frequency energy is across blocks.
     * Real photos: uneven (textured areas vs. smooth skin vs. background).
     * GAN outputs: more uniform frequency profile.
     * Returns 0..1 where higher = more uniform = more suspicious.
     */
    private fun frequencyUniformityScore(gray: FloatArray, w: Int, h: Int): Double {
        val blocksX = w / BLOCK_SIZE
        val blocksY = h / BLOCK_SIZE
        if (blocksX < 2 || blocksY < 2) return 0.5

        val blockLaplacians = DoubleArray(blocksX * blocksY)

        for (by in 0 until blocksY) {
            for (bx in 0 until blocksX) {
                var laplacianSum = 0.0
                val y0 = by * BLOCK_SIZE
                val x0 = bx * BLOCK_SIZE
                for (dy in 1 until BLOCK_SIZE - 1) {
                    for (dx in 1 until BLOCK_SIZE - 1) {
                        val y = y0 + dy
                        val x = x0 + dx
                        val center = gray[y * w + x]
                        val lap = abs(
                            4 * center -
                            gray[(y - 1) * w + x] -
                            gray[(y + 1) * w + x] -
                            gray[y * w + (x - 1)] -
                            gray[y * w + (x + 1)]
                        )
                        laplacianSum += lap
                    }
                }
                blockLaplacians[by * blocksX + bx] =
                    laplacianSum / ((BLOCK_SIZE - 2) * (BLOCK_SIZE - 2))
            }
        }

        val mean = blockLaplacians.average()
        if (mean < 1e-6) return 0.5
        val std = stdDev(blockLaplacians, mean)
        val cv = std / mean

        // Low CV = uniform frequency = suspicious. Real photos typically CV > 0.6
        return (1.0 - (cv / 1.2).coerceAtMost(1.0)).coerceIn(0.0, 1.0)
    }

    /**
     * Noise-residual uniformity: subtract a local-mean-smoothed image,
     * then check how uniform the residual noise is across blocks.
     * Real sensor noise varies spatially; synthetic noise is more even.
     * Returns 0..1 where higher = more uniform residual = more suspicious.
     */
    private fun noiseResidualScore(gray: FloatArray, w: Int, h: Int): Double {
        val blocksX = w / BLOCK_SIZE
        val blocksY = h / BLOCK_SIZE
        if (blocksX < 2 || blocksY < 2) return 0.5

        // 3x3 box-filter smoothed image
        val smoothed = FloatArray(w * h)
        for (y in 1 until h - 1) {
            for (x in 1 until w - 1) {
                var sum = 0f
                for (dy in -1..1) {
                    for (dx in -1..1) {
                        sum += gray[(y + dy) * w + (x + dx)]
                    }
                }
                smoothed[y * w + x] = sum / 9f
            }
        }

        // Residual = original - smoothed
        val blockNoiseStds = DoubleArray(blocksX * blocksY)
        for (by in 0 until blocksY) {
            for (bx in 0 until blocksX) {
                val residuals = mutableListOf<Double>()
                val y0 = by * BLOCK_SIZE
                val x0 = bx * BLOCK_SIZE
                for (dy in 1 until BLOCK_SIZE - 1) {
                    for (dx in 1 until BLOCK_SIZE - 1) {
                        val idx = (y0 + dy) * w + (x0 + dx)
                        residuals.add((gray[idx] - smoothed[idx]).toDouble())
                    }
                }
                val mean = residuals.average()
                var variance = 0.0
                for (r in residuals) {
                    val d = r - mean
                    variance += d * d
                }
                blockNoiseStds[by * blocksX + bx] = sqrt(variance / residuals.size)
            }
        }

        val mean = blockNoiseStds.average()
        if (mean < 1e-6) return 0.5
        val std = stdDev(blockNoiseStds, mean)
        val cv = std / mean

        // Low CV in noise residual = synthetic-looking uniform noise
        return (1.0 - (cv / 0.8).coerceAtMost(1.0)).coerceIn(0.0, 1.0)
    }

    private fun toGrayscale(bitmap: Bitmap, w: Int, h: Int): FloatArray {
        val pixels = IntArray(w * h)
        bitmap.getPixels(pixels, 0, w, 0, 0, w, h)
        return FloatArray(w * h) { i ->
            val p = pixels[i]
            0.299f * ((p shr 16) and 0xFF) + 0.587f * ((p shr 8) and 0xFF) + 0.114f * (p and 0xFF)
        }
    }

    private fun stdDev(values: DoubleArray, mean: Double): Double {
        var sum = 0.0
        for (v in values) {
            val d = v - mean
            sum += d * d
        }
        return sqrt(sum / values.size)
    }
}
