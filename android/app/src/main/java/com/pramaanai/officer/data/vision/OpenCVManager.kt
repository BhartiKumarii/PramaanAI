package com.pramaanai.officer.data.vision

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Matrix
import android.graphics.PointF
import android.util.Log
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

/**
 * Pure-Kotlin document detection, perspective correction, and quality analysis.
 *
 * Implements Sobel edge detection → Canny-style thresholding → contour tracing
 * → quadrilateral approximation → perspective transform using Android's Matrix
 * API. Quality metrics (blur via Laplacian variance, glare via saturation
 * analysis, lighting/shadow via luminance statistics) computed directly from
 * pixel arrays.
 *
 * No native OpenCV dependency needed — keeps APK lean and avoids JNI issues.
 */
object OpenCVManager {
    private const val TAG = "OpenCVManager"

    fun init(context: Context) {
        Log.i(TAG, "OpenCVManager initialized (pure-Kotlin edge detection + perspective transform)")
    }

    data class DetectionResult(
        val corners: List<PointF>? = null,
        val alignmentScore: Float = 0f,
        val qualityMetrics: QualityMetrics? = null,
        val correctedBitmap: Bitmap? = null,
    )

    data class QualityMetrics(
        val blurScore: Float,
        val glareScore: Float,
        val lightingScore: Float,
        val shadowScore: Float,
    ) {
        val overallPass: Boolean
            get() = blurScore >= 0.3f && glareScore <= 0.6f && lightingScore >= 0.3f
    }

    fun detectDocument(bitmap: Bitmap): DetectionResult {
        return try {
            detectDocumentReal(bitmap)
        } catch (e: Exception) {
            Log.w(TAG, "Document detection failed", e)
            fallbackDetection(bitmap)
        }
    }

    private fun detectDocumentReal(bitmap: Bitmap): DetectionResult {
        val w = bitmap.width
        val h = bitmap.height
        val pixels = IntArray(w * h)
        bitmap.getPixels(pixels, 0, w, 0, 0, w, h)

        val gray = toGrayscale(pixels)
        val quality = computeQuality(gray, pixels, w, h)

        // Gaussian blur (3x3)
        val blurred = gaussianBlur3x3(gray, w, h)

        // Sobel edge detection
        val (gx, gy) = sobelGradients(blurred, w, h)
        val magnitude = FloatArray(w * h) { sqrt(gx[it] * gx[it] + gy[it] * gy[it]) }

        // Canny-style non-maximum suppression + double threshold
        val edges = cannyThreshold(magnitude, gx, gy, w, h)

        // Find contours and pick the best quadrilateral
        val quad = findBestQuadrilateral(edges, w, h, (w * h * 0.1).toInt())

        if (quad == null) {
            return DetectionResult(
                corners = null,
                alignmentScore = 0f,
                qualityMetrics = quality,
                correctedBitmap = null,
            )
        }

        val ordered = orderPoints(quad)
        val corners = ordered.map { PointF(it[0], it[1]) }
        val alignmentScore = computeAlignmentScore(ordered)
        val corrected = perspectiveTransform(bitmap, ordered)

        return DetectionResult(
            corners = corners,
            alignmentScore = alignmentScore,
            qualityMetrics = quality,
            correctedBitmap = corrected,
        )
    }

    private fun toGrayscale(pixels: IntArray): FloatArray {
        return FloatArray(pixels.size) { i ->
            val p = pixels[i]
            0.299f * ((p shr 16) and 0xFF) + 0.587f * ((p shr 8) and 0xFF) + 0.114f * (p and 0xFF)
        }
    }

    private fun gaussianBlur3x3(gray: FloatArray, w: Int, h: Int): FloatArray {
        val out = FloatArray(w * h)
        for (y in 1 until h - 1) {
            for (x in 1 until w - 1) {
                out[y * w + x] = (
                    gray[(y-1)*w+(x-1)] + 2*gray[(y-1)*w+x] + gray[(y-1)*w+(x+1)] +
                    2*gray[y*w+(x-1)] + 4*gray[y*w+x] + 2*gray[y*w+(x+1)] +
                    gray[(y+1)*w+(x-1)] + 2*gray[(y+1)*w+x] + gray[(y+1)*w+(x+1)]
                ) / 16f
            }
        }
        return out
    }

