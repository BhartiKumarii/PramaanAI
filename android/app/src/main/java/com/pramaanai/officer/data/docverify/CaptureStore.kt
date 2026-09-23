package com.pramaanai.officer.data.docverify

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import java.io.File
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** The officer's own on-phone copy of what was captured — the document image
 * and the live face crop — so a result reopened from Review/History can show
 * the document with the exact problem areas marked, and the live photo next
 * to the document photo. Verification itself only ever sends region crops;
 * a copy of these images is attached to the case as its evidence record
 * (DocVerifyRepository.uploadEvidence). Encrypted at rest with AES-256-GCM under a
 * non-exportable Android Keystore key; files older than [RETENTION_DAYS] are
 * deleted. Saved under the request id at capture time and linked to the
 * server's verification id once verified (immediately, or at offline sync). */
class CaptureStore private constructor(private val context: Context) {
    private val dir = File(context.filesDir, "docverify_captures").apply { mkdirs() }

    private fun key(): SecretKey {
        val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (ks.getKey(ALIAS, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build())
        }.generateKey()
    }

    private fun write(file: File, bitmap: Bitmap, maxSide: Int) {
        val scale = minOf(1f, maxSide.toFloat() / maxOf(bitmap.width, bitmap.height))
        val bmp = if (scale < 1f) Bitmap.createScaledBitmap(bitmap, (bitmap.width * scale).toInt(), (bitmap.height * scale).toInt(), true) else bitmap
        val jpg = ByteArrayOutputStream().also { bmp.compress(Bitmap.CompressFormat.JPEG, 88, it) }.toByteArray()
        val cipher = Cipher.getInstance(TRANSFORMATION).apply { init(Cipher.ENCRYPT_MODE, key()) }
        file.writeBytes(byteArrayOf(cipher.iv.size.toByte()) + cipher.iv + cipher.doFinal(jpg))
    }

    private fun read(file: File): Bitmap? = runCatching {
        val bytes = file.readBytes()
        val ivLen = bytes[0].toInt()
        val cipher = Cipher.getInstance(TRANSFORMATION).apply {
            init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, bytes.copyOfRange(1, 1 + ivLen)))
        }
        val jpg = cipher.doFinal(bytes.copyOfRange(1 + ivLen, bytes.size))
        BitmapFactory.decodeByteArray(jpg, 0, jpg.size)
    }.getOrNull()

    /** [document] must be the exact bitmap the regions were located on, so
     * server evidence boxes (in its pixel coordinates) line up. */
    suspend fun save(requestId: String, document: Bitmap, face: Bitmap?) = withContext(Dispatchers.IO) {
        prune()
        write(File(dir, "$requestId.doc"), document, maxSide = 4000)
        face?.let { write(File(dir, "$requestId.face"), it, maxSide = 800) }
    }

    suspend fun link(requestId: String?, verificationId: String) = withContext(Dispatchers.IO) {
        requestId ?: return@withContext
        listOf("doc", "face").forEach { ext ->
            val from = File(dir, "$requestId.$ext")
            if (from.exists()) from.renameTo(File(dir, "$verificationId.$ext"))
        }
    }

    suspend fun document(id: String): Bitmap? = withContext(Dispatchers.IO) { File(dir, "$id.doc").takeIf { it.exists() }?.let(::read) }
    suspend fun face(id: String): Bitmap? = withContext(Dispatchers.IO) { File(dir, "$id.face").takeIf { it.exists() }?.let(::read) }

    suspend fun count(): Int = withContext(Dispatchers.IO) { dir.listFiles { f -> f.name.endsWith(".doc") }?.size ?: 0 }

    suspend fun clearAll() = withContext(Dispatchers.IO) { dir.listFiles()?.forEach { it.delete() } }

    private fun prune() {
        val days = com.pramaanai.officer.data.local.AppSettings.retentionDays(context)
        val cutoff = System.currentTimeMillis() - days * 24L * 3600 * 1000
        dir.listFiles()?.filter { it.lastModified() < cutoff }?.forEach { it.delete() }
    }

    companion object {
        const val RETENTION_DAYS = 30
        private const val ALIAS = "pramaan_capture_store_key"
        private const val TRANSFORMATION = "AES/GCM/NoPadding"
        @Volatile private var instance: CaptureStore? = null
        fun get(context: Context) = instance ?: synchronized(this) {
            instance ?: CaptureStore(context.applicationContext).also { instance = it }
        }
    }
}
