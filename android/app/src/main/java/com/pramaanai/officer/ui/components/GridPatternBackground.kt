package com.pramaanai.officer.ui.components

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.core.withInfiniteAnimationFrameMillis
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.pramaanai.officer.ui.theme.BackgroundDark
import kotlin.math.cos
import kotlin.math.floor
import kotlin.math.sin

private val TealGreen = Color(0xFF2DD4A8)

@Composable
fun GridPatternBackground(
    modifier: Modifier = Modifier,
    animated: Boolean = false,
    content: @Composable () -> Unit,
) {
    val time by produceState(0f) {
        if (!animated) return@produceState
        while (true) {
            withInfiniteAnimationFrameMillis { frameTimeMillis ->
                value = frameTimeMillis / 1000f * 0.03f
            }
        }
    }

    val textMeasurer = rememberTextMeasurer()
    val chars = "█▓▒░"

    Box(modifier = modifier.fillMaxSize().background(BackgroundDark)) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            // Grid lines — teal at low opacity, matching website's oklch(0.7 0.18 170 / 0.03)
            val cell = 60.dp.toPx()
            val lineColor = TealGreen.copy(alpha = 0.05f)
            var gx = 0f
            while (gx < size.width) {
                drawLine(lineColor, Offset(gx, 0f), Offset(gx, size.height), strokeWidth = 1f)
                gx += cell
            }
            var gy = 0f
            while (gy < size.height) {
                drawLine(lineColor, Offset(0f, gy), Offset(size.width, gy), strokeWidth = 1f)
                gy += cell
            }

            if (animated) {
                val charW = 8.dp.toPx()
                val charH = 12.dp.toPx()
                val cols = (size.width / charW).toInt().coerceAtMost(60)
                val rows = (size.height / charH).toInt().coerceAtMost(40)

                for (row in 0 until rows) {
                    for (col in 0 until cols) {
                        val x = col.toFloat()
                        val y = row.toFloat()
                        val t = time * 33f

                        val wave1 = sin(x * 0.08f + t) * cos(y * 0.12f + t * 0.5f)
                        val wave2 = sin(x * 0.05f - t * 0.7f) * sin(y * 0.08f + t * 0.3f)
                        val wave3 = cos(x * 0.03f + y * 0.03f + t * 0.4f)

                        val combined = (wave1 + wave2 + wave3) / 3f
                        val normalized = (combined + 1f) / 2f

                        val charIndex = floor(normalized * (chars.length - 1)).toInt()
                            .coerceIn(0, chars.length - 1)
                        if (charIndex < chars.length - 1) {
                            val alpha = (0.08f + normalized * 0.15f)
                            val hue = 170f + normalized * 30f
                            val green = TealGreen.copy(alpha = alpha)

                            drawText(
                                textMeasurer = textMeasurer,
                                text = chars[charIndex].toString(),
                                topLeft = Offset(col * charW, row * charH),
                                style = TextStyle(
                                    color = green,
                                    fontSize = 10.sp,
                                    letterSpacing = 0.sp,
                                ),
                            )
                        }
                    }
                }
            }
        }
        content()
    }
}
