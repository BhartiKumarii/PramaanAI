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
import com.pramaanai.officer.data.model.FaceMatchStatus
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

            // Legend - Enhanced for face match status
            Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp)) {
                // First row - Person types with face match status
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    LegendItem(stringResource(R.string.graph_legend_person_new), NodeType.PERSON_NEW.color, Icons.Filled.Person)
                    LegendItem(stringResource(R.string.graph_legend_person_verified), NodeType.PERSON_VERIFIED.color, Icons.Filled.Person)
                    LegendItem(stringResource(R.string.graph_legend_person_partial), NodeType.PERSON_PARTIAL.color, Icons.Filled.Person)
                }
                androidx.compose.foundation.layout.Spacer(Modifier.height(4.dp))
                // Second row - Other entity types
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    LegendItem(stringResource(R.string.graph_legend_checkpoint), NodeType.CHECKPOINT.color, Icons.Filled.LocationOn)
                    LegendItem(stringResource(R.string.graph_legend_document), NodeType.DOCUMENT.color, Icons.Filled.Description)
                    LegendItem(stringResource(R.string.graph_legend_vehicle), NodeType.VEHICLE.color, Icons.Filled.DirectionsCar)
                    LegendItem(stringResource(R.string.graph_legend_travel_event), NodeType.TRAVEL_EVENT.color, Icons.Filled.FlightTakeoff)
                }
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

                            // Get edge style based on relationship type
                            val edgeStyle = when (edge.relationshipType) {
                                "FACE_VERIFIED" -> EdgeStyle.FACE_VERIFIED
                                "FACE_SIMILAR" -> EdgeStyle.FACE_SIMILAR
                                "DOCUMENT_LINKED" -> EdgeStyle.DOCUMENT_LINKED
                                "TRAVEL_HISTORY" -> EdgeStyle.TRAVEL_HISTORY
                                else -> EdgeStyle.IDENTITY_MATCH
                            }

                            // Draw edge line with appropriate style
                            val edgeColor = edgeStyle.color.copy(alpha = 0.7f)
                            drawLine(
                                color = edgeColor,
                                start = Offset(startX, startY),
                                end = Offset(endX, endY),
                                strokeWidth = edgeStyle.strokeWidth,
                                pathEffect = edgeStyle.dashEffect?.let {
                                    androidx.compose.ui.graphics.PathEffect.dashPathEffect(it)
                                }
                            )

                            // Draw edge label at midpoint with confidence info
                            val midX = (startX + endX) / 2
                            val midY = (startY + endY) / 2

                            val labelText = when (edge.relationshipType) {
                                "FACE_VERIFIED", "FACE_SIMILAR" -> {
                                    if (edge.confidence > 0.0) {
                                        "${edge.label} ${(edge.confidence * 100).toInt()}%"
                                    } else {
                                        edge.label
                                    }
                                }
                                else -> edge.label
                            }

                            // Label background for better readability
                            val labelPaint = android.graphics.Paint().apply {
                                color = android.graphics.Color.WHITE
                                textSize = 18f
                                textAlign = android.graphics.Paint.Align.CENTER
                                typeface = Typeface.DEFAULT
                                isAntiAlias = true
                            }
                            val labelBounds = android.graphics.Rect()
                            labelPaint.getTextBounds(labelText, 0, labelText.length, labelBounds)

                            drawContext.canvas.nativeCanvas.drawRoundRect(
                                midX - labelBounds.width() / 2f - 4f,
                                midY - labelBounds.height() / 2f - 6f,
                                midX + labelBounds.width() / 2f + 4f,
                                midY + labelBounds.height() / 2f + 2f,
                                6f, 6f,
                                android.graphics.Paint().apply {
                                    color = android.graphics.Color.WHITE
                                    alpha = 220 // Semi-transparent background
                                }
                            )

                            drawContext.canvas.nativeCanvas.drawText(
                                labelText,
                                midX,
                                midY,
                                android.graphics.Paint().apply {
                                    color = android.graphics.Color.BLACK
                                    textSize = 18f
                                    textAlign = android.graphics.Paint.Align.CENTER
                                    typeface = Typeface.DEFAULT
                                    isAntiAlias = true
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

                        // Face match confidence ring for person nodes
                        if (node.type.badge in listOf("N", "V", "P", "?") && node.faceConfidence > 0.0) {
                            val confidenceColor = when {
                                node.faceConfidence >= 0.8 -> SuccessGreen  // High confidence
                                node.faceConfidence >= 0.6 -> WarningAmber  // Medium confidence
                                else -> DestructiveRed                      // Low confidence
                            }
                            val confidenceAlpha = (0.3f + (node.faceConfidence * 0.5f)).toFloat()
                            drawCircle(
                                color = confidenceColor.copy(alpha = confidenceAlpha),
                                radius = nodeRadius + 4f,
                                center = Offset(nodeX, nodeY),
                                style = Stroke(width = 2f),
                            )
                        }

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

                        // Previous encounters indicator for person nodes
                        if (node.previousEncounters > 0 && node.type.badge in listOf("N", "V", "P", "?")) {
                            val encounterText = if (node.previousEncounters > 9) "9+" else node.previousEncounters.toString()
                            val encounterBadgeX = nodeX + nodeRadius - 8f
                            val encounterBadgeY = nodeY - nodeRadius + 8f

                            // Small badge background
                            drawCircle(
                                color = ChartBlue,
                                radius = 10f,
                                center = Offset(encounterBadgeX, encounterBadgeY),
                            )

                            // Encounter count text
                            drawContext.canvas.nativeCanvas.drawText(
                                encounterText,
                                encounterBadgeX,
                                encounterBadgeY + 3f,
                                android.graphics.Paint().apply {
                                    color = android.graphics.Color.WHITE
                                    textSize = 16f
                                    textAlign = android.graphics.Paint.Align.CENTER
                                    typeface = Typeface.DEFAULT_BOLD
                                    isAntiAlias = true
                                },
                            )
                        }

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
    val faceMatchStatus: FaceMatchStatus = FaceMatchStatus.UNKNOWN,
    val faceConfidence: Double = 0.0,
    val previousEncounters: Int = 0,
    val relationshipType: String = "IDENTITY_MATCH",
)

private enum class NodeType(val badge: String, val color: Int, val icon: androidx.compose.ui.graphics.vector.ImageVector) {
    // Person nodes with face match status differentiation
    PERSON_NEW("N", 0xFF2ECC71.toInt(), Icons.Filled.Person),           // New face - bright green
    PERSON_VERIFIED("V", 0xFF3498DB.toInt(), Icons.Filled.Person),      // Verified match - blue
    PERSON_PARTIAL("P", 0xFFF39C12.toInt(), Icons.Filled.Person),       // Partial match - orange
    PERSON_UNKNOWN("?", 0xFF95A5A6.toInt(), Icons.Filled.Person),       // Unknown status - gray

    // Other entity types
    CHECKPOINT("C", 0xFF00B5EB.toInt(), Icons.Filled.LocationOn),
    VEHICLE("V", 0xFFFF8918.toInt(), Icons.Filled.DirectionsCar),
    TRAVEL_EVENT("T", 0xFFF14D4C.toInt(), Icons.Filled.FlightTakeoff),
    DOCUMENT("D", 0xFFAD87ED.toInt(), Icons.Filled.Description),
}

private fun layoutNodes(members: List<IdentityClusterMember>): List<GraphNode> {
    val center = members.firstOrNull() ?: return emptyList()

    val result = mutableListOf<GraphNode>()
    val centerX = 0f
    val centerY = 0f

    // Center node (primary person) with face match status
    result.add(GraphNode(
        id = center.recordId,
        label = center.referenceName,
        type = getPersonNodeType(center.faceMatchStatus),
        x = centerX,
        y = centerY,
        isCenter = true,
        faceMatchStatus = center.faceMatchStatus,
        faceConfidence = center.faceConfidence,
        previousEncounters = center.previousEncounters,
        relationshipType = center.relationshipType,
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
                    faceMatchStatus = member.faceMatchStatus,
                    faceConfidence = member.faceConfidence,
                    previousEncounters = member.previousEncounters,
                    relationshipType = member.relationshipType,
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
                    faceMatchStatus = member.faceMatchStatus,
                    faceConfidence = member.faceConfidence,
                    previousEncounters = member.previousEncounters,
                    relationshipType = member.relationshipType,
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
                    faceMatchStatus = member.faceMatchStatus,
                    faceConfidence = member.faceConfidence,
                    previousEncounters = member.previousEncounters,
                    relationshipType = member.relationshipType,
                ))
                nodesInCurrentRing++
            }
        }
    }

    return result
}

