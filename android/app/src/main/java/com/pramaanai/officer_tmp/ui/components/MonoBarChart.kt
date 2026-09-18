package com.bordershield.officer.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.bordershield.officer.data.DailyCount
import com.bordershield.officer.ui.theme.Gray200
import com.bordershield.officer.ui.theme.Gray500
import com.bordershield.officer.ui.theme.Ink900

/** A plain monochrome bar chart — no charting library dependency, no color
 * beyond ink/gray, matching the "monochrome charts" requirement. */
@Composable
fun MonoBarChart(data: List<DailyCount>, modifier: Modifier = Modifier) {
    val maxCount = (data.maxOfOrNull { it.count } ?: 0).coerceAtLeast(1)
    Column(modifier = modifier) {
        Canvas(
            modifier = Modifier
                .fillMaxWidth()
                .height(120.dp)
                .padding(horizontal = 4.dp),
        ) {
            val barCount = data.size.coerceAtLeast(1)
            val gap = size.width * 0.02f
            val barWidth = (size.width - gap * (barCount - 1)) / barCount
            drawLine(Gray200, Offset(0f, size.height), Offset(size.width, size.height), strokeWidth = 2f)
            data.forEachIndexed { index, entry ->
                val barHeight = (entry.count.toFloat() / maxCount) * (size.height - 8f)
                val x = index * (barWidth + gap)
                drawRect(
                    color = if (entry.count > 0) Ink900 else Gray200,
                    topLeft = Offset(x, size.height - barHeight),
                    size = Size(barWidth, barHeight.coerceAtLeast(2f)),
                )
            }
        }
        androidx.compose.foundation.layout.Row(modifier = Modifier.fillMaxWidth()) {
            data.forEach { entry ->
                Text(
                    entry.label,
                    style = MaterialTheme.typography.labelSmall,
                    color = Gray500,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.weight(1f),
                )
            }
        }
    }
}

@Composable
fun MonoRibbonBar(label: String, value: Int, total: Int, modifier: Modifier = Modifier) {
    val fraction = if (total == 0) 0f else value.toFloat() / total
    Column(modifier = modifier.fillMaxWidth()) {
        androidx.compose.foundation.layout.Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = androidx.compose.foundation.layout.Arrangement.SpaceBetween,
        ) {
            Text(label, style = MaterialTheme.typography.bodySmall)
            Text("$value", style = MaterialTheme.typography.bodySmall)
        }
        androidx.compose.foundation.layout.Spacer(Modifier.height(4.dp))
        Canvas(modifier = Modifier.fillMaxWidth().height(8.dp)) {
            drawRoundRect(color = Gray200, cornerRadius = androidx.compose.ui.geometry.CornerRadius(4f, 4f))
            drawRoundRect(
                color = Ink900,
                size = Size(size.width * fraction, size.height),
                cornerRadius = androidx.compose.ui.geometry.CornerRadius(4f, 4f),
            )
        }
        androidx.compose.foundation.layout.Spacer(Modifier.height(10.dp))
    }
}
