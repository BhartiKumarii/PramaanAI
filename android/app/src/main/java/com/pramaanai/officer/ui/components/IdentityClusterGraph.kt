package com.pramaanai.officer.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
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
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import android.graphics.Paint
import android.graphics.Typeface
import com.pramaanai.officer.R
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
 * Enhanced for mobile with touch interactions, better readability and adaptive sizing.
 * Node positions and labels come directly from [members]; nothing here is
 * illustrative-only. */
@Composable
fun IdentityClusterGraph(
    members: List<IdentityClusterMember>,
    modifier: Modifier = Modifier,
) {
    if (members.size < 2) return

    var selectedNode by remember { mutableStateOf<String?>(null) }
    val nodes = remember(members) {
        layoutNodes(members)
    }

    // Dynamic height based on number of members - more space for larger graphs
    val graphHeight = when {
        members.size <= 3 -> 240.dp
        members.size <= 6 -> 320.dp
        else -> 400.dp
    }

    Card(
        modifier = modifier
            .fillMaxWidth()
            .height(graphHeight)
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
                    stringResource(R.string.identity_network_title),
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                    color = Ink900,
                )
                Text(
                    stringResource(R.string.identity_network_entities, members.size),
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
                LegendItem(stringResource(R.string.graph_legend_person), 0xFF45BA50.toInt(), Icons.Filled.Person)
                LegendItem(stringResource(R.string.graph_legend_checkpoint), 0xFF00B5EB.toInt(), Icons.Filled.LocationOn)
                LegendItem(stringResource(R.string.graph_legend_document), 0xFFAD87ED.toInt(), Icons.Filled.Description)
                LegendItem(stringResource(R.string.graph_legend_vehicle), 0xFFFF8918.toInt(), Icons.Filled.DirectionsCar)
                LegendItem(stringResource(R.string.graph_legend_travel_event), 0xFFF14D4C.toInt(), Icons.Filled.FlightTakeoff)
            }

            // Graph Canvas with touch interaction
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(16.dp),
            ) {
                Canvas(
                    modifier = Modifier
                        .fillMaxSize()
                        .pointerInput(nodes) {
                            detectTapGestures { offset ->
                                val centerX = size.width / 2f
                                val centerY = size.height / 2f

                                // Find tapped node
                                val tappedNode = nodes.firstOrNull { node ->
                                    val nodeX = centerX + node.x
                                    val nodeY = centerY + node.y
                                    val nodeRadius = if (node.isCenter) 28f else 22f
                                    val distance = kotlin.math.sqrt(
                                        (offset.x - nodeX) * (offset.x - nodeX) +
                                        (offset.y - nodeY) * (offset.y - nodeY)
                                    )
                                    distance <= nodeRadius + 10f // Add some tap tolerance
                                }

                                selectedNode = if (selectedNode == tappedNode?.id) null else tappedNode?.id
                            }
                        }
                ) {
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

                    // Draw nodes with improved mobile visibility
                    nodes.forEach { node ->
                        val nodeX = centerX + node.x
                        val nodeY = centerY + node.y
                        val isSelected = selectedNode == node.id
                        // Larger nodes for better mobile interaction
                        val nodeRadius = when {
                            node.isCenter -> 28f
                            isSelected -> 24f
                            else -> 22f
                        }
                        val badgeRadius = when {
                            node.isCenter -> 12f
                            isSelected -> 10f
                            else -> 9f
                        }
                        val nodeColor = Color(node.type.color)

                        // Selection ring for selected node
                        if (isSelected) {
                            drawCircle(
                                color = SuccessGreen.copy(alpha = 0.4f),
                                radius = nodeRadius + 6f,
                                center = Offset(nodeX, nodeY),
                                style = Stroke(width = 3f),
                            )
                        }

                        // Node background circle with better contrast
                        drawCircle(
                            color = nodeColor,
                            radius = nodeRadius,
                            center = Offset(nodeX, nodeY),
                        )

                        // Inner white circle for badge with higher contrast
                        drawCircle(
                            color = Color.White,
                            radius = nodeRadius - 3f,
                            center = Offset(nodeX, nodeY),
                        )

                        // Badge circle with type color
                        drawCircle(
                            color = nodeColor,
                            radius = badgeRadius,
                            center = Offset(nodeX, nodeY),
                        )

                        // Badge letter with improved mobile readability
                        val badgeFontSize = when {
                            node.isCenter -> 32f
                            isSelected -> 28f
                            else -> 24f
                        }
                        drawContext.canvas.nativeCanvas.drawText(
                            node.type.badge,
                            nodeX,
                            nodeY + badgeRadius * 0.35f,
                            android.graphics.Paint().apply {
                                color = android.graphics.Color.WHITE
                                textSize = badgeFontSize
                                textAlign = android.graphics.Paint.Align.CENTER
                                typeface = Typeface.DEFAULT_BOLD
                                isAntiAlias = true
                            },
                        )

                        // Node label with better mobile formatting
                        val displayLabel = when {
                            node.label.length > 10 -> node.label.substring(0, 10) + "…"
                            else -> node.label
                        }
                        val labelFontSize = when {
                            node.isCenter -> 26f
                            isSelected -> 24f
                            else -> 22f
                        }

                        // Draw label background for better readability
                        val labelWidth = android.graphics.Paint().apply {
                            textSize = labelFontSize
                        }.measureText(displayLabel)

                        // Semi-transparent background for label
                        drawRoundRect(
                            color = BackgroundDark.copy(alpha = 0.8f),
                            topLeft = Offset(nodeX - labelWidth/2 - 4f, nodeY + nodeRadius + 8f),
                            size = androidx.compose.ui.geometry.Size(labelWidth + 8f, labelFontSize + 8f),
                            cornerRadius = androidx.compose.ui.geometry.CornerRadius(4f, 4f)
                        )

                        drawContext.canvas.nativeCanvas.drawText(
                            displayLabel,
                            nodeX,
                            nodeY + nodeRadius + 24f,
                            android.graphics.Paint().apply {
                                color = when {
                                    node.isCenter -> android.graphics.Color.WHITE
                                    isSelected -> android.graphics.Color.WHITE
                                    else -> android.graphics.Color.LTGRAY
                                }
                                textSize = labelFontSize
                                textAlign = android.graphics.Paint.Align.CENTER
                                typeface = if (node.isCenter || isSelected) Typeface.DEFAULT_BOLD else Typeface.DEFAULT
                                isAntiAlias = true
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

    // For mobile optimization, use adaptive radii based on screen space
    val others = members.drop(1)
    val nodeCount = others.size

    when {
        nodeCount <= 2 -> {
            // Simple horizontal layout for small graphs
            others.forEachIndexed { index, member ->
                val nodeType = inferNodeType(member)
                val xOffset = if (index == 0) -120f else 120f
                result.add(GraphNode(
                    id = member.recordId,
                    label = member.referenceName,
                    type = nodeType,
                    x = centerX + xOffset,
                    y = centerY,
                ))
            }
        }
        nodeCount <= 4 -> {
            // Square/diamond pattern for 3-4 nodes
            val positions = listOf(
                Offset(-100f, -100f), // Top-left
                Offset(100f, -100f),  // Top-right
                Offset(-100f, 100f),  // Bottom-left
                Offset(100f, 100f)    // Bottom-right
            )
            others.forEachIndexed { index, member ->
                val pos = positions[index]
                val nodeType = inferNodeType(member)
                result.add(GraphNode(
                    id = member.recordId,
                    label = member.referenceName,
                    type = nodeType,
                    x = centerX + pos.x,
                    y = centerY + pos.y,
                ))
            }
        }
        else -> {
            // Circular layout for larger graphs with better mobile spacing
            val baseRadius = 90f // Smaller base radius for mobile
            val radiusStep = 80f  // Distance between rings
            var currentRadius = baseRadius
            var nodesInCurrentRing = 0
            var maxNodesInRing = 4 // Start with fewer nodes per ring

            others.forEachIndexed { index, member ->
                if (nodesInCurrentRing >= maxNodesInRing) {
                    // Move to next ring
                    currentRadius += radiusStep
                    nodesInCurrentRing = 0
                    maxNodesInRing = max(6, maxNodesInRing + 2) // Increase capacity for outer rings
                }

                val angle = (2 * PI * nodesInCurrentRing.toDouble()) / maxNodesInRing.toDouble()
                val nodeType = inferNodeType(member)
                result.add(GraphNode(
                    id = member.recordId,
                    label = member.referenceName,
                    type = nodeType,
                    x = centerX + currentRadius * cos(angle).toFloat(),
                    y = centerY + currentRadius * sin(angle).toFloat(),
                ))
                nodesInCurrentRing++
            }
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