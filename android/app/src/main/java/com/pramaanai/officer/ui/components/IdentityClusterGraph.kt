package com.pramaanai.officer.ui.components

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.DirectionsCar
import androidx.compose.material.icons.filled.FlightTakeoff
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Verified
import androidx.compose.material.icons.automirrored.filled.HelpOutline
import androidx.compose.material.icons.filled.FiberNew
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
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
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
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

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun IdentityClusterGraph(
    members: List<IdentityClusterMember>,
    modifier: Modifier = Modifier,
) {
    if (members.isEmpty()) return

    var selectedNodeId by remember { mutableStateOf<String?>(null) }
    val nodes = remember(members) { layoutNodes(members) }
    val edges = remember(members) { edgesFromMembers(members) }
    val selectedMember = members.firstOrNull { it.recordId == selectedNodeId }

    Column(modifier = modifier.fillMaxWidth()) {
        // Header card
        Card(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp),
            colors = CardDefaults.cardColors(containerColor = Color(0xFF1A1A2E)),
            shape = RoundedCornerShape(16.dp),
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column {
                        Text(
                            stringResource(R.string.identity_network_title),
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = Color.White,
                        )
                        Text(
                            stringResource(R.string.identity_network_entities, members.size),
                            style = MaterialTheme.typography.bodySmall,
                            color = Gray600,
                        )
                    }
                    // Status chip
                    val mainStatus = members.firstOrNull()?.faceMatchStatus
                    val statusColor = when (mainStatus) {
                        FaceMatchStatus.VERIFIED_MATCH -> SuccessGreen
                        FaceMatchStatus.PARTIAL_MATCH -> WarningAmber
                        FaceMatchStatus.NEW_FACE -> ChartBlue
                        else -> Gray600
                    }
                    val statusText = when (mainStatus) {
                        FaceMatchStatus.VERIFIED_MATCH -> "Verified"
                        FaceMatchStatus.PARTIAL_MATCH -> "Needs Review"
                        FaceMatchStatus.NEW_FACE -> "New Face"
                        FaceMatchStatus.NO_FACE_DATA -> "No Face Data"
                        else -> "Unknown"
                    }
                    Box(
                        modifier = Modifier
                            .background(statusColor.copy(alpha = 0.15f), RoundedCornerShape(20.dp))
                            .border(1.dp, statusColor.copy(alpha = 0.4f), RoundedCornerShape(20.dp))
                            .padding(horizontal = 12.dp, vertical = 6.dp),
                    ) {
                        Text(statusText, color = statusColor, style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.SemiBold)
                    }
                }

                Spacer(Modifier.height(12.dp))

                // Compact legend row
                Row(
                    modifier = Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    LegendChip("New", Color(0xFF2ECC71), Icons.Filled.FiberNew)
                    LegendChip("Verified", Color(0xFF3498DB), Icons.Filled.Verified)
                    LegendChip("Review", Color(0xFFF39C12), Icons.AutoMirrored.Filled.HelpOutline)
                    LegendChip("Checkpoint", Color(0xFF00B5EB), Icons.Filled.LocationOn)
                    LegendChip("Document", Color(0xFFAD87ED), Icons.Filled.Description)
                }

                Spacer(Modifier.height(16.dp))

                // Graph canvas — bigger, more spread out
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(280.dp),
                ) {
                    Canvas(
                        modifier = Modifier
                            .fillMaxSize()
                            .pointerInput(nodes) {
                                detectTapGestures { offset ->
                                    val cx = size.width / 2f
                                    val cy = size.height / 2f
                                    val tapped = nodes.firstOrNull { node ->
                                        val nx = cx + node.x
                                        val ny = cy + node.y
                                        val r = if (node.isCenter) 36f else 30f
                                        val dx = offset.x - nx
                                        val dy = offset.y - ny
                                        dx * dx + dy * dy <= (r + 16f) * (r + 16f)
                                    }
                                    selectedNodeId = if (selectedNodeId == tapped?.id) null else tapped?.id
                                }
                            }
                    ) {
                        val cx = size.width / 2f
                        val cy = size.height / 2f

                        // Draw edges
                        edges.forEach { edge ->
                            val from = nodes.firstOrNull { it.id == edge.from }
                            val to = nodes.firstOrNull { it.id == edge.to }
                            if (from != null && to != null) {
                                val sx = cx + from.x
                                val sy = cy + from.y
                                val ex = cx + to.x
                                val ey = cy + to.y

                                val style = edgeStyleFor(edge.relationshipType)
                                val isHighlighted = selectedNodeId == from.id || selectedNodeId == to.id
                                val alpha = if (isHighlighted) 1f else 0.5f

                                drawLine(
                                    color = style.color.copy(alpha = alpha),
                                    start = Offset(sx, sy),
                                    end = Offset(ex, ey),
                                    strokeWidth = if (isHighlighted) style.strokeWidth + 1.5f else style.strokeWidth,
                                    pathEffect = style.dashEffect?.let { PathEffect.dashPathEffect(it) },
                                )

                                // Edge label at midpoint
                                val mx = (sx + ex) / 2f
                                val my = (sy + ey) / 2f
                                val labelText = edge.label
                                val labelPaint = android.graphics.Paint().apply {
                                    color = android.graphics.Color.argb(
                                        if (isHighlighted) 230 else 140, 255, 255, 255
                                    )
                                    textSize = if (isHighlighted) 24f else 20f
                                    textAlign = android.graphics.Paint.Align.CENTER
                                    typeface = Typeface.DEFAULT
                                    isAntiAlias = true
                                }
                                val bounds = android.graphics.Rect()
                                labelPaint.getTextBounds(labelText, 0, labelText.length, bounds)

                                // Label pill background
                                drawContext.canvas.nativeCanvas.drawRoundRect(
                                    mx - bounds.width() / 2f - 8f,
                                    my - bounds.height() / 2f - 6f,
                                    mx + bounds.width() / 2f + 8f,
                                    my + bounds.height() / 2f + 4f,
                                    12f, 12f,
                                    android.graphics.Paint().apply {
                                        color = android.graphics.Color.argb(200, 26, 26, 46)
                                    }
                                )
                                drawContext.canvas.nativeCanvas.drawText(labelText, mx, my + 2f, labelPaint)
                            }
                        }

                        // Draw nodes — bigger, with icon indicators
                        nodes.forEach { node ->
                            val nx = cx + node.x
                            val ny = cy + node.y
                            val isSelected = selectedNodeId == node.id
                            val nodeColor = Color(node.type.color)
                            val radius = when {
                                node.isCenter -> 36f
                                isSelected -> 32f
                                else -> 28f
                            }

                            // Glow/selection ring
                            if (isSelected || node.isCenter) {
                                val glowAlpha = if (isSelected) 0.5f else 0.25f
                                drawCircle(
                                    color = nodeColor.copy(alpha = glowAlpha),
                                    radius = radius + 10f,
                                    center = Offset(nx, ny),
                                )
                                drawCircle(
                                    color = nodeColor.copy(alpha = 0.8f),
                                    radius = radius + 5f,
                                    center = Offset(nx, ny),
                                    style = Stroke(width = 2.5f),
                                )
                            }

                            // Main circle
                            drawCircle(color = nodeColor, radius = radius, center = Offset(nx, ny))

                            // White icon background
                            drawCircle(color = Color.White, radius = radius * 0.55f, center = Offset(nx, ny))

                            // Type icon letter (drawn bigger)
                            val iconChar = node.type.badge
                            val iconSize = if (node.isCenter) 28f else 24f
                            drawContext.canvas.nativeCanvas.drawText(
                                iconChar, nx, ny + iconSize * 0.35f,
                                android.graphics.Paint().apply {
                                    color = node.type.color
                                    textSize = iconSize
                                    textAlign = android.graphics.Paint.Align.CENTER
                                    typeface = Typeface.DEFAULT_BOLD
                                    isAntiAlias = true
                                },
                            )

                            // Encounter count badge
                            val pe = node.previousEncounters ?: 0
                            if (pe > 0) {
                                val bx = nx + radius * 0.7f
                                val by = ny - radius * 0.7f
                                drawCircle(color = Color(0xFF3498DB), radius = 12f, center = Offset(bx, by))
                                drawCircle(color = Color.White, radius = 12f, center = Offset(bx, by), style = Stroke(1.5f))
                                drawContext.canvas.nativeCanvas.drawText(
                                    if (pe > 9) "9+" else pe.toString(),
                                    bx, by + 5f,
                                    android.graphics.Paint().apply {
                                        color = android.graphics.Color.WHITE
                                        textSize = 16f
                                        textAlign = android.graphics.Paint.Align.CENTER
                                        typeface = Typeface.DEFAULT_BOLD
                                        isAntiAlias = true
                                    },
                                )
                            }

                            // Name label below node
                            val displayLabel = when {
                                node.label.length > 14 -> node.label.take(14) + "…"
                                else -> node.label
                            }
                            val labelSize = if (node.isCenter || isSelected) 26f else 22f
                            val labelWidth = android.graphics.Paint().apply { textSize = labelSize }.measureText(displayLabel)

                            drawRoundRect(
                                color = Color(0xDD1A1A2E),
                                topLeft = Offset(nx - labelWidth / 2 - 6f, ny + radius + 6f),
                                size = androidx.compose.ui.geometry.Size(labelWidth + 12f, labelSize + 10f),
                                cornerRadius = androidx.compose.ui.geometry.CornerRadius(6f, 6f),
                            )
                            drawContext.canvas.nativeCanvas.drawText(
                                displayLabel, nx, ny + radius + labelSize + 2f,
                                android.graphics.Paint().apply {
                                    color = android.graphics.Color.WHITE
                                    textSize = labelSize
                                    textAlign = android.graphics.Paint.Align.CENTER
                                    typeface = if (node.isCenter || isSelected) Typeface.DEFAULT_BOLD else Typeface.DEFAULT
                                    isAntiAlias = true
                                },
                            )
                        }
                    }
                }
            }
        }

        // Detail card — shows when a node is tapped
        AnimatedVisibility(visible = selectedMember != null) {
            selectedMember?.let { member ->
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 8.dp, vertical = 6.dp),
                    colors = CardDefaults.cardColors(containerColor = Color(0xFF16213E)),
                    shape = RoundedCornerShape(12.dp),
                    border = androidx.compose.foundation.BorderStroke(
                        1.dp, getStatusColor(member.faceMatchStatus).copy(alpha = 0.5f)
                    ),
                ) {
                    Column(modifier = Modifier.padding(14.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                val nodeType = inferNodeType(member)
                                Box(
                                    modifier = Modifier
                                        .size(36.dp)
                                        .background(Color(nodeType.color).copy(alpha = 0.2f), CircleShape),
                                    contentAlignment = Alignment.Center,
                                ) {
                                    Icon(
                                        nodeType.icon,
                                        contentDescription = null,
                                        tint = Color(nodeType.color),
                                        modifier = Modifier.size(20.dp),
                                    )
                                }
                                Spacer(Modifier.width(10.dp))
                                Column {
                                    Text(
                                        member.referenceName,
                                        style = MaterialTheme.typography.titleSmall,
                                        fontWeight = FontWeight.Bold,
                                        color = Color.White,
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis,
                                    )
                                    Text(
                                        (member.entityType ?: "Person").lowercase()
                                            .replaceFirstChar { it.uppercase() },
                                        style = MaterialTheme.typography.bodySmall,
                                        color = Gray600,
                                    )
                                }
                            }
                            IconButton(onClick = { selectedNodeId = null }, modifier = Modifier.size(28.dp)) {
                                Icon(Icons.Filled.Close, contentDescription = "Close", tint = Gray600, modifier = Modifier.size(18.dp))
                            }
                        }

                        Spacer(Modifier.height(10.dp))

                        // Info chips
                        FlowRow(
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                            verticalArrangement = Arrangement.spacedBy(6.dp),
                        ) {
                            val statusColor = getStatusColor(member.faceMatchStatus)
                            val statusLabel = when (member.faceMatchStatus) {
                                FaceMatchStatus.VERIFIED_MATCH -> "Face Verified"
                                FaceMatchStatus.PARTIAL_MATCH -> "Partial Match"
                                FaceMatchStatus.NEW_FACE -> "New Face"
                                FaceMatchStatus.NO_FACE_DATA -> "No Face Data"
                                else -> "Unknown"
                            }
                            InfoChip(statusLabel, statusColor)

                            val conf = member.faceConfidence ?: 0.0
                            if (conf > 0.0) {
                                val confColor = when {
                                    conf >= 0.8 -> SuccessGreen
                                    conf >= 0.6 -> WarningAmber
                                    else -> DestructiveRed
                                }
                                InfoChip("${(conf * 100).toInt()}% confidence", confColor)
                            }

                            val enc = member.previousEncounters ?: 0
                            if (enc > 0) {
                                InfoChip("$enc prior encounter${if (enc > 1) "s" else ""}", ChartBlue)
                            }

                            member.documentNumber?.let {
                                if (it.isNotBlank()) InfoChip("Doc: $it", ChartPurple)
                            }

                            member.lastSeen?.let {
                                if (it.isNotBlank()) InfoChip("Last seen: $it", Gray600)
                            }

                            val rel = member.relationshipType ?: "IDENTITY_MATCH"
                            val relLabel = when (rel) {
                                "FACE_VERIFIED" -> "Face Verified Link"
                                "FACE_SIMILAR" -> "Similar Face Link"
                                "DOCUMENT_LINKED" -> "Document Link"
                                "TRAVEL_HISTORY" -> "Travel History"
                                else -> "Identity Match"
                            }
                            InfoChip(relLabel, Gray300)
                        }
                    }
                }
            }
        }

        // Connection summary - always visible
        if (members.size >= 2) {
            Spacer(Modifier.height(4.dp))
            Text(
                "Tap any node for details",
                style = MaterialTheme.typography.labelSmall,
                color = Gray600,
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
            )
        }
    }
}

