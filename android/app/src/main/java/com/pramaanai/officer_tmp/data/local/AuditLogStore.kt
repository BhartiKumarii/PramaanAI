package com.bordershield.officer.data.local

import android.content.Context
import com.bordershield.officer.data.model.AuditLogEntry
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

/** Real audit trail of officer actions taken in this app (login, screening
 * submitted, decision made, logout) — a flat JSON store, same rationale as
 * [LocalScreeningStore]: no Room annotation processor needed. Entries are
 * append-only from the app's perspective; nothing in the UI ever edits or
 * deletes a written entry. */
class AuditLogStore(context: Context) {
    private val file = File(context.filesDir, "audit_log.json")
    private val gson = Gson()
    private val listType = object : TypeToken<List<AuditLogEntry>>() {}.type
    private val mutex = Mutex()
    private val state = MutableStateFlow(loadFromDisk())

    fun observeAll(): Flow<List<AuditLogEntry>> = state.asStateFlow()

    suspend fun append(entry: AuditLogEntry) = mutex.withLock {
        state.value = state.value + entry
        persist()
    }

    private suspend fun persist() = withContext(Dispatchers.IO) {
        file.writeText(gson.toJson(state.value))
    }

    private fun loadFromDisk(): List<AuditLogEntry> {
        if (!file.exists()) return emptyList()
        return try {
            gson.fromJson<List<AuditLogEntry>>(file.readText(), listType) ?: emptyList()
        } catch (_: Exception) {
            emptyList()
        }
    }

    companion object {
        @Volatile
        private var instance: AuditLogStore? = null

        fun getInstance(context: Context): AuditLogStore =
            instance ?: synchronized(this) {
                instance ?: AuditLogStore(context.applicationContext).also { instance = it }
            }
    }
}