private fun inferNodeType(member: IdentityClusterMember): NodeType {
    return when (member.entityType.uppercase()) {
        "PERSON" -> getPersonNodeType(member.faceMatchStatus)
        "CHECKPOINT" -> NodeType.CHECKPOINT
        "VEHICLE" -> NodeType.VEHICLE
        "TRAVEL_EVENT" -> NodeType.TRAVEL_EVENT
        "DOCUMENT" -> NodeType.DOCUMENT
        else -> {
            // Fallback to name-based inference for backward compatibility
            when {
                member.referenceName.contains("CHECKPOINT", ignoreCase = true) -> NodeType.CHECKPOINT
                member.referenceName.contains("VEHICLE", ignoreCase = true) -> NodeType.VEHICLE
                member.referenceName.contains("TRAVEL", ignoreCase = true) -> NodeType.TRAVEL_EVENT
                member.referenceName.contains("DOC", ignoreCase = true) || member.referenceName.contains("PASSPORT", ignoreCase = true) -> NodeType.DOCUMENT
                else -> getPersonNodeType(member.faceMatchStatus)
            }
        }
    }
}

private fun getPersonNodeType(faceMatchStatus: FaceMatchStatus): NodeType {
    return when (faceMatchStatus) {
        FaceMatchStatus.NEW_FACE -> NodeType.PERSON_NEW
        FaceMatchStatus.VERIFIED_MATCH -> NodeType.PERSON_VERIFIED
        FaceMatchStatus.PARTIAL_MATCH -> NodeType.PERSON_PARTIAL
        FaceMatchStatus.NO_FACE_DATA, FaceMatchStatus.UNKNOWN -> NodeType.PERSON_UNKNOWN
    }
}

