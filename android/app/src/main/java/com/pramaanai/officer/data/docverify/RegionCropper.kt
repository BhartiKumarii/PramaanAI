package com.pramaanai.officer.data.docverify

import android.graphics.Bitmap
import android.graphics.Rect
import android.util.Base64
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import kotlinx.coroutines.suspendCancellableCoroutine
import java.io.ByteArrayOutputStream
import kotlin.coroutines.resume
import kotlin.math.max
import kotlin.math.min

/** Turns on-device detections into the padded REGION CROPS the server
 * accepts. The full image is never sent: crops are limited to located
 * regions (plus ML Kit text blocks, so the server can read printed fields),
 * and the union of crops is kept under [MAX_COVERAGE] of the frame — the
 * server enforces the same rule and rejects a whole-image upload. */
object RegionCropper {
    const val MAX_COVERAGE = 0.85
    private const val REGION_PAD_FRACTION = 0.40f  // forensics compares a region with its surroundings
    private const val TEXT_PAD_PX = 6

    data class Prepared(val crops: List<RegionCrop>, val coverage: Double, val droppedTextBlocks: Int)

    /** What the phone's own OCR read: paragraph blocks (sent as "text" crops)
     * and individual lines (sent as device_text, and shown to the officer in
     * the Extraction step before anything leaves the phone). */
    data class OnDeviceText(val blocks: List<Rect>, val lines: List<DeviceTextLine>)

    suspend fun readText(bitmap: Bitmap): OnDeviceText = suspendCancellableCoroutine { cont ->
        TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
            .process(InputImage.fromBitmap(bitmap, 0))
            .addOnSuccessListener { text ->
                val lines = text.textBlocks.flatMap { b -> b.lines }.mapNotNull { l ->
                    val r = l.boundingBox ?: return@mapNotNull null
                    if (l.text.isBlank()) null
                    else DeviceTextLine(0, l.text.trim().take(300), listOf(r.left, r.top, r.right, r.bottom),
                        (l.confidence.takeIf { it > 0f } ?: 0.8f).coerceIn(0f, 1f))
                }
                cont.resume(OnDeviceText(text.textBlocks.mapNotNull { it.boundingBox }, lines))
            }
            .addOnFailureListener { cont.resume(OnDeviceText(emptyList(), emptyList())) }
    }

    /** Plans the crops so printed text is never squeezed out:
     *  1. every detected region at a tight fit (always sent);
     *  2. every text block (small; needed for field extraction);
     *  3. regions widened to the forensic margin (region-vs-surroundings
     *     comparison) only while the union stays under [MAX_COVERAGE],
     *     falling back to half the margin, else staying tight. */
    suspend fun prepare(bitmap: Bitmap, detections: List<OnDeviceRegionDetector.Detection>,
                        text: OnDeviceText? = null): Prepared {
        val w = bitmap.width
        val h = bitmap.height
        val covered = BooleanArray(w * h)
        var coveredCount = 0

        fun clamp(r: Rect, pad: Int) = Rect(max(0, r.left - pad), max(0, r.top - pad), min(w, r.right + pad), min(h, r.bottom + pad))
        fun newArea(r: Rect): Int {
            var n = 0
            for (y in r.top until r.bottom) for (x in r.left until r.right) if (!covered[y * w + x]) n++
            return n
        }
        fun mark(r: Rect) {
            for (y in r.top until r.bottom) for (x in r.left until r.right) {
                val i = y * w + x
                if (!covered[i]) { covered[i] = true; coveredCount++ }
            }
        }
        fun fits(r: Rect) = (coveredCount + newArea(r)).toDouble() / covered.size <= MAX_COVERAGE

        class Planned(val label: String, val tight: Rect, var padded: Rect, val confidence: Float)
        val plan = ArrayList<Planned>()

        val regions = detections.filter { it.label != "document" }.sortedByDescending { it.score }
        for (d in regions) {
            val tight = Rect(d.box.left.toInt(), d.box.top.toInt(), d.box.right.toInt(), d.box.bottom.toInt())
            val padded = clamp(tight, 8)
            if (padded.width() < 8 || padded.height() < 8) continue
            mark(padded)
            plan.add(Planned(d.label, tight, padded, d.score))
        }
        var dropped = 0
        for (block in (text ?: readText(bitmap)).blocks) {
            val padded = clamp(block, TEXT_PAD_PX)
            if (padded.width() < 8 || padded.height() < 8) continue
            if (fits(padded)) { mark(padded); plan.add(Planned("text", block, padded, 0.9f)) } else dropped++
        }
        for (p in plan.filter { it.label != "text" }) {
            val full = (REGION_PAD_FRACTION * max(p.tight.width(), p.tight.height())).toInt() + 8
            for (pad in intArrayOf(full, full / 2)) {
                val wider = clamp(p.tight, pad)
                if (fits(wider)) { mark(wider); p.padded = wider; break }
            }
        }
        val crops = plan.map { p ->
            RegionCrop(p.label, listOf(p.tight.left, p.tight.top, p.tight.right, p.tight.bottom),
                listOf(p.padded.left, p.padded.top, p.padded.right, p.padded.bottom), p.confidence, encode(bitmap, p.padded))
        }
        return Prepared(crops, coveredCount.toDouble() / covered.size, dropped)
    }

