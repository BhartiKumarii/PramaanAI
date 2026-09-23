package com.pramaanai.officer.data.docverify

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import com.google.gson.Gson
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.io.File
import java.security.KeyStore
import java.util.UUID
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Offline queue for document verifications captured without connectivity.
 * Each item (region crops — personal data) is encrypted at rest with
 * AES-256-GCM under a non-exportable key held in the Android Keystore, one
 * file per item, deleted as soon as the server accepts it. */
class EncryptedDocVerifyQueue private constructor(context: Context) {

    data class Pending(
        val id: String,
        val createdAt: Long,
        val request: RegionVerificationRequest,
        val localChecks: List<LocalCheck>,
    )

    private val dir = File(context.filesDir, "docverify_queue").apply { mkdirs() }
    private val gson = Gson()
    private val mutex = Mutex()

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

    suspend fun enqueue(request: RegionVerificationRequest, localChecks: List<LocalCheck>): Pending = mutex.withLock {
        withContext(Dispatchers.IO) {
            val item = Pending(UUID.randomUUID().toString(), System.currentTimeMillis(), request, localChecks)
            val cipher = Cipher.getInstance(TRANSFORMATION).apply { init(Cipher.ENCRYPT_MODE, key()) }
            val body = cipher.doFinal(gson.toJson(item).toByteArray(Charsets.UTF_8))
            File(dir, "${item.id}.bin").writeBytes(byteArrayOf(cipher.iv.size.toByte()) + cipher.iv + body)
            item
        }
    }

    suspend fun all(): List<Pending> = mutex.withLock {
        withContext(Dispatchers.IO) {
            dir.listFiles { f -> f.name.endsWith(".bin") }.orEmpty().mapNotNull { f ->
                runCatching {
                    val bytes = f.readBytes()
                    val ivLen = bytes[0].toInt()
                    val iv = bytes.copyOfRange(1, 1 + ivLen)
                    val cipher = Cipher.getInstance(TRANSFORMATION).apply {
                        init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, iv))
                    }
                    gson.fromJson(String(cipher.doFinal(bytes.copyOfRange(1 + ivLen, bytes.size)), Charsets.UTF_8), Pending::class.java)
                }.getOrNull()
            }.sortedBy { it.createdAt }
        }
    }

    suspend fun remove(id: String) = mutex.withLock { withContext(Dispatchers.IO) { File(dir, "$id.bin").delete() } }

    suspend fun count(): Int = withContext(Dispatchers.IO) { dir.listFiles { f -> f.name.endsWith(".bin") }?.size ?: 0 }

    companion object {
        private const val ALIAS = "pramaan_docverify_queue_key"
        private const val TRANSFORMATION = "AES/GCM/NoPadding"
        @Volatile private var instance: EncryptedDocVerifyQueue? = null
        fun get(context: Context) = instance ?: synchronized(this) {
            instance ?: EncryptedDocVerifyQueue(context.applicationContext).also { instance = it }
        }
    }
}
