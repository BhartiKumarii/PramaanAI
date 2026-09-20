package com.pramaanai.officer.ui.components

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.pramaanai.officer.ui.theme.AccentGreen
import com.pramaanai.officer.ui.theme.BackgroundDark

@Composable
fun GridPatternBackground(
    modifier: Modifier = Modifier,
    animated: Boolean = false,
    content: @Composable () -> Unit,
) {
    val infiniteTransition = rememberInfiniteTransition(label = "grid")
    val pulseAlpha by infiniteTransition.animateFloat(
        initialValue = 0.06f,
        targetValue = if (animated) 0.10f else 0.06f,
        animationSpec = infiniteRepeatable(
            animation = tween(4000, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "gridPulse",
    )
    val glowOffset by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = if (animated) 1f else 0f,
        animationSpec = infiniteRepeatable(
            animation = tween(6000, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "glowDrift",
    )

    Box(modifier = modifier.fillMaxSize().background(BackgroundDark)) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            val cell = 60.dp.toPx()
            val lineAlpha = if (animated) pulseAlpha else 0.08f
            val lineColor = AccentGreen.copy(alpha = lineAlpha)
            var x = 0f
            while (x < size.width) {
                drawLine(lineColor, Offset(x, 0f), Offset(x, size.height), strokeWidth = 1f)
                x += cell
            }
            var y = 0f
            while (y < size.height) {
                drawLine(lineColor, Offset(0f, y), Offset(size.width, y), strokeWidth = 1f)
                y += cell
            }

            if (animated) {
                val cx = size.width * (0.3f + 0.4f * glowOffset)
                val cy = size.height * (0.2f + 0.3f * glowOffset)
                drawCircle(
                    brush = Brush.radialGradient(
                        colors = listOf(AccentGreen.copy(alpha = 0.06f), Color.Transparent),
                        center = Offset(cx, cy),
                        radius = size.width * 0.4f,
                    ),
                    radius = size.width * 0.4f,
                    center = Offset(cx, cy),
                )
            }
        }
        content()
    }
}
