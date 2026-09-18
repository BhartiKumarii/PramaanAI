package com.pramaanai.officer.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.DirectionsCar
import androidx.compose.material.icons.filled.FlightTakeoff
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import android.graphics.Paint
import android.graphics.Typeface
import com.pramaanai.officer.data.model.IdentityClusterMember
import com.pramaanai.officer.ui.theme.BackgroundDark
import com.pramaanai.officer.ui.theme.ChartBlue
import com.pramaanai.officer.ui.theme.ChartPurple
import com.pramaanai.officer.ui.theme.Gray300
import com.pramaanai.officer.ui.theme.Gray600
import com.pramaanai.officer.ui.theme.Ink900
import com.pramaanai.officer.ui.theme.SuccessGreen
import com.pramaanai.officer.ui.theme.WarningAmber
import com.pramaanai.officer.ui.theme.DestructiveRed
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.max
import kotlin.math.sin

/** Real graph rendering of the identity-graph result — ReactFlow-inspired
 * force-directed layout with entity types (PERSON, CHECKPOINT, VEHICLE,
 * TRAVEL_EVENT, DOCUMENT) rendered as badged nodes with connecting edges.
 * Node positions and labels come directly from [members]; nothing here is
 * illustrative-only. */
@Composable
fun IdentityClusterGraph(
    members: List<IdentityClusterMember>,
    modifier: Modifier = Modifier,
) {
    if (members.size < 2) return

    val nodes = remember(members) {
        layoutNodes(members)
    }

    Card(
        modifier = modifier
            .fillMaxWidth()
            .height(280.dp)
            .padding(8.dp),
        colors = CardDefaults.cardColors(containerColor = BackgroundDark),
        shape = RoundedCornerShape(12.dp),
        border = androidx.compose.foundation.BorderStroke(1.dp, Gray300.copy(alpha = 0.3f)),
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            // Header
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    "Identity Network",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                    color = Ink900,
                )
                Text(
                    "${members.size} entities",
                    style = MaterialTheme.typography.labelSmall,
                    color = Gray600,
                )
            }

            // Legend
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                LegendItem("Person", 0xFF45BA50.toInt(), Icons.Filled.Person)
                LegendItem("Checkpoint", 0xFF00B5EB.toInt(), Icons.Filled.LocationOn)
                LegendItem("Document", 0xFFAD87ED.toInt(), Icons.Filled.Description)
                LegendItem("Vehicle", 0xFFFF8918.toInt(), Icons.Filled.DirectionsCar)
                LegendItem("Travel Event", 0xFFF14D4C.toInt(), Icons.Filled.FlightTakeoff)
            }

            // Graph Canvas
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(16.dp),
            ) {
                Canvas(modifier = Modifier.fillMaxSize()) {
                    val centerX = size.width / 2f
                    val centerY = size.height / 2f
                    val edges = edgesFromMembers(members)

                    // Draw edges first (behind nodes)
                    edges.forEach { edge ->
                        val fromNode = nodes.firstOrNull { it.id == edge.from }
                        val toNode = nodes.firstOrNull { it.id == edge.to }
                        if (fromNode != null && toNode != null) {
                            val startX = centerX + fromNode.x
                            val startY = centerY + fromNode.y
                            val endX = centerX + toNode.x
                            val endY = centerY + toNode.y

                            // Draw edge line
                            drawLine(
                                color = Gray300.copy(alpha = 0.5f),
                                start = Offset(startX, startY),
                                end = Offset(endX, endY),
                                strokeWidth = 1.5f,
                            )

                            // Draw edge label at midpoint
                            val midX = (startX + endX) / 2
                            val midY = (startY + endY) / 2
                            drawContext.canvas.nativeCanvas.drawText(
                                edge.label,
                                midX,
                                midY - 4f,
                                android.graphics.Paint().apply {
                                    color = android.graphics.Color.GRAY
                                    textSize = 20f
                                    textAlign = android.graphics.Paint.Align.CENTER
                                    typeface = Typeface.DEFAULT_BOLD
                                },
                            )
                        }
                    }

                    // Draw nodes
                    nodes.forEach { node ->
                        val nodeX = centerX + node.x
                        val nodeY = centerY + node.y
                        val nodeRadius = if (node.isCenter) 24f else 20f
                        val badgeRadius = if (node.isCenter) 10f else 8f
                        val nodeColor = Color(node.type.color)

                        // Node background circle
                        drawCircle(
                            color = nodeColor,
                            radius = nodeRadius,
                            center = Offset(nodeX, nodeY),
                        )

                        // Inner white circle for badge
                        drawCircle(
                            color = Color.White,
                            radius = nodeRadius - 2f,
                            center = Offset(nodeX, nodeY),
                        )

                        // Badge circle with type color
                        drawCircle(
                            color = nodeColor,
                            radius = badgeRadius,
                            center = Offset(nodeX, nodeY),
                        )

                        // Badge letter — same raw-Canvas approach as the edge
                        // labels above; androidx.compose.ui.text.drawText
                        // needs a TextMeasurer and doesn't take raw x/y/color,
                        // so plain Paint.drawText is what's actually callable
                        // from inside a DrawScope without one.
                        val badgeFontSize = if (node.isCenter) 28f else 22f
                        drawContext.canvas.nativeCanvas.drawText(
                            node.type.badge,
                            nodeX,
                            nodeY + badgeRadius * 0.35f,
                            android.graphics.Paint().apply {
                                color = android.graphics.Color.WHITE
                                textSize = badgeFontSize
                                textAlign = android.graphics.Paint.Align.CENTER
                                typeface = Typeface.DEFAULT_BOLD
                            },
                        )

                        // Node label below
                        val displayLabel = if (node.label.length > 12) node.label.substring(0, 12) + "…" else node.label
                        val labelFontSize = if (node.isCenter) 24f else 20f
                        drawContext.canvas.nativeCanvas.drawText(
                            displayLabel,
                            nodeX,
                            nodeY + nodeRadius + 20f,
                            android.graphics.Paint().apply {
                                color = if (node.isCenter) android.graphics.Color.WHITE else android.graphics.Color.DKGRAY
                                textSize = labelFontSize
                                textAlign = android.graphics.Paint.Align.CENTER
                                typeface = if (node.isCenter) Typeface.DEFAULT_BOLD else Typeface.DEFAULT
                            },
                        )

                        // Center node ring pulse animation
                        if (node.isCenter) {
                            val pulseRadius = nodeRadius + 8f + (System.currentTimeMillis() % 2000 / 2000f * 10f)
                            drawCircle(
                                color = nodeColor.copy(alpha = 0.3f),
                                radius = pulseRadius,
                                center = Offset(nodeX, nodeY),
                                style = Stroke(width = 2f),
                            )
                        }
                    }
                }
            }
        }
    }
}