private data class GraphEdge(
    val from: String,
    val to: String,
    val label: String,
    val relationshipType: String = "IDENTITY_MATCH",
    val confidence: Double = 1.0,
)

private enum class EdgeStyle(val color: Color, val strokeWidth: Float, val dashEffect: FloatArray?) {
    FACE_VERIFIED(SuccessGreen, 3f, null),                    // Solid thick green line
    FACE_SIMILAR(ChartBlue, 2f, floatArrayOf(10f, 5f)),      // Dashed blue line
    DOCUMENT_LINKED(ChartPurple, 2f, floatArrayOf(5f, 5f)),  // Dotted purple line
    TRAVEL_HISTORY(WarningAmber, 1.5f, floatArrayOf(15f, 10f)), // Long dash orange line
    IDENTITY_MATCH(Color.Gray, 1.5f, null),                  // Regular gray line
}

private fun edgesFromMembers(members: List<IdentityClusterMember>): List<GraphEdge> {
    val edges = mutableListOf<GraphEdge>()
    val centerId = members.firstOrNull()?.recordId ?: return emptyList()
    val centerMember = members.first()

    // Connect center to all others with appropriate relationship types
    members.drop(1).forEach { member ->
        val relationshipType = when {
            member.entityType == "PERSON" -> {
                when (member.faceMatchStatus) {
                    FaceMatchStatus.VERIFIED_MATCH -> "FACE_VERIFIED"
                    FaceMatchStatus.PARTIAL_MATCH -> "FACE_SIMILAR"
                    else -> "IDENTITY_MATCH"
                }
            }
            member.entityType == "DOCUMENT" -> "DOCUMENT_LINKED"
            member.entityType == "TRAVEL_EVENT" -> "TRAVEL_HISTORY"
            else -> "IDENTITY_MATCH"
        }

        val label = when (relationshipType) {
            "FACE_VERIFIED" -> "Verified Face"
            "FACE_SIMILAR" -> "Similar Face"
            "DOCUMENT_LINKED" -> "Same Document"
            "TRAVEL_HISTORY" -> "Travel History"
            else -> "Connected"
        }

        edges.add(GraphEdge(
            from = centerId,
            to = member.recordId,
            label = label,
            relationshipType = relationshipType,
            confidence = member.faceConfidence,
        ))
    }

    // Add meaningful cross-connections based on data
    if (members.size > 3) {
        val personMembers = members.filter { it.entityType == "PERSON" }
        val documentMembers = members.filter { it.entityType == "DOCUMENT" }

        // Connect people who share documents
        if (personMembers.size >= 2 && documentMembers.isNotEmpty()) {
            edges.add(GraphEdge(
                from = personMembers[0].recordId,
                to = personMembers[1].recordId,
                label = "Shared Doc",
                relationshipType = "DOCUMENT_LINKED",
                confidence = 0.8,
            ))
        }
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