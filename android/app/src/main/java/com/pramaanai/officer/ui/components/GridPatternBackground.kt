package com.pramaanai.officer.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.unit.dp
import com.pramaanai.officer.ui.theme.AccentGreen
import com.pramaanai.officer.ui.theme.BackgroundDark

// Same faint graph-paper grid as the web landing page's `.grid-pattern`
// utility (60px cells, accent-green tinted at ~3% opacity) — applied here
// so the officer app reads as the same product as the web console and
// public site, not a differently-themed companion app.
@Composable
fun GridPatternBackground(
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    Box(modifier = modifier.fillMaxSize().background(BackgroundDark)) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            val cell = 60.dp.toPx()
            val lineColor = AccentGreen.copy(alpha = 0.08f)
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
        }
        content()
    }
}