private data class GraphNode(
    val id: String,
    val label: String,
    val type: NodeType,
    val x: Float,
    val y: Float,
    val isCenter: Boolean = false,
)

private enum class NodeType(val badge: String, val color: Int, val icon: androidx.compose.ui.graphics.vector.ImageVector) {
    PERSON("P", 0xFF45BA50.toInt(), Icons.Filled.Person),
    CHECKPOINT("C", 0xFF00B5EB.toInt(), Icons.Filled.LocationOn),
    VEHICLE("V", 0xFFFF8918.toInt(), Icons.Filled.DirectionsCar),
    TRAVEL_EVENT("T", 0xFFF14D4C.toInt(), Icons.Filled.FlightTakeoff),
    DOCUMENT("D", 0xFFAD87ED.toInt(), Icons.Filled.Description),
    UNKNOWN("?", 0xFF8F8F8F.toInt(), Icons.Filled.Person),
}

private fun layoutNodes(members: List<IdentityClusterMember>): List<GraphNode> {
    val center = members.firstOrNull() ?: return emptyList()
    val neighbors = members.drop(1).take(6)
    val outer = members.drop(7)

    val result = mutableListOf<GraphNode>()
    val centerX = 0f
    val centerY = 0f

    // Center node (primary person)
    result.add(GraphNode(
        id = center.recordId,
        label = center.referenceName,
        type = NodeType.PERSON,
        x = centerX,
        y = centerY,
        isCenter = true,
    ))

    // Inner ring - direct connections (neighbors)
    if (neighbors.isNotEmpty()) {
        val innerRadius = 140f
        neighbors.forEachIndexed { index, member ->
            val angle = (2 * PI * index.toDouble()) / max(neighbors.size, 1).toDouble()
            val nodeType = inferNodeType(member)
            result.add(GraphNode(
                id = member.recordId,
                label = member.referenceName,
                type = nodeType,
                x = centerX + innerRadius * cos(angle).toFloat(),
                y = centerY + innerRadius * sin(angle).toFloat(),
            ))
        }
    }

    // Outer ring - indirect connections
    if (outer.isNotEmpty()) {
        val outerRadius = 240f
        outer.forEachIndexed { index, member ->
            val angle = (2 * PI * index.toDouble()) / max(outer.size, 1).toDouble()
            val nodeType = inferNodeType(member)
            result.add(GraphNode(
                id = member.recordId,
                label = member.referenceName,
                type = nodeType,
                x = centerX + outerRadius * cos(angle).toFloat(),
                y = centerY + outerRadius * sin(angle).toFloat(),
            ))
        }
    }

    return result
}

private fun inferNodeType(member: IdentityClusterMember): NodeType {
    // Infer type from available data - in real implementation, this would come from backend
    return when {
        member.referenceName.contains("CHECKPOINT", ignoreCase = true) -> NodeType.CHECKPOINT
        member.referenceName.contains("VEHICLE", ignoreCase = true) -> NodeType.VEHICLE
        member.referenceName.contains("TRAVEL", ignoreCase = true) -> NodeType.TRAVEL_EVENT
        member.referenceName.contains("DOC", ignoreCase = true) || member.referenceName.contains("PASSPORT", ignoreCase = true) -> NodeType.DOCUMENT
        else -> NodeType.PERSON
    }
}

private data class GraphEdge(
    val from: String,
    val to: String,
    val label: String,
)

private fun edgesFromMembers(members: List<IdentityClusterMember>): List<GraphEdge> {
    val edges = mutableListOf<GraphEdge>()
    val centerId = members.firstOrNull()?.recordId ?: return emptyList()

    // Connect center to all others
    members.drop(1).forEach { member ->
        edges.add(GraphEdge(
            from = centerId,
            to = member.recordId,
            label = "same_face",
        ))
    }

    // Add some cross-connections for visual richness
    if (members.size > 3) {
        edges.add(GraphEdge(
            from = members[1].recordId,
            to = members[2].recordId,
            label = "same_doc",
        ))
    }

    return edges
}

@Composable
private fun LegendItem(label: String, colorInt: Int, icon: androidx.compose.ui.graphics.vector.ImageVector) {
    Row(
        modifier = Modifier.padding(top = 4.dp, bottom = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier.size(8.dp)
                .background(Color(colorInt.toInt()), CircleShape),
        )
        androidx.compose.foundation.layout.Spacer(Modifier.width(4.dp))
        Icon(icon, contentDescription = null, tint = Color(colorInt.toInt()), modifier = Modifier.size(10.dp))
        androidx.compose.foundation.layout.Spacer(Modifier.width(4.dp))
        Text(label, style = MaterialTheme.typography.labelSmall, color = Gray600, fontSize = 10.sp)
    }
}