    private fun encode(bitmap: Bitmap, r: Rect): String {
        val crop = Bitmap.createBitmap(bitmap, r.left, r.top, r.width(), r.height())
        val out = ByteArrayOutputStream()
        crop.compress(Bitmap.CompressFormat.JPEG, 92, out)
        return Base64.encodeToString(out.toByteArray(), Base64.NO_WRAP)
    }

    /** Offline-capable local checks on located regions: MRZ check digits
     * (ICAO 9303 7-3-1, identical rule to the server) and QR decoding. */
    suspend fun localChecks(bitmap: Bitmap, detections: List<OnDeviceRegionDetector.Detection>): List<LocalCheck> {
        val out = ArrayList<LocalCheck>()
        out.add(LocalCheck("Regions located", true,
            detections.groupingBy { it.label }.eachCount().entries.joinToString { "${it.value} ${it.key.replace('_', ' ')}" }
                .ifEmpty { "no regions found" }))
        detections.firstOrNull { it.label == "mrz" }?.let { d ->
            val lines = recognizeText(crop(bitmap, d)).lines()
                .map { it.uppercase().replace(" ", "").replace("«", "<<") }
                .filter { it.length >= 28 && it.count { c -> c == '<' } >= 2 }
            val result = MrzCheck.validate(lines.takeLast(2))
            out.add(LocalCheck("MRZ check digits (on device)", result?.first, result?.second ?: "MRZ lines not readable on device"))
        }
        detections.filter { it.label == "qr_code" || it.label == "barcode" }.forEach { d ->
            val decoded = decodeBarcode(crop(bitmap, d))
            out.add(LocalCheck("QR/barcode read (on device)", decoded, if (decoded) "decoded" else "located but not decodable"))
        }
        return out
    }

    private fun crop(bitmap: Bitmap, d: OnDeviceRegionDetector.Detection): Bitmap {
        val l = d.box.left.toInt().coerceIn(0, bitmap.width - 1)
        val t = d.box.top.toInt().coerceIn(0, bitmap.height - 1)
        val r = d.box.right.toInt().coerceIn(l + 1, bitmap.width)
        val b = d.box.bottom.toInt().coerceIn(t + 1, bitmap.height)
        return Bitmap.createBitmap(bitmap, l, t, r - l, b - t)
    }

    private suspend fun recognizeText(bitmap: Bitmap): String = suspendCancellableCoroutine { cont ->
        TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS).process(InputImage.fromBitmap(bitmap, 0))
            .addOnSuccessListener { cont.resume(it.text) }
            .addOnFailureListener { cont.resume("") }
    }

    private suspend fun decodeBarcode(bitmap: Bitmap): Boolean = suspendCancellableCoroutine { cont ->
        BarcodeScanning.getClient().process(InputImage.fromBitmap(bitmap, 0))
            .addOnSuccessListener { cont.resume(it.any { b -> b.rawValue != null }) }
            .addOnFailureListener { cont.resume(false) }
    }
}

/** passed = null means "could not be checked" — never shown as a failure. */
data class LocalCheck(val name: String, val passed: Boolean?, val detail: String)

object MrzCheck {
    private fun value(c: Char): Int = when (c) {
        in '0'..'9' -> c - '0'
        in 'A'..'Z' -> c - 'A' + 10
        else -> 0
    }

    fun checkDigit(data: String): Int {
        val weights = intArrayOf(7, 3, 1)
        return data.foldIndexed(0) { i, acc, c -> acc + value(c) * weights[i % 3] } % 10
    }

    /** Fields from a TD3 (passport) MRZ, for display on the phone before
     * anything is sent; the server re-parses and re-validates. */
    fun fields(lines: List<String>): Map<String, String> {
        if (lines.size < 2) return emptyMap()
        val l1 = lines[0].padEnd(44, '<').take(44)
        val l2 = lines[1].padEnd(44, '<').take(44)
        val names = l1.substring(5).split("<<", limit = 2)
        fun date(s: String) = if (s.all { it.isDigit() }) "${s.substring(4, 6)}/${s.substring(2, 4)}/${s.substring(0, 2)}" else s
        return linkedMapOf(
            "Document number" to l2.substring(0, 9).trimEnd('<'),
            "Surname" to names[0].replace('<', ' ').trim(),
            "Given names" to (names.getOrNull(1) ?: "").replace('<', ' ').trim(),
            "Nationality" to l2.substring(10, 13).replace("<", ""),
            "Date of birth" to date(l2.substring(13, 19)),
            "Sex" to l2.substring(20, 21).replace("<", "Unspecified"),
            "Date of expiry" to date(l2.substring(21, 27)),
            "Issuing state" to l1.substring(2, 5).replace("<", ""),
        ).filterValues { it.isNotBlank() }
    }

    /** TD3 / MRV-A line 2: returns (all valid, human-readable detail) or null. */
    fun validate(lines: List<String>): Pair<Boolean, String>? {
        if (lines.size < 2) return null
        val l2 = lines[1].padEnd(44, '<').take(44)
        val fields = listOf("document number" to (0 to 9), "date of birth" to (13 to 19), "date of expiry" to (21 to 27))
        val failed = fields.filter { (_, r) ->
            val printed = l2[r.second]
            !printed.isDigit() || printed - '0' != checkDigit(l2.substring(r.first, r.second))
        }.map { it.first }
        return if (failed.isEmpty()) true to "all check digits correct"
        else false to "check digit failed for ${failed.joinToString()} (may be a misread — the server re-checks)"
    }
}
