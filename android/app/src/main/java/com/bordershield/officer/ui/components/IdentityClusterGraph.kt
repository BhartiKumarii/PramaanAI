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
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.bordershield.officer.data.model.IdentityClusterMember
import com.bordershield.officer.ui.theme.Gray300
import com.bordershield.officer.ui.theme.Gray600
import com.bordershield.officer.ui.theme.Ink900
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin

/** Real graph rendering of the identity-graph result — the same connected
 * face embedding registered under more than one declared identity, drawn as
 * nodes and edges rather than only a text description. Node positions and
 * labels come directly from [members]; nothing here is illustrative-only. */
@Composable
fun IdentityClusterGraph(members: List<IdentityClusterMember>, modifier: Modifier = Modifier) {
    if (members.size < 2) return
    Column(modifier = modifier.fillMaxWidth()) {
        Text("Multi-identity cluster", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
        androidx.compose.foundation.layout.Spacer(Modifier.height(8.dp))
        Canvas(modifier = Modifier.fillMaxWidth().height(180.dp).padding(8.dp)) {
            val center = Offset(size.width / 2, size.height / 2)
            val radius = minOf(size.width, size.height) / 2 - 40f
            val nodeRadius = 8f
            val angleStep = 2 * PI / members.size
            val nodePositions = members.mapIndexed { index, _ ->
                val angle = angleStep * index - PI / 2
                Offset(
                    center.x + (radius * cos(angle)).toFloat(),
                    center.y + (radius * sin(angle)).toFloat(),
                )
            }
            nodePositions.forEach { pos ->
                drawLine(color = Gray300, start = center, end = pos, strokeWidth = 3f)
            }
            drawCircle(color = Ink900, radius = nodeRadius + 4f, center = center)
            nodePositions.forEachIndexed { index, pos ->
                drawCircle(color = Ink900, radius = nodeRadius, center = pos, style = Stroke(width = 3f))
                val label = members[index].referenceName
                drawContext.canvas.nativeCanvas.drawText(
                    label,
                    pos.x,
                    pos.y + nodeRadius + 28f,
                    android.graphics.Paint().apply {
                        color = android.graphics.Color.DKGRAY
                        textSize = 26f
                        textAlign = android.graphics.Paint.Align.CENTER
                    },
                )
            }
        }
        Text(
            "${members.size} declared identities share the same face embedding.",
            style = MaterialTheme.typography.labelSmall,
            color = Gray600,
        )
    }
}
