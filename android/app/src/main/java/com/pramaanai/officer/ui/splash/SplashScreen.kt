package com.pramaanai.officer.ui.splash

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.core.withInfiniteAnimationFrameMillis
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.scale
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.pramaanai.officer.R
import com.pramaanai.officer.ui.theme.AccentGreen
import com.pramaanai.officer.ui.theme.BackgroundDark
import kotlinx.coroutines.delay
import kotlin.math.cos
import kotlin.math.floor
import kotlin.math.sin

private val TealGreen = Color(0xFF2DD4A8)

@Composable
fun SplashScreen(onFinished: () -> Unit) {
    val logoScale = remember { Animatable(0.3f) }
    val logoAlpha = remember { Animatable(0f) }
    val textAlpha = remember { Animatable(0f) }
    val textMeasurer = rememberTextMeasurer()
    val chars = "█▓▒░"

    val time by produceState(0f) {
        while (true) {
            withInfiniteAnimationFrameMillis { frameTimeMillis ->
                value = frameTimeMillis / 1000f * 0.03f
            }
        }
    }

    LaunchedEffect(Unit) {
        logoScale.animateTo(1f, tween(800, easing = FastOutSlowInEasing))
    }
    LaunchedEffect(Unit) {
        logoAlpha.animateTo(1f, tween(600, easing = FastOutSlowInEasing))
    }
    LaunchedEffect(Unit) {
        delay(400)
        textAlpha.animateTo(1f, tween(500, easing = FastOutSlowInEasing))
    }
    LaunchedEffect(Unit) {
        delay(2200)
        onFinished()
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(BackgroundDark),
        contentAlignment = Alignment.Center,
    ) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            // Grid lines
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

            // Flowing ASCII wave — same algorithm as website AsciiWave
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
                        val alpha = (0.10f + normalized * 0.20f)

                        drawText(
                            textMeasurer = textMeasurer,
                            text = chars[charIndex].toString(),
                            topLeft = Offset(col * charW, row * charH),
                            style = TextStyle(
                                color = TealGreen.copy(alpha = alpha),
                                fontSize = 10.sp,
                                letterSpacing = 0.sp,
                            ),
                        )
                    }
                }
            }
        }

        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Image(
                painter = painterResource(R.mipmap.ic_launcher_foreground),
                contentDescription = "PramaanAI",
                modifier = Modifier
                    .size(120.dp)
                    .scale(logoScale.value)
                    .alpha(logoAlpha.value),
            )
            Spacer(Modifier.height(16.dp))
            Text(
                text = "PramaanAI",
                style = MaterialTheme.typography.headlineMedium.copy(
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 1.sp,
                ),
                color = TealGreen,
                modifier = Modifier.alpha(textAlpha.value),
            )
            Spacer(Modifier.height(8.dp))
            Text(
                text = "Secure · Explainable · Connectivity-Aware",
                style = MaterialTheme.typography.bodySmall,
                color = TealGreen.copy(alpha = 0.6f),
                modifier = Modifier.alpha(textAlpha.value),
            )
        }
    }
}
