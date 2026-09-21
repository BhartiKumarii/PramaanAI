package com.pramaanai.officer.ui.splash

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
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
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.pramaanai.officer.R
import com.pramaanai.officer.ui.theme.BackgroundDark
import kotlinx.coroutines.delay
import kotlin.math.cos
import kotlin.math.sin

private val TealGreen = Color(0xFF2DD4A8)

@Composable
fun SplashScreen(onFinished: () -> Unit) {
    val logoScale = remember { Animatable(0.3f) }
    val logoAlpha = remember { Animatable(0f) }
    val textAlpha = remember { Animatable(0f) }

    val time by produceState(0f) {
        while (true) {
            withInfiniteAnimationFrameMillis { ms ->
                value = ms / 1000f
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

                    val alpha = normalized * 0.22f
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
        }
    }
}
