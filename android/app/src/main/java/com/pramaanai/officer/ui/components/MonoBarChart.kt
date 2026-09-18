package com.pramaanai.officer.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.RoundRect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.pramaanai.officer.data.DailyCount
import com.pramaanai.officer.ui.theme.AccentGreen
import com.pramaanai.officer.ui.theme.BorderDark
import com.pramaanai.officer.ui.theme.Gray500
import com.pramaanai.officer.ui.theme.Gray600

/** Activity bar chart sized for a phone: y-axis gridlines with real values,
 * thin rounded bars, x-labels thinned to what actually fits (30 daily bars
 * can't each carry a label), and a tap-to-read line above the plot so an
 * exact count is never left to eyeballing a bar height. No charting library
 * dependency. Empty periods draw a faint baseline tick rather than a bar so
 * "zero" reads as zero, not as missing data. */
@Composable
fun MonoBarChart(data: List<DailyCount>, modifier: Modifier = Modifier, initialSelected: Int = data.lastIndex) {
    if (data.isEmpty()) return
    val textMeasurer = rememberTextMeasurer()
    var selected by remember(data) { mutableIntStateOf(initialSelected.coerceIn(0, data.lastIndex)) }
    val maxCount = data.maxOf { it.count }
    val top = niceTop(maxCount)
    val total = data.sumOf { it.count }
    val axisStyle = MaterialTheme.typography.labelSmall.copy(color = Gray500, fontSize = 10.sp)
    val valueStyle = MaterialTheme.typography.labelSmall.copy(
        color = AccentGreen, fontSize = 11.sp, fontWeight = FontWeight.Bold,
    )

    Column(modifier = modifier.fillMaxWidth()) {
        val sel = data[selected.coerceIn(0, data.lastIndex)]
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(sel.fullLabel, style = MaterialTheme.typography.labelMedium, color = Gray600)
            Text(
                "${sel.count} screening${if (sel.count == 1) "" else "s"}",
                style = MaterialTheme.typography.labelMedium,
                color = AccentGreen,
                fontWeight = FontWeight.Bold,
            )
        }
        Spacer(Modifier.height(2.dp))
        Text("$total in this period", style = MaterialTheme.typography.labelSmall, color = Gray500)
        Spacer(Modifier.height(10.dp))

        Canvas(
            modifier = Modifier
                .fillMaxWidth()
                .height(168.dp)
                .pointerInput(data) {
                    detectTapGestures { offset ->
                        val leftPad = 30.dp.toPx()
                        val slot = (size.width - leftPad) / data.size
                        if (slot > 0f) selected = ((offset.x - leftPad) / slot).toInt().coerceIn(0, data.lastIndex)
                    }
                },
        ) {
            val leftPad = 30.dp.toPx()
            val bottomPad = 20.dp.toPx()
            val topPad = 6.dp.toPx()
            val plotW = size.width - leftPad
            val plotH = size.height - bottomPad - topPad
            val baseY = topPad + plotH

            // Gridlines + y labels at 0, half, top.
            listOf(0, top / 2, top).distinct().forEach { value ->
                val y = baseY - (value.toFloat() / top) * plotH
                drawLine(
                    color = BorderDark,
                    start = Offset(leftPad, y),
                    end = Offset(size.width, y),
                    strokeWidth = 1.dp.toPx(),
                    pathEffect = if (value == 0) null else PathEffect.dashPathEffect(floatArrayOf(6f, 6f)),
                )
                val label = textMeasurer.measure(value.toString(), axisStyle)
                drawText(label, topLeft = Offset(leftPad - label.size.width - 6.dp.toPx(), y - label.size.height / 2f))
            }

            val slot = plotW / data.size
            val barW = (slot * if (data.size <= 8) 0.55f else 0.62f).coerceAtLeast(2.dp.toPx())
            val radius = CornerRadius((barW * 0.35f).coerceAtMost(6.dp.toPx()))
            val labelEvery = if (data.size <= 8) 1 else Math.ceil(data.size / 6.0).toInt()

            data.forEachIndexed { index, entry ->
                val cx = leftPad + slot * index + slot / 2f
                val isSelected = index == selected
                if (entry.count > 0) {
                    val h = (entry.count.toFloat() / top * plotH).coerceAtLeast(4.dp.toPx())
                    val path = Path().apply {
                        addRoundRect(
                            RoundRect(
                                left = cx - barW / 2f, top = baseY - h, right = cx + barW / 2f, bottom = baseY,
                                topLeftCornerRadius = radius, topRightCornerRadius = radius,
                                bottomLeftCornerRadius = CornerRadius.Zero, bottomRightCornerRadius = CornerRadius.Zero,
                            ),
                        )
                    }
                    drawPath(path, color = AccentGreen.copy(alpha = if (isSelected) 1f else 0.55f))
                    if (isSelected) {
                        val v = textMeasurer.measure(entry.count.toString(), valueStyle)
                        val vx = (cx - v.size.width / 2f).coerceIn(leftPad, size.width - v.size.width)
                        drawText(v, topLeft = Offset(vx, (baseY - h - v.size.height - 2.dp.toPx()).coerceAtLeast(0f)))
                    }
                } else {
                    drawRect(
                        color = if (isSelected) AccentGreen else AccentGreen.copy(alpha = 0.25f),
                        topLeft = Offset(cx - barW / 2f, baseY - 2.dp.toPx()),
                        size = Size(barW, 2.dp.toPx()),
                    )
                }

                if (index % labelEvery == 0 || index == data.lastIndex && labelEvery == 1) {
                    val l = textMeasurer.measure(entry.label, axisStyle)
                    drawText(l, topLeft = Offset(cx - l.size.width / 2f, baseY + 4.dp.toPx()))
                }
            }
        }
    }
}

/** A y-axis maximum with room above the tallest bar and round gridline values. */
private fun niceTop(max: Int): Int = when {
    max <= 4 -> 4
    else -> ((max + 3) / 4) * 4
}

@Composable
fun MonoRibbonBar(
    label: String,
    value: Int,
    total: Int,
    modifier: Modifier = Modifier,
    color: androidx.compose.ui.graphics.Color = AccentGreen,
) {
    val fraction = if (total == 0) 0f else value.toFloat() / total
    Column(modifier = modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text(label, style = MaterialTheme.typography.bodySmall)
            Text("$value", style = MaterialTheme.typography.bodySmall)
        }
        Spacer(Modifier.height(4.dp))
        Canvas(modifier = Modifier.fillMaxWidth().height(8.dp)) {
            drawRoundRect(color = BorderDark, cornerRadius = CornerRadius(4f, 4f))
            drawRoundRect(
                color = color,
                size = Size(size.width * fraction, size.height),
                cornerRadius = CornerRadius(4f, 4f),
            )
        }
        Spacer(Modifier.height(10.dp))
    }
}