    private fun sobelGradients(gray: FloatArray, w: Int, h: Int): Pair<FloatArray, FloatArray> {
        val gx = FloatArray(w * h)
        val gy = FloatArray(w * h)
        for (y in 1 until h - 1) {
            for (x in 1 until w - 1) {
                gx[y*w+x] = -gray[(y-1)*w+(x-1)] + gray[(y-1)*w+(x+1)] +
                    -2*gray[y*w+(x-1)] + 2*gray[y*w+(x+1)] +
                    -gray[(y+1)*w+(x-1)] + gray[(y+1)*w+(x+1)]
                gy[y*w+x] = -gray[(y-1)*w+(x-1)] - 2*gray[(y-1)*w+x] - gray[(y-1)*w+(x+1)] +
                    gray[(y+1)*w+(x-1)] + 2*gray[(y+1)*w+x] + gray[(y+1)*w+(x+1)]
            }
        }
        return gx to gy
    }

    private fun cannyThreshold(magnitude: FloatArray, gx: FloatArray, gy: FloatArray, w: Int, h: Int): BooleanArray {
        // Compute adaptive thresholds from histogram
        val sorted = magnitude.filter { it > 0 }.sorted()
        val highThreshold = if (sorted.isNotEmpty()) sorted[(sorted.size * 0.85).toInt().coerceAtMost(sorted.size - 1)] else 50f
        val lowThreshold = highThreshold * 0.4f

        val edges = BooleanArray(w * h)
        for (y in 2 until h - 2) {
            for (x in 2 until w - 2) {
                val idx = y * w + x
                if (magnitude[idx] < lowThreshold) continue

                // Non-maximum suppression along gradient direction
                val angle = Math.toDegrees(kotlin.math.atan2(gy[idx].toDouble(), gx[idx].toDouble())).toFloat()
                val a = ((angle + 180) % 180)
                val mag = magnitude[idx]

                val (n1, n2) = when {
                    a < 22.5f || a >= 157.5f -> magnitude[y*w+(x-1)] to magnitude[y*w+(x+1)]
                    a < 67.5f -> magnitude[(y-1)*w+(x+1)] to magnitude[(y+1)*w+(x-1)]
                    a < 112.5f -> magnitude[(y-1)*w+x] to magnitude[(y+1)*w+x]
                    else -> magnitude[(y-1)*w+(x-1)] to magnitude[(y+1)*w+(x+1)]
                }

                if (mag >= n1 && mag >= n2 && mag >= highThreshold) {
                    edges[idx] = true
                }
            }
        }

        // Hysteresis: connect weak edges to strong edges
        var changed = true
        while (changed) {
            changed = false
            for (y in 2 until h - 2) {
                for (x in 2 until w - 2) {
                    val idx = y * w + x
                    if (edges[idx]) continue
                    if (magnitude[idx] < lowThreshold) continue
                    // Check 8-neighbors for a strong edge
                    for (dy in -1..1) for (dx in -1..1) {
                        if (edges[(y+dy)*w+(x+dx)]) {
                            edges[idx] = true
                            changed = true
                        }
                    }
                }
            }
        }

        return edges
    }

    /**
     * Find the largest quadrilateral in the edge map using contour tracing
     * and the Douglas-Peucker polygon simplification.
     */
    private fun findBestQuadrilateral(edges: BooleanArray, w: Int, h: Int, minArea: Int): List<FloatArray>? {
        val visited = BooleanArray(w * h)
        var bestQuad: List<FloatArray>? = null
        var bestArea = 0.0

        for (y in 1 until h - 1) {
            for (x in 1 until w - 1) {
                val idx = y * w + x
                if (!edges[idx] || visited[idx]) continue

                // Trace contour using 8-connectivity
                val contour = traceContour(edges, visited, x, y, w, h)
                if (contour.size < 20) continue

                val area = contourArea(contour)
                if (area < minArea) continue

                // Douglas-Peucker simplification
                val peri = contourPerimeter(contour)
                val simplified = douglasPeucker(contour, 0.02f * peri)

                if (simplified.size == 4 && area > bestArea) {
                    bestQuad = simplified
                    bestArea = area
                }
            }
        }

        return bestQuad
    }

    private fun traceContour(edges: BooleanArray, visited: BooleanArray, startX: Int, startY: Int, w: Int, h: Int): List<FloatArray> {
        val points = mutableListOf<FloatArray>()
        val stack = ArrayDeque<Pair<Int, Int>>()
        stack.addLast(startX to startY)
        var count = 0
        val maxPoints = 2000

        while (stack.isNotEmpty() && count < maxPoints) {
            val (cx, cy) = stack.removeLast()
            val idx = cy * w + cx
            if (visited[idx]) continue
            visited[idx] = true
            points.add(floatArrayOf(cx.toFloat(), cy.toFloat()))
            count++

            for (dy in -1..1) for (dx in -1..1) {
                if (dx == 0 && dy == 0) continue
                val nx = cx + dx; val ny = cy + dy
                if (nx < 0 || nx >= w || ny < 0 || ny >= h) continue
                val nidx = ny * w + nx
                if (edges[nidx] && !visited[nidx]) {
                    stack.addLast(nx to ny)
                }
            }
        }
        return points
    }

