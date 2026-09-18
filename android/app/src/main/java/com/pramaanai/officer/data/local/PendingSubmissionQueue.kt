package com.pramaanai.officer.data.local

import android.content.Context
import com.pramaanai.officer.data.remote.ScreeningSubmissionRequest
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import java.io.File
import java.util.UUID
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

/** Offline submit queue — same Gson+flat-JSON-file pattern as
 * [LocalScreeningStore] (a sibling store, not a repurposing of it: this
 * holds pending *requests* awaiting a network, not completed screening
 * results). "Never block the officer on a missing connection" (CLAUDE.md):
 * when a submission genuinely can't reach the backend, it lands here and
 * [com.pramaanai.officer.data.sync.PendingSubmissionWorker] drains it once
 * connectivity returns.
 *
 * Known gap, reported honestly rather than silently skipped: this file is
 * NOT encrypted at rest. CLAUDE.md calls for "encrypted locally" for the
 * offline path; doing that properly needs an Android Keystore-backed
 * EncryptedFile (androidx.security.crypto), which isn't a dependency this
 * project currently has. Adding it is a reasonable follow-up, not done in
 * this pass so as to not silently introduce an unvetted crypto dependency
 * without the user confirming it. */
class PendingSubmissionQueue(context: Context) {
    data class PendingSubmission(
        val id: String,
        val travelerName: String,
        val request: ScreeningSubmissionRequest,
        val queuedAt: Long,
    )

    private val file = File(context.filesDir, "pending_submissions.json")
    private val gson = Gson()
    private val listType = object : TypeToken<List<PendingSubmission>>() {}.type
    private val mutex = Mutex()
    private val state = MutableStateFlow(loadFromDisk())

    fun observeAll(): Flow<List<PendingSubmission>> = state.asStateFlow()

    suspend fun enqueue(travelerName: String, request: ScreeningSubmissionRequest): PendingSubmission {
        val item = PendingSubmission(
            id = UUID.randomUUID().toString(),
            travelerName = travelerName,
            request = request,
            queuedAt = System.currentTimeMillis(),
        )
        mutex.withLock {
            state.value = state.value + item
            persist()
        }
        return item
    }

    suspend fun remove(id: String) = mutex.withLock {
        state.value = state.value.filterNot { it.id == id }
        persist()
    }

    suspend fun count(): Int = state.value.size

    private suspend fun persist() = withContext(Dispatchers.IO) {
        file.writeText(gson.toJson(state.value))
    }

    private fun loadFromDisk(): List<PendingSubmission> {
        if (!file.exists()) return emptyList()
        return try {
            gson.fromJson<List<PendingSubmission>>(file.readText(), listType) ?: emptyList()
        } catch (_: Exception) {
            emptyList()
        }
    }

    companion object {
        @Volatile
        private var instance: PendingSubmissionQueue? = null

        fun getInstance(context: Context): PendingSubmissionQueue =
            instance ?: synchronized(this) {
                instance ?: PendingSubmissionQueue(context.applicationContext).also { instance = it }
            }
    }
}
