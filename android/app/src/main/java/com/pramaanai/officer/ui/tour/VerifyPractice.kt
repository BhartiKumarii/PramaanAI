package com.pramaanai.officer.ui.tour

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.google.gson.FieldNamingPolicy
import com.google.gson.GsonBuilder
import com.pramaanai.officer.data.docverify.VerificationOutcome

/** Practice verification driven by the guided tour: the real Verify screens
 * run on a bundled SYNTHETIC sample (assets/practice/) — the document is
 * analysed on the phone as usual, but nothing is sent to the server or saved;
 * the result shown is a stored sample produced by the real pipeline. */
object VerifyPractice {
    enum class Command { NONE, LOAD_DOCUMENT, TO_FACE, USE_FACE, FINISH }

    var active by mutableStateOf(false)
        private set
    var command by mutableStateOf(Command.NONE)

    fun start() {
        TourAnchors.positions.keys.filter { it.startsWith("vp_") }.forEach { TourAnchors.positions.remove(it) }
        active = true
        command = Command.NONE
    }

    fun stop() {
        command = Command.FINISH
        active = false
    }

    fun document(context: Context): Bitmap = context.assets.open("practice/document.jpg").use { BitmapFactory.decodeStream(it) }
    fun face(context: Context): Bitmap = context.assets.open("practice/live_face.jpg").use { BitmapFactory.decodeStream(it) }
    fun outcome(context: Context): VerificationOutcome = context.assets.open("practice/outcome.json").use {
        GsonBuilder().setFieldNamingPolicy(FieldNamingPolicy.LOWER_CASE_WITH_UNDERSCORES).create()
            .fromJson(it.reader(), VerificationOutcome::class.java)
    }
}
