package com.pramaanai.officer.ui.i18n

import android.content.Context
import com.pramaanai.officer.data.local.LocaleManager

/** Strings in the officer's chosen app language, usable anywhere — including
 * plain (non-composable) helpers such as status labels. The Activity is
 * recreated when the language changes, so screens re-read fresh text. */
object L {
    private lateinit var base: Context
    private var localized: Context? = null
    private var tag: String? = null

    fun init(context: Context) {
        base = context.applicationContext
    }

    private fun ctx(): Context {
        val current = LocaleManager.getSavedLanguageTag(base)
        if (localized == null || current != tag) {
            localized = LocaleManager.wrap(base)
            tag = current
        }
        return localized!!
    }

    fun s(id: Int): String = ctx().getString(id)

    fun f(id: Int, vararg args: Any?): String = ctx().getString(id, *args)
}