@Composable
private fun InfoChip(label: String, color: Color) {
    Box(
        modifier = Modifier
            .background(color.copy(alpha = 0.12f), RoundedCornerShape(16.dp))
            .border(1.dp, color.copy(alpha = 0.3f), RoundedCornerShape(16.dp))
            .padding(horizontal = 10.dp, vertical = 4.dp),
    ) {
        Text(label, style = MaterialTheme.typography.labelSmall, color = color, fontWeight = FontWeight.Medium)
    }
}

@Composable
private fun LegendChip(label: String, color: Color, icon: ImageVector) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier
            .background(color.copy(alpha = 0.1f), RoundedCornerShape(12.dp))
            .padding(horizontal = 8.dp, vertical = 4.dp),
    ) {
        Icon(icon, contentDescription = null, tint = color, modifier = Modifier.size(14.dp))
        Spacer(Modifier.width(4.dp))
        Text(label, style = MaterialTheme.typography.labelSmall, color = color, fontSize = 11.sp)
    }
}

private fun getStatusColor(status: FaceMatchStatus?): Color = when (status) {
    FaceMatchStatus.VERIFIED_MATCH -> SuccessGreen
    FaceMatchStatus.PARTIAL_MATCH -> WarningAmber
    FaceMatchStatus.NEW_FACE -> Color(0xFF2ECC71)
    FaceMatchStatus.NO_FACE_DATA -> Gray600
    else -> Gray600
}