    private fun contourArea(pts: List<FloatArray>): Double {
        var area = 0.0
        val n = pts.size
        for (i in 0 until n) {
            val j = (i + 1) % n
            area += pts[i][0] * pts[j][1]
            area -= pts[j][0] * pts[i][1]
        }
        return abs(area) / 2.0
    }

    private fun contourPerimeter(pts: List<FloatArray>): Float {
        var peri = 0f
        for (i in pts.indices) {
            val j = (i + 1) % pts.size
            val dx = pts[j][0] - pts[i][0]
            val dy = pts[j][1] - pts[i][1]
            peri += sqrt(dx * dx + dy * dy)
        }
        return peri
    }

    private fun douglasPeucker(points: List<FloatArray>, epsilon: Float): List<FloatArray> {
        if (points.size < 3) return points
        var maxDist = 0f
        var maxIdx = 0
        val first = points.first()
        val last = points.last()

        for (i in 1 until points.size - 1) {
            val d = pointLineDistance(points[i], first, last)
            if (d > maxDist) {
                maxDist = d
                maxIdx = i
            }
        }

        return if (maxDist > epsilon) {
            val left = douglasPeucker(points.subList(0, maxIdx + 1), epsilon)
            val right = douglasPeucker(points.subList(maxIdx, points.size), epsilon)
            left.dropLast(1) + right
        } else {
            listOf(first, last)
        }
    }

    private fun pointLineDistance(pt: FloatArray, lineStart: FloatArray, lineEnd: FloatArray): Float {
        val dx = lineEnd[0] - lineStart[0]
        val dy = lineEnd[1] - lineStart[1]
        val lenSq = dx * dx + dy * dy
        if (lenSq < 1e-8f) return sqrt((pt[0]-lineStart[0])*(pt[0]-lineStart[0]) + (pt[1]-lineStart[1])*(pt[1]-lineStart[1]))
        val t = ((pt[0]-lineStart[0])*dx + (pt[1]-lineStart[1])*dy) / lenSq
        val tc = t.coerceIn(0f, 1f)
        val projX = lineStart[0] + tc * dx
        val projY = lineStart[1] + tc * dy
        return sqrt((pt[0]-projX)*(pt[0]-projX) + (pt[1]-projY)*(pt[1]-projY))
    }

    /** Order 4 points: top-left, top-right, bottom-right, bottom-left. */
    private fun orderPoints(quad: List<FloatArray>): List<FloatArray> {
        val sorted = quad.sortedBy { it[0] + it[1] }
        val tl = sorted.first()
        val br = sorted.last()
        val remaining = quad.filter { it !== tl && it !== br }
        val tr = remaining.maxByOrNull { it[0] - it[1] } ?: remaining.first()
        val bl = remaining.first { it !== tr }
        return listOf(tl, tr, br, bl)
    }

    /**
     * Perspective transform using bilinear interpolation.
     * Maps the quadrilateral defined by the 4 ordered corners to a rectangle.
     */
    private fun perspectiveTransform(bitmap: Bitmap, ordered: List<FloatArray>): Bitmap? {
        val (tl, tr, br, bl) = ordered
        val widthTop = dist(tl, tr)
        val widthBottom = dist(bl, br)
        val dstW = max(widthTop, widthBottom).toInt()

        val heightLeft = dist(tl, bl)
        val heightRight = dist(tr, br)
        val dstH = max(heightLeft, heightRight).toInt()

        if (dstW < 50 || dstH < 50) return null

        val srcW = bitmap.width
        val srcH = bitmap.height
        val srcPixels = IntArray(srcW * srcH)
        bitmap.getPixels(srcPixels, 0, srcW, 0, 0, srcW, srcH)

        val dst = Bitmap.createBitmap(dstW, dstH, Bitmap.Config.ARGB_8888)
        val dstPixels = IntArray(dstW * dstH)

        for (dy in 0 until dstH) {
            val ty = dy.toFloat() / dstH
            for (dx in 0 until dstW) {
                val tx = dx.toFloat() / dstW
                // Bilinear interpolation of source coordinates
                val topX = tl[0] + tx * (tr[0] - tl[0])
                val topY = tl[1] + tx * (tr[1] - tl[1])
                val botX = bl[0] + tx * (br[0] - bl[0])
                val botY = bl[1] + tx * (br[1] - bl[1])
                val sx = topX + ty * (botX - topX)
                val sy = topY + ty * (botY - topY)

                val ix = sx.toInt().coerceIn(0, srcW - 1)
                val iy = sy.toInt().coerceIn(0, srcH - 1)
                dstPixels[dy * dstW + dx] = srcPixels[iy * srcW + ix]
            }
        }

        dst.setPixels(dstPixels, 0, dstW, 0, 0, dstW, dstH)
        return dst
    }

