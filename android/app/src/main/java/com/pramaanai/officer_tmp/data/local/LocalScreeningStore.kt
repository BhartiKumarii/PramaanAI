package com.bordershield.officer.data.local

import android.content.Context
import com.bordershield.officer.data.model.ScreeningQueueItem
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

/** Local cache of recent screenings, backed by a single JSON file instead of
 * Room: AGP 9.x's built-in-Kotlin support paired with KSP2 hits an
 * unresolved upstream bug (`unexpected jvm signature V`) processing Room's
 * generated code, and compileSdk 37 (required by current Compose/AndroidX
 * releases) needs AGP 9.x. A flat JSON store needs no annotation processor,
 * so it sidesteps the bug entirely while keeping the same read/write shape
 * a Room DAO would have offered. */
class LocalScreeningStore(context: Context) {
    private val file = File(context.filesDir, "screenings.json")
    private val gson = Gson()
    private val listType = object : TypeToken<List<ScreeningQueueItem>>() {}.type
    private val mutex = Mutex()
    private val state = MutableStateFlow(loadFromDisk())

    fun observeAll(): Flow<List<ScreeningQueueItem>> = state.asStateFlow()

    suspend fun getById(id: String): ScreeningQueueItem? = state.value.find { it.id == id }

    suspend fun count(): Int = state.value.size

    suspend fun upsertAll(items: List<ScreeningQueueItem>) = mutex.withLock {
        val merged = state.value.associateBy { it.id }.toMutableMap()
        items.forEach { merged[it.id] = it }
        state.value = merged.values.toList()
        persist()
    }

    suspend fun upsert(item: ScreeningQueueItem) = upsertAll(listOf(item))

    private suspend fun persist() = withContext(Dispatchers.IO) {
        file.writeText(gson.toJson(state.value))
    }

    private fun loadFromDisk(): List<ScreeningQueueItem> {
        if (!file.exists()) return emptyList()
        return try {
            gson.fromJson<List<ScreeningQueueItem>>(file.readText(), listType) ?: emptyList()
        } catch (_: Exception) {
            emptyList()
        }
    }

    companion object {
        @Volatile
        private var instance: LocalScreeningStore? = null

        fun getInstance(context: Context): LocalScreeningStore =
            instance ?: synchronized(this) {
                instance ?: LocalScreeningStore(context.applicationContext).also { instance = it }
            }
    }
}
