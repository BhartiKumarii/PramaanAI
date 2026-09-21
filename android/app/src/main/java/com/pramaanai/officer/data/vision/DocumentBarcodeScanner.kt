package com.pramaanai.officer.data.vision

import android.graphics.Bitmap
import android.util.Log
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

object DocumentBarcodeScanner {

    private const val TAG = "DocumentBarcodeScanner"

    data class BarcodeResult(
        val found: Boolean,
        val codes: List<DecodedCode>,
        val fieldsFromCode: Map<String, String>,
    )

    data class DecodedCode(
        val format: String,
        val rawValue: String,
        val displayValue: String,
    )

    private val scanner by lazy {
        BarcodeScanning.getClient(
            BarcodeScannerOptions.Builder()
                .setBarcodeFormats(
                    Barcode.FORMAT_QR_CODE,
                    Barcode.FORMAT_PDF417,
                    Barcode.FORMAT_DATA_MATRIX,
                    Barcode.FORMAT_AZTEC,
                    Barcode.FORMAT_CODE_128,
                    Barcode.FORMAT_CODE_39,
                )
                .build()
        )
    }

    suspend fun scan(bitmap: Bitmap): BarcodeResult {
        val image = InputImage.fromBitmap(bitmap, 0)
        val barcodes = suspendCancellableCoroutine { cont ->
            scanner.process(image)
                .addOnSuccessListener { result -> cont.resume(result) }
                .addOnFailureListener { e -> cont.resumeWithException(e) }
        }

        if (barcodes.isEmpty()) {
            Log.d(TAG, "No barcodes found")
            return BarcodeResult(found = false, codes = emptyList(), fieldsFromCode = emptyMap())
        }

        val decoded = barcodes.mapNotNull { barcode ->
            val raw = barcode.rawValue ?: return@mapNotNull null
            val format = when (barcode.format) {
                Barcode.FORMAT_QR_CODE -> "QR_CODE"
                Barcode.FORMAT_PDF417 -> "PDF417"
                Barcode.FORMAT_DATA_MATRIX -> "DATA_MATRIX"
                Barcode.FORMAT_AZTEC -> "AZTEC"
                Barcode.FORMAT_CODE_128 -> "CODE_128"
                Barcode.FORMAT_CODE_39 -> "CODE_39"
                else -> "UNKNOWN"
            }
            DecodedCode(
                format = format,
                rawValue = raw,
                displayValue = barcode.displayValue ?: raw,
            )
        }

        Log.d(TAG, "Found ${decoded.size} barcodes: ${decoded.map { "${it.format}: ${it.rawValue.take(60)}" }}")

        val fields = mutableMapOf<String, String>()
        for (code in decoded) {
            parseFieldsFromBarcode(code.rawValue, fields)
        }

        return BarcodeResult(found = decoded.isNotEmpty(), codes = decoded, fieldsFromCode = fields)
    }

    private fun parseFieldsFromBarcode(raw: String, fields: MutableMap<String, String>) {
        // Aadhaar QR: XML format with uid, name, gender, dob, etc.
        if (raw.contains("<PrintLetterBarcodeData") || raw.contains("uid=")) {
            parseAadhaarQr(raw, fields)
            return
        }

        // JSON-like content (some e-visas, digital IDs)
        if (raw.trimStart().startsWith("{")) {
            parseJsonBarcode(raw, fields)
            return
        }

        // Key-value pairs separated by newlines or pipes
        if (raw.contains("\n") || raw.contains("|")) {
            parseDelimitedBarcode(raw, fields)
            return
        }

        // PDF417 on Indian DL — pipe-delimited or ANSI format
        if (raw.contains("DL") || raw.contains("ANSI")) {
            parseDlBarcode(raw, fields)
            return
        }

        // Plain text — store the raw value for cross-check
        if (raw.length >= 8) {
            fields["barcode_raw"] = raw.take(200)
        }
    }

