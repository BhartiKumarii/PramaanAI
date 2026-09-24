package com.pramaanai.officer

import android.graphics.BitmapFactory
import android.graphics.Rect
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.pramaanai.officer.data.vision.PassiveAntiSpoof
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test
import org.junit.runner.RunWith

/**
 * The on-device MiniFASNet port must match the Python reference (upstream
 * 2.7x crop, BGR, raw 0..255). Reference scores were computed with
 * onnxruntime + OpenCV on the bundled synthetic practice face; the tolerance
 * covers Android's bilinear resize vs. OpenCV INTER_LINEAR.
 */
@RunWith(AndroidJUnit4::class)
class PassiveAntiSpoofParityTest {
    @Test
    fun matchesPythonReference() {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        val model = PassiveAntiSpoof.get(ctx)
        assertNotNull("model asset must load", model)
        val bmp = ctx.assets.open("practice/live_face.jpg").use {
            BitmapFactory.decodeStream(it, null, BitmapFactory.Options().apply { inScaled = false })
        }!!
        val cases = listOf(
            Rect(123, 125, 270, 336) to 0.1557f,
            Rect(0, 0, 150, 200) to 0.2722f,      // clamped at the top-left edge
            Rect(250, 300, 400, 500) to 0.8361f,  // clamped at the bottom-right edge
        )
        for ((box, expected) in cases) {
            val score = model!!.score(bmp, box)
            assertNotNull(score)
            android.util.Log.i("PassiveAntiSpoofParity", "box=$box score=$score expected=$expected")
            assertEquals("box $box", expected, score!!, 0.05f)
        }
    }
}