private fun edgeStyleFor(relationshipType: String): EdgeStyleDef = when (relationshipType) {
    "FACE_VERIFIED" -> EdgeStyleDef(SuccessGreen, 3.5f, null)
    "FACE_SIMILAR" -> EdgeStyleDef(ChartBlue, 2.5f, floatArrayOf(10f, 5f))
    "DOCUMENT_LINKED" -> EdgeStyleDef(ChartPurple, 2.5f, floatArrayOf(5f, 5f))
    "TRAVEL_HISTORY" -> EdgeStyleDef(WarningAmber, 2f, floatArrayOf(15f, 10f))
    else -> EdgeStyleDef(Gray300, 2f, null)
}

private data class EdgeStyleDef(val color: Color, val strokeWidth: Float, val dashEffect: FloatArray?)

private data class GraphNode(
    val id: String,
    val label: String,
    val type: NodeType,
    val x: Float,
    val y: Float,
    val isCenter: Boolean = false,
    val faceMatchStatus: FaceMatchStatus? = FaceMatchStatus.UNKNOWN,
    val faceConfidence: Double? = 0.0,
    val previousEncounters: Int? = 0,
    val relationshipType: String? = "IDENTITY_MATCH",
)

private enum class NodeType(val badge: String, val color: Int, val icon: ImageVector) {
    PERSON_NEW("N", 0xFF2ECC71.toInt(), Icons.Filled.Person),
    PERSON_VERIFIED("V", 0xFF3498DB.toInt(), Icons.Filled.Person),
    PERSON_PARTIAL("P", 0xFFF39C12.toInt(), Icons.Filled.Person),
    PERSON_UNKNOWN("?", 0xFF95A5A6.toInt(), Icons.Filled.Person),
    CHECKPOINT("C", 0xFF00B5EB.toInt(), Icons.Filled.LocationOn),
    VEHICLE("V", 0xFFFF8918.toInt(), Icons.Filled.DirectionsCar),
    TRAVEL_EVENT("T", 0xFFF14D4C.toInt(), Icons.Filled.FlightTakeoff),
    DOCUMENT("D", 0xFFAD87ED.toInt(), Icons.Filled.Description),
}

