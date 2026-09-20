package com.pramaanai.officer.data.local

import android.content.Context
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

class ReadAlertsStore(context: Context) {
    private val prefs = context.applicationContext.getSharedPreferences("read_alerts", Context.MODE_PRIVATE)
    private val _readIds = MutableStateFlow(prefs.getStringSet("read_ids", emptySet()) ?: emptySet())
    val readIds: StateFlow<Set<String>> = _readIds

    fun isRead(alertId: String): Boolean = _readIds.value.contains(alertId)

    fun markRead(alertId: String) {
        val updated = _readIds.value + alertId
        prefs.edit().putStringSet("read_ids", updated).apply()
        _readIds.value = updated
    }

    fun markAllRead(alertIds: List<String>) {
        val updated = _readIds.value + alertIds.toSet()
        prefs.edit().putStringSet("read_ids", updated).apply()
        _readIds.value = updated
    }

    companion object {
        @Volatile
        private var instance: ReadAlertsStore? = null

        fun getInstance(context: Context): ReadAlertsStore =
            instance ?: synchronized(this) {
                instance ?: ReadAlertsStore(context).also { instance = it }
            }
    }
}
