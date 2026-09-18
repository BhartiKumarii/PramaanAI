package com.bordershield.officer.data.local

import android.content.Context

/** Tracks whether each officer account has completed the first-login guided
 * tour — keyed per officer ID so a shared device doesn't skip the tour for
 * a second officer who has never seen it. */
class TourPreferences(context: Context) {
    private val prefs = context.applicationContext.getSharedPreferences("tour_prefs", Context.MODE_PRIVATE)

    fun hasSeenTour(officerId: String): Boolean = prefs.getBoolean("seen_$officerId", false)

    fun markTourSeen(officerId: String) {
        prefs.edit().putBoolean("seen_$officerId", true).apply()
    }

    companion object {
        @Volatile
        private var instance: TourPreferences? = null

        fun getInstance(context: Context): TourPreferences =
            instance ?: synchronized(this) {
                instance ?: TourPreferences(context).also { instance = it }
            }
    }
}