private data class GraphEdge(
    val from: String,
    val to: String,
    val label: String,
    val relationshipType: String = "IDENTITY_MATCH",
    val confidence: Double = 1.0,
)

private fun layoutNodes(members: List<IdentityClusterMember>): List<GraphNode> {
    val center = members.firstOrNull() ?: return emptyList()
    val result = mutableListOf<GraphNode>()

    result.add(GraphNode(
        id = center.recordId,
        label = center.referenceName,
        type = getPersonNodeType(center.faceMatchStatus),
        x = 0f, y = 0f,
        isCenter = true,
        faceMatchStatus = center.faceMatchStatus,
        faceConfidence = center.faceConfidence,
        previousEncounters = center.previousEncounters,
        relationshipType = center.relationshipType,
    ))

    val others = members.drop(1)
    val count = others.size
    // Wider spread for better readability on mobile
    val radius = when {
        count <= 2 -> 130f
        count <= 4 -> 120f
        else -> 100f
    }

    others.forEachIndexed { i, member ->
        val angle = (2 * PI * i / count) - PI / 2
        result.add(GraphNode(
            id = member.recordId,
            label = member.referenceName,
            type = inferNodeType(member),
            x = (radius * cos(angle)).toFloat(),
            y = (radius * sin(angle)).toFloat(),
            faceMatchStatus = member.faceMatchStatus,
            faceConfidence = member.faceConfidence,
            previousEncounters = member.previousEncounters,
            relationshipType = member.relationshipType,
        ))
    }
    return result
}