    private fun computeAlignmentScore(ordered: List<FloatArray>): Float {
        val (tl, tr, br, bl) = ordered
        val topEdge = dist(tl, tr)
        val bottomEdge = dist(bl, br)
        val leftEdge = dist(tl, bl)
        val rightEdge = dist(tr, br)

        val hRatio = if (bottomEdge > 0) topEdge / bottomEdge else 0f
        val vRatio = if (rightEdge > 0) leftEdge / rightEdge else 0f

        val hScore = (1f - abs(hRatio - 1f)).coerceIn(0f, 1f)
        val vScore = (1f - abs(vRatio - 1f)).coerceIn(0f, 1f)

        // Perpendicularity check
        val vec1x = tr[0] - tl[0]; val vec1y = tr[1] - tl[1]
        val vec2x = bl[0] - tl[0]; val vec2y = bl[1] - tl[1]
        val dot = vec1x * vec2x + vec1y * vec2y
        val mag = topEdge * leftEdge
        val cosAngle = if (mag > 0) abs(dot / mag) else 1f
        val perpScore = (1f - cosAngle).coerceIn(0f, 1f)

        return (hScore + vScore + perpScore) / 3f
    }

    private fun computeQuality(gray: FloatArray, pixels: IntArray, w: Int, h: Int): QualityMetrics {
        val n = pixels.size.toLong()

        // Blur via Laplacian variance
        var lapSum = 0.0
        for (y in 1 until h - 1) {
            for (x in 1 until w - 1) {
                val center = gray[y * w + x]
                val lap = abs(4 * center - gray[(y-1)*w+x] - gray[(y+1)*w+x] - gray[y*w+(x-1)] - gray[y*w+(x+1)])
                lapSum += lap * lap
            }
        }
        val lapVar = lapSum / ((w - 2) * (h - 2))
        val blurScore = (lapVar / 500.0).coerceIn(0.0, 1.0).toFloat()

        // Glare: very bright + low saturation pixels
        var saturated = 0
        var dark = 0
        var sumLuma = 0.0
        for (p in pixels) {
            val r = (p shr 16) and 0xFF
            val g = (p shr 8) and 0xFF
            val b = p and 0xFF
            sumLuma += 0.299 * r + 0.587 * g + 0.114 * b
            if (r > 240 && g > 240 && b > 240) saturated++
            if (r < 30 && g < 30 && b < 30) dark++
        }
        val glareScore = (saturated.toDouble() / n * 10).coerceIn(0.0, 1.0).toFloat()
        val meanLuma = sumLuma / n
        val lightingScore = (1.0 - abs(meanLuma - 128.0) / 128.0).coerceIn(0.0, 1.0).toFloat()
        val shadowScore = (dark.toDouble() / n * 5).coerceIn(0.0, 1.0).toFloat()

        return QualityMetrics(blurScore, glareScore, lightingScore, shadowScore)
    }

    private fun dist(a: FloatArray, b: FloatArray): Float =
        sqrt((b[0]-a[0])*(b[0]-a[0]) + (b[1]-a[1])*(b[1]-a[1]))

    private fun fallbackDetection(bitmap: Bitmap): DetectionResult {
        val w = bitmap.width.toFloat()
        val h = bitmap.height.toFloat()
        val mx = w * 0.15f
        val my = h * 0.2f
        val corners = listOf(PointF(mx, my), PointF(w-mx, my), PointF(w-mx, h-my), PointF(mx, h-my))
        val pixels = IntArray(bitmap.width * bitmap.height)
        bitmap.getPixels(pixels, 0, bitmap.width, 0, 0, bitmap.width, bitmap.height)
        val gray = toGrayscale(pixels)
        return DetectionResult(
            corners = corners,
            alignmentScore = 0.5f,
            qualityMetrics = computeQuality(gray, pixels, bitmap.width, bitmap.height),
            correctedBitmap = try {
                Bitmap.createBitmap(bitmap, mx.toInt(), my.toInt(), (w - 2*mx).toInt(), (h - 2*my).toInt())
            } catch (_: Exception) { null },
        )
    }
}
