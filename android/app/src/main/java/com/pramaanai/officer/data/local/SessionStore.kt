package com.pramaanai.officer.data.local

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import com.google.gson.Gson
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** What survives an app restart so an officer isn't forced to retype
 * credentials every launch — tokens plus the server-assigned identity, never
 * the password. Encrypted at rest with a non-exportable AES-GCM key held in
 * the Android Keystore (per CLAUDE.md's local-encryption rule), so the file
 * is useless if copied off the device. */
data class PersistedSession(
    val accessToken: String,
    val refreshToken: String,
    val username: String?,
    val role: String?,
    val checkpointCode: String?,
    val checkpointName: String?,
    val loginAt: Long?,
)

object SessionStore {
    private const val KEY_ALIAS = "pramaanai_session_key"
    private const val PREFS = "pramaanai_session"
    private const val PREF_BLOB = "blob"
    private const val TRANSFORMATION = "AES/GCM/NoPadding"

    private val gson = Gson()
    private var appContext: Context? = null

    fun init(context: Context) {
        appContext = context.applicationContext
    }

    private fun prefs() = appContext?.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    private fun key(): SecretKey {
        val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (keyStore.getKey(KEY_ALIAS, null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        generator.init(
            KeyGenParameterSpec.Builder(KEY_ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build(),
        )
        return generator.generateKey()
    }

    fun save(session: PersistedSession) {
        val prefs = prefs() ?: return
        try {
            val cipher = Cipher.getInstance(TRANSFORMATION).apply { init(Cipher.ENCRYPT_MODE, key()) }
            val encrypted = cipher.doFinal(gson.toJson(session).toByteArray(Charsets.UTF_8))
            val blob = Base64.encodeToString(cipher.iv + encrypted, Base64.NO_WRAP)
            prefs.edit().putString(PREF_BLOB, blob).apply()
        } catch (_: Exception) {
            // Persisting is a convenience: if the Keystore misbehaves the
            // officer simply signs in again next launch — never a crash.
            clear()
        }
    }

    fun load(): PersistedSession? {
        val blob = prefs()?.getString(PREF_BLOB, null) ?: return null
        return try {
            val raw = Base64.decode(blob, Base64.NO_WRAP)
            val iv = raw.copyOfRange(0, 12)
            val cipher = Cipher.getInstance(TRANSFORMATION).apply {
                init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, iv))
            }
            gson.fromJson(String(cipher.doFinal(raw.copyOfRange(12, raw.size)), Charsets.UTF_8), PersistedSession::class.java)
        } catch (_: Exception) {
            clear()
            null
        }
    }

    fun clear() {
        prefs()?.edit()?.remove(PREF_BLOB)?.apply()
    }
}