private fun inferNodeType(member: IdentityClusterMember): NodeType {
    return when (member.entityType?.uppercase()) {
        "PERSON" -> getPersonNodeType(member.faceMatchStatus)
        "CHECKPOINT" -> NodeType.CHECKPOINT
        "VEHICLE" -> NodeType.VEHICLE
        "TRAVEL_EVENT" -> NodeType.TRAVEL_EVENT
        "DOCUMENT" -> NodeType.DOCUMENT
        else -> {
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

private fun getPersonNodeType(faceMatchStatus: FaceMatchStatus?): NodeType {
    return when (faceMatchStatus) {
        FaceMatchStatus.NEW_FACE -> NodeType.PERSON_NEW
        FaceMatchStatus.VERIFIED_MATCH -> NodeType.PERSON_VERIFIED
        FaceMatchStatus.PARTIAL_MATCH -> NodeType.PERSON_PARTIAL
        FaceMatchStatus.NO_FACE_DATA, FaceMatchStatus.UNKNOWN -> NodeType.PERSON_UNKNOWN
        null -> NodeType.PERSON_UNKNOWN
    }
}

private fun edgesFromMembers(members: List<IdentityClusterMember>): List<GraphEdge> {
    val edges = mutableListOf<GraphEdge>()
    val centerId = members.firstOrNull()?.recordId ?: return emptyList()

    members.drop(1).forEach { member ->
        val et = member.entityType ?: "PERSON"
        val relType = when {
            et == "PERSON" -> when (member.faceMatchStatus) {
                FaceMatchStatus.VERIFIED_MATCH -> "FACE_VERIFIED"
                FaceMatchStatus.PARTIAL_MATCH -> "FACE_SIMILAR"
                else -> "IDENTITY_MATCH"
            }
            et == "DOCUMENT" -> "DOCUMENT_LINKED"
            et == "TRAVEL_EVENT" -> "TRAVEL_HISTORY"
            else -> "IDENTITY_MATCH"
        }
        val label = when (relType) {
            "FACE_VERIFIED" -> "Verified"
            "FACE_SIMILAR" -> "Similar"
            "DOCUMENT_LINKED" -> "Document"
            "TRAVEL_HISTORY" -> "Travel"
            else -> "Linked"
        }
        edges.add(GraphEdge(centerId, member.recordId, label, relType, member.faceConfidence ?: 0.0))
    }

    if (members.size > 3) {
        val persons = members.filter { (it.entityType ?: "PERSON") == "PERSON" }
        val docs = members.filter { it.entityType == "DOCUMENT" }
        if (persons.size >= 2 && docs.isNotEmpty()) {
            edges.add(GraphEdge(persons[0].recordId, persons[1].recordId, "Shared Doc", "DOCUMENT_LINKED", 0.8))
        }
    }
    return edges
}