    private fun parseAadhaarQr(raw: String, fields: MutableMap<String, String>) {
        fun attr(name: String): String? {
            val pattern = Regex("""$name\s*=\s*"([^"]+)"""")
            return pattern.find(raw)?.groupValues?.get(1)
        }
        attr("uid")?.let {
            fields["aadhaar_number"] = it
            fields["document_number"] = it
        }
        attr("name")?.let { fields["qr_name"] = it }
        attr("gender")?.let {
            fields["qr_gender"] = when (it.uppercase()) {
                "M", "MALE" -> "M"
                "F", "FEMALE" -> "F"
                else -> it
            }
        }
        attr("dob")?.let { fields["qr_date_of_birth"] = it }
        attr("yob")?.let { fields["qr_year_of_birth"] = it }
    }

    private fun parseJsonBarcode(raw: String, fields: MutableMap<String, String>) {
        try {
            val json = org.json.JSONObject(raw)
            json.optString("name").takeIf { it.isNotBlank() }?.let { fields["qr_name"] = it }
            json.optString("dob").takeIf { it.isNotBlank() }?.let { fields["qr_date_of_birth"] = it }
            json.optString("id").takeIf { it.isNotBlank() }?.let { fields["qr_document_number"] = it }
            json.optString("passport").takeIf { it.isNotBlank() }?.let { fields["qr_passport_number"] = it }
            json.optString("visa_number").takeIf { it.isNotBlank() }?.let { fields["qr_visa_number"] = it }
        } catch (_: Exception) {
            fields["barcode_raw"] = raw.take(200)
        }
    }

    private fun parseDelimitedBarcode(raw: String, fields: MutableMap<String, String>) {
        val lines = raw.split(Regex("[|\n]")).map { it.trim() }.filter { it.isNotBlank() }
        for (line in lines) {
            val parts = line.split(Regex("[=:]"), limit = 2)
            if (parts.size == 2) {
                val key = parts[0].trim().lowercase().replace(" ", "_")
                val value = parts[1].trim()
                if (value.isNotBlank()) {
                    fields["qr_$key"] = value
                }
            }
        }
    }

    private fun parseDlBarcode(raw: String, fields: MutableMap<String, String>) {
        val nameMatch = Regex("""(?:DAC|DCS|DCT)([^\n|]+)""").find(raw)
        nameMatch?.let { fields["qr_name"] = it.groupValues[1].trim() }
        val dobMatch = Regex("""DBB(\d{8})""").find(raw)
        dobMatch?.let {
            val d = it.groupValues[1]
            if (d.length == 8) fields["qr_date_of_birth"] = "${d.substring(0,2)}/${d.substring(2,4)}/${d.substring(4)}"
        }
        val dlMatch = Regex("""DAQ([^\n|]+)""").find(raw)
        dlMatch?.let { fields["qr_dl_number"] = it.groupValues[1].trim() }
    }

    fun crossCheckFields(
        barcodeFields: Map<String, String>,
        ocrFields: Map<String, String>,
    ): List<DocumentOcrExtractor.VerificationCheck> {
        val checks = mutableListOf<DocumentOcrExtractor.VerificationCheck>()
        val P = DocumentOcrExtractor.CheckStatus.PASS
        val W = DocumentOcrExtractor.CheckStatus.WARNING

        if (barcodeFields.isEmpty()) return checks

        fun compare(qrKey: String, ocrKey: String, label: String) {
            val qrVal = barcodeFields[qrKey]?.uppercase()?.trim() ?: return
            val ocrVal = ocrFields[ocrKey]?.uppercase()?.trim() ?: return
            val qrNorm = qrVal.replace(Regex("[\\s\\-/.]"), "")
            val ocrNorm = ocrVal.replace(Regex("[\\s\\-/.]"), "")
            if (qrNorm == ocrNorm) {
                checks.add(DocumentOcrExtractor.VerificationCheck("QR ↔ printed $label", P, "Match: $ocrVal"))
            } else {
                checks.add(DocumentOcrExtractor.VerificationCheck("QR ↔ printed $label", W,
                    "QR reads \"$qrVal\" but printed text reads \"$ocrVal\""))
            }
        }

        compare("qr_name", "name", "name")
        compare("qr_date_of_birth", "date_of_birth", "date of birth")
        compare("qr_gender", "gender", "gender")
        compare("qr_document_number", "document_number", "document number")
        compare("qr_passport_number", "passport_number", "passport number")
        compare("qr_dl_number", "dl_number", "DL number")
        compare("qr_visa_number", "visa_number", "visa number")

        // Aadhaar number from QR vs OCR
        val qrAadhaar = barcodeFields["aadhaar_number"]
        val ocrAadhaar = ocrFields["aadhaar_number"]
        if (qrAadhaar != null && ocrAadhaar != null) {
            val qrClean = qrAadhaar.replace(" ", "")
            val ocrClean = ocrAadhaar.replace(" ", "")
            if (qrClean == ocrClean) {
                checks.add(DocumentOcrExtractor.VerificationCheck("QR ↔ printed Aadhaar number", P, "Match: $ocrClean"))
            } else {
                checks.add(DocumentOcrExtractor.VerificationCheck("QR ↔ printed Aadhaar number", W,
                    "QR reads \"$qrClean\" but printed text reads \"$ocrClean\""))
            }
        }

        return checks
    }
}
