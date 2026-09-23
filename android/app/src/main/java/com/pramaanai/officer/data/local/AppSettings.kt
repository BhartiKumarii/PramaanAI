package com.pramaanai.officer.data.local

import android.content.Context

/** Officer-adjustable app settings, stored on this phone. Each one is read by
 * the code it controls (see usages) — no setting is display-only. */
object AppSettings {
    private const val PREFS = "pramaan_app_settings"
    private fun prefs(context: Context) = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    /** Crossing pre-selected on the Verify review step: null = use the officer's post. */
    fun defaultRoute(context: Context): String? = prefs(context).getString("default_route", null)
    fun setDefaultRoute(context: Context, route: String?) = prefs(context).edit().putString("default_route", route).apply()

    /** Ask for a live photo of the traveller after the document (face match). */
    fun askLivePhoto(context: Context): Boolean = prefs(context).getBoolean("ask_live_photo", true)
    fun setAskLivePhoto(context: Context, on: Boolean) = prefs(context).edit().putBoolean("ask_live_photo", on).apply()

    /** Days the encrypted document/live-photo copies are kept on this phone. */
    fun retentionDays(context: Context): Int = prefs(context).getInt("retention_days", 30)
    fun setRetentionDays(context: Context, days: Int) = prefs(context).edit().putInt("retention_days", days).apply()

    /** How often to check for the admin's responses (seconds); 0 = only when a list is opened. */
    fun responsePollSeconds(context: Context): Int = prefs(context).getInt("response_poll_seconds", 30)
    fun setResponsePollSeconds(context: Context, seconds: Int) = prefs(context).edit().putInt("response_poll_seconds", seconds).apply()

    /** Risk levels shown as alerts in Notifications. */
    fun alertLevels(context: Context): Set<String> =
        prefs(context).getStringSet("alert_levels", null) ?: setOf("HIGH", "MEDIUM", "LOW")
    fun setAlertLevels(context: Context, levels: Set<String>) = prefs(context).edit().putStringSet("alert_levels", levels).apply()

    /** Minutes of inactivity before the session-lock warning. */
    fun autoLockMinutes(context: Context): Int = prefs(context).getInt("auto_lock_minutes", 10)
    fun setAutoLockMinutes(context: Context, minutes: Int) = prefs(context).edit().putInt("auto_lock_minutes", minutes).apply()
}
