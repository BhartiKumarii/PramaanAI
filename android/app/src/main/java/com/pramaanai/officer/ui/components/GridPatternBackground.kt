package com.pramaanai.officer.ui.components

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
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.pramaanai.officer.ui.theme.BackgroundDark
import kotlin.math.cos
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
            withInfiniteAnimationFrameMillis { ms ->
                value = ms / 1000f
            }
        }
    }

    Box(modifier = modifier.fillMaxSize().background(BackgroundDark)) {
        Canvas(modifier = Modifier.fillMaxSize()) {
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
                val dotSize = 6.dp.toPx()
                val spacing = 14.dp.toPx()
                val cols = (size.width / spacing).toInt()
                val rows = (size.height / spacing).toInt()
                val t = time

                for (row in 0 until rows) {
                    for (col in 0 until cols) {
                        val x = col.toFloat()
                        val y = row.toFloat()

                        val wave1 = sin(x * 0.15f + t * 1.2f) * cos(y * 0.2f + t * 0.8f)
                        val wave2 = sin(x * 0.1f - t * 0.9f) * sin(y * 0.15f + t * 0.5f)
                        val wave3 = cos(x * 0.06f + y * 0.06f + t * 0.7f)

                        val combined = (wave1 + wave2 + wave3) / 3f
                        val normalized = (combined + 1f) / 2f

                        val alpha = normalized * 0.18f
                        if (alpha > 0.04f) {
                            val s = dotSize * (0.3f + normalized * 0.7f)
                            drawRect(
                                color = TealGreen.copy(alpha = alpha),
                                topLeft = Offset(col * spacing, row * spacing),
                                size = Size(s, s),
                            )
                        }
                    }
                }
            }
        }
        content()
    }
}
