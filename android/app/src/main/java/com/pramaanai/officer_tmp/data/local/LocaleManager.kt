package com.bordershield.officer.data.local

import android.content.Context
import android.content.res.Configuration
import java.util.Locale

/** Per-officer UI language preference — independent of any traveler's
 * document language (see AppLocales / OcrResult). Applied by wrapping the
 * base Context in MainActivity.attachBaseContext, not via a Compose-only
 * mechanism, so it also covers resources read outside Compose. */
object LocaleManager {
    private const val PREFS = "locale_prefs"
    private const val KEY_LANGUAGE_TAG = "language_tag"

    val SUPPORTED = listOf("en", "hi", "ne", "bn", "pa", "as", "dz")

    fun getSavedLanguageTag(context: Context): String =
        context.applicationContext
            .getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_LANGUAGE_TAG, "en") ?: "en"

    fun setSavedLanguageTag(context: Context, tag: String) {
        context.applicationContext
            .getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_LANGUAGE_TAG, tag)
            .apply()
    }

    fun wrap(context: Context): Context {
        val tag = getSavedLanguageTag(context)
        val locale = Locale.forLanguageTag(tag)
        Locale.setDefault(locale)
        val config = Configuration(context.resources.configuration)
        config.setLocale(locale)
        return context.createConfigurationContext(config)
    }
}
