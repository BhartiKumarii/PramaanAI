package com.bordershield.officer.ui.review

import android.graphics.BitmapFactory
import android.widget.Toast
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.bordershield.officer.data.ScreeningRepository
import com.bordershield.officer.data.model.RegistryHit
import com.bordershield.officer.data.model.RiskSignalBreakdown
import com.bordershield.officer.data.model.ScreeningQueueItem
import com.bordershield.officer.data.remote.AuditEventResponse
import com.bordershield.officer.data.remote.BlockchainVerifyResponse
import com.bordershield.officer.ui.components.MatchTypeTag
import com.bordershield.officer.ui.components.RiskBadge
import com.bordershield.officer.ui.theme.Gray500
import com.bordershield.officer.ui.theme.Gray600
import com.bordershield.officer.ui.theme.Ink900
import kotlinx.coroutines.launch

private val SIGNAL_BOX_COLORS = mapOf(
    "forensics" to Color(0xFFE65100),
    "checksum" to Color(0xFF1565C0),
    "face_match" to Color(0xFF6A1B9A),
    "blacklist" to Color(0xFFC62828),
    "identity_graph" to Color(0xFF00838F),
)
private val DEFAULT_BOX_COLOR = Color(0xFF424242)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReviewScreen(repository: ScreeningRepository, screeningId: String, onBack: () -> Unit) {
    val context = LocalContext.current
    var item by remember { mutableStateOf<ScreeningQueueItem?>(null) }
    var showDisputeDialog by remember { mutableStateOf(false) }
    var auditTrail by remember { mutableStateOf<List<AuditEventResponse>?>(null) }
    var blockchainResult by remember { mutableStateOf<BlockchainVerifyResponse?>(null) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(screeningId) {
        var loaded = repository.getById(screeningId)
        // A record that arrived via the shared-queue sync (from another
        // officer/device) only has the summary score — hydrate the real
        // per-signal detail from the backend before showing it.
        if (loaded != null && loaded.ocr == null && loaded.risk?.breakdown.isNullOrEmpty()) {
            try {
                repository.hydrateFullDetail(screeningId)
                loaded = repository.getById(screeningId)
            } catch (_: Exception) {
                // Backend unreachable — show what little summary we have.
            }
        }
        item = loaded
        try {
            auditTrail = repository.getBackendAuditTrail(screeningId)
        } catch (_: Exception) {
            auditTrail = emptyList()
        }
        try {
            blockchainResult = repository.verifyBlockchain(screeningId)
        } catch (_: Exception) {
            blockchainResult = null
        }
    }

    Scaffold(topBar = { TopAppBar(title = { Text("Screening Review") }) }) { padding ->
        val currentItem = item
        if (currentItem == null) {
            Column(
                modifier = Modifier.fillMaxSize().padding(padding),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                CircularProgressIndicator()
            }
            return@Scaffold
        }

        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
        ) {
            item { TravelerHeader(currentItem) }
            item { Spacer(Modifier.height(16.dp)) }
            item { RiskScoreCard(currentItem) }
            item { Spacer(Modifier.height(16.dp)) }

            item { DocumentImageWithOverlay(currentItem) }
            item { Spacer(Modifier.height(16.dp)) }

            if (currentItem.registryHits.isNotEmpty()) {
                item { Text("Registry hits", style = MaterialTheme.typography.titleMedium) }
                item {
                    Text(
                        "Checked against mock_central_registry — a sandboxed test dataset, not a real " +
                            "INTERPOL/government watchlist integration.",
                        style = MaterialTheme.typography.labelSmall,
                        color = Gray600,
                    )
                }
                item { Spacer(Modifier.height(8.dp)) }
                items(currentItem.registryHits) { hit ->
                    RegistryHitRow(hit)
                    Spacer(Modifier.height(8.dp))
                }
                item { Spacer(Modifier.height(8.dp)) }
            }

            if (currentItem.identityGraph?.status == "CLUSTER_FOUND") {
                item { com.bordershield.officer.ui.components.IdentityClusterGraph(currentItem.identityGraph.members) }
                item { Spacer(Modifier.height(16.dp)) }
            }

            item { Text("Signal breakdown", style = MaterialTheme.typography.titleMedium) }
            item { Spacer(Modifier.height(8.dp)) }
            currentItem.risk?.breakdown?.let { breakdown ->
                items(breakdown) { signal ->
                    SignalRow(signal)
                    Spacer(Modifier.height(8.dp))
                }
            }

            // Deepfake/liveness are real signals now (see SIGNAL_BOX_COLORS-adjacent
            // heuristics on the backend) and already appear above in "Signal
            // breakdown" as ordinary SignalRow entries whenever they ran. This
            // panel only shows for the Phase-2 mock queue items or the rare
            // no-live-capture case, where there's genuinely nothing to report —
            // never alongside a real result, which would look contradictory.
            if (currentItem.deepfakeStatus == null || currentItem.deepfakeStatus == "NOT_IMPLEMENTED") {
                item { Spacer(Modifier.height(8.dp)) }
                item {
                    NotImplementedCard(
                        title = "Deepfake detection",
                        reason = currentItem.deepfakeReason
                            ?: "No deepfake result was returned for this record.",
                    )
                }
            }
            if (currentItem.livenessStatus == null || currentItem.livenessStatus == "NOT_IMPLEMENTED") {
                item { Spacer(Modifier.height(8.dp)) }
                item {
                    NotImplementedCard(
                        title = "Liveness detection",
                        reason = currentItem.livenessReason
                            ?: ("The challenge prompt shown during capture (e.g. \"turn your head left\") is judged " +
                                "visually by the officer only — no automated liveness check ran for this record."),
                    )
                }
            }

            item { Spacer(Modifier.height(8.dp)) }
            blockchainResult?.let { item { BlockchainIntegrityRow(it) } }
            item { Spacer(Modifier.height(16.dp)) }

            item { Text("Audit History", style = MaterialTheme.typography.titleMedium) }
            item {
                Text(
                    "Real backend record of every officer action on this screening — read-only.",
                    style = MaterialTheme.typography.labelSmall,
                    color = Gray600,
                )
            }
            item { Spacer(Modifier.height(8.dp)) }
            auditTrail?.let { trail ->
                if (trail.isEmpty()) {
                    item { Text("No backend audit trail yet for this record.", style = MaterialTheme.typography.bodySmall, color = Gray500) }
                } else {
                    items(trail) { event ->
                        AuditEventRow(event)
                        Spacer(Modifier.height(8.dp))
                    }
                }
            } ?: item { Text("Loading…", style = MaterialTheme.typography.bodySmall, color = Gray500) }

            item { Spacer(Modifier.height(24.dp)) }
            item {
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    OutlinedButton(
                        onClick = { showDisputeDialog = true },
                        modifier = Modifier.weight(1f),
                    ) { Text("Dispute") }
                    Button(
                        onClick = {
                            scope.launch {
                                try {
                                    repository.clearOnBackend(screeningId, null)
                                    onBack()
                                } catch (e: Exception) {
                                    Toast.makeText(context, "Clear failed: ${e.message}", Toast.LENGTH_LONG).show()
                                }
                            }
                        },
                        modifier = Modifier.weight(1f),
                    ) { Text("Clear") }
                }
            }
        }
    }

    if (showDisputeDialog) {
        DisputeDialog(
            onDismiss = { showDisputeDialog = false },
            onConfirm = { reason ->
                scope.launch {
                    try {
                        repository.disputeOnBackend(screeningId, reason)
                        Toast.makeText(context, "Disputed — logged: \"$reason\"", Toast.LENGTH_LONG).show()
                        showDisputeDialog = false
                        onBack()
                    } catch (e: Exception) {
                        Toast.makeText(context, "Dispute failed: ${e.message}", Toast.LENGTH_LONG).show()
                    }
                }
            },
        )
    }
}

@Composable
private fun TravelerHeader(item: ScreeningQueueItem) {
    Column {
        Text(item.travelerName, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Text(
            "${item.documentType.replaceFirstChar { it.uppercase() }} · ${item.nationality} · ${item.checkpoint}",
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

@Composable
private fun RiskScoreCard(item: ScreeningQueueItem) {
    val risk = item.risk ?: return
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("${risk.score}", style = MaterialTheme.typography.displaySmall, color = Ink900, fontWeight = FontWeight.Bold)
                Spacer(Modifier.width(12.dp))
                Column {
                    RiskBadge(level = risk.level)
                    Spacer(Modifier.height(4.dp))
                    Text(risk.decision.replace("_", " "), style = MaterialTheme.typography.bodySmall, color = Gray600)
                }
            }
            Spacer(Modifier.height(8.dp))
            HorizontalDivider()
            Spacer(Modifier.height(8.dp))
            Text("Top reason", style = MaterialTheme.typography.labelMedium)
            Text(risk.topReason, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

/** Draws each signal's real bounding box (backend pixel coordinates, e.g.
 * the ELA forensics anomaly region) directly on the real captured document
 * image, scaled to however large the image renders on screen. Mock queue
 * items have no [ScreeningQueueItem.documentImagePath] and show nothing
 * here — there is no real photo to draw on, so this doesn't fake one. */
@Composable
private fun DocumentImageWithOverlay(item: ScreeningQueueItem) {
    val path = item.documentImagePath ?: return
    val boxedSignals = item.risk?.breakdown?.filter { it.location != null } ?: emptyList()

    val decoded = remember(path) {
        BitmapFactory.decodeFile(path)?.let { Triple(it.asImageBitmap(), it.width, it.height) }
    } ?: return

    val (imageBitmap, originalWidth, originalHeight) = decoded
    if (originalWidth <= 0 || originalHeight <= 0) return

    Column {
        Text("Captured document", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(8.dp))
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .aspectRatio(originalWidth.toFloat() / originalHeight.toFloat()),
        ) {
            Image(
                bitmap = imageBitmap,
                contentDescription = "Captured document photo",
                modifier = Modifier.fillMaxSize(),
            )
            Canvas(modifier = Modifier.fillMaxSize()) {
                val scaleX = size.width / originalWidth
                val scaleY = size.height / originalHeight
                boxedSignals.forEach { signal ->
                    val loc = signal.location ?: return@forEach
                    val color = SIGNAL_BOX_COLORS[signal.signal] ?: DEFAULT_BOX_COLOR
                    drawRect(
                        color = color,
                        topLeft = Offset(loc.x0 * scaleX, loc.y0 * scaleY),
                        size = Size((loc.x1 - loc.x0) * scaleX, (loc.y1 - loc.y0) * scaleY),
                        style = Stroke(width = 4f),
                    )
                }
            }
        }
        if (boxedSignals.isNotEmpty()) {
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                boxedSignals.forEach { signal ->
                    val color = SIGNAL_BOX_COLORS[signal.signal] ?: DEFAULT_BOX_COLOR
                    Row {
                        Box(
                            modifier = Modifier
                                .height(12.dp)
                                .width(12.dp)
                                .background(color, RoundedCornerShape(2.dp)),
                        )
                        Spacer(Modifier.width(4.dp))
                        Text(signal.signal.replace("_", " "), style = MaterialTheme.typography.labelSmall)
                    }
                }
            }
        }
    }
}

/** Real result of recomputing the mock hash chain up to this record's
 * block — never a decorative "verified" badge. A broken chain here means
 * the backend's own append-only ledger detected tampering somewhere at or
 * before this record, not that this specific record was edited. */
@Composable
private fun BlockchainIntegrityRow(result: BlockchainVerifyResponse) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column {
                Text("Blockchain integrity", fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodyMedium)
                Text(
                    "Mock local hash chain — not a real distributed ledger",
                    style = MaterialTheme.typography.labelSmall,
                    color = Gray500,
                )
            }
            Text(
                if (result.chainValid) "VERIFIED" else "BROKEN",
                color = Color.White,
                fontWeight = FontWeight.Bold,
                style = MaterialTheme.typography.labelSmall,
                modifier = Modifier
                    .background(if (result.chainValid) Ink900 else Color(0xFF757575), RoundedCornerShape(6.dp))
                    .padding(horizontal = 10.dp, vertical = 4.dp),
            )
        }
    }
}

@Composable
private fun AuditEventRow(event: AuditEventResponse) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp)) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(event.eventType.replace("_", " "), fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodySmall)
                Text(event.createdAt.take(19).replace("T", " "), style = MaterialTheme.typography.labelSmall, color = Gray500)
            }
            Text("Officer: ${event.actorUsername ?: event.actorUserId.take(8)}", style = MaterialTheme.typography.labelSmall, color = Gray500)
            if (!event.reason.isNullOrBlank()) {
                Spacer(Modifier.height(4.dp))
                Text(event.reason, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun RegistryHitRow(hit: RegistryHit) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(modifier = Modifier.fillMaxWidth().padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(hit.fullName, fontWeight = FontWeight.SemiBold)
                Text(hit.registryReason, style = MaterialTheme.typography.bodySmall)
                Text("Doc #${hit.documentNumber} · confidence ${"%.2f".format(hit.confidence)}", style = MaterialTheme.typography.labelSmall)
            }
            MatchTypeTag(hit.matchType)
        }
    }
}

@Composable
private fun SignalRow(signal: RiskSignalBreakdown) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp)) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(signal.signal.replace("_", " ").replaceFirstChar { it.uppercase() }, fontWeight = FontWeight.SemiBold)
                Text("weight ${"%.2f".format(signal.weight)} · contribution ${"%.3f".format(signal.contribution)}", style = MaterialTheme.typography.labelSmall)
            }
            Spacer(Modifier.height(4.dp))
            Text(signal.reason, style = MaterialTheme.typography.bodySmall)
            if (signal.location != null) {
                Spacer(Modifier.height(4.dp))
                Text(
                    "Region: (${signal.location.x0},${signal.location.y0})–(${signal.location.x1},${signal.location.y1})",
                    style = MaterialTheme.typography.labelSmall,
                )
            }
        }
    }
}

/** Per the project's honesty rule: a check that isn't real yet is shown as a
 * visibly labeled "not implemented" panel, never a faked pass/fail. */
@Composable
private fun NotImplementedCard(title: String, reason: String) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp)) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(title, fontWeight = FontWeight.SemiBold)
                Box(
                    modifier = Modifier
                        .background(color = Color(0xFF757575), shape = RoundedCornerShape(6.dp))
                        .padding(horizontal = 10.dp, vertical = 4.dp),
                ) {
                    Text(
                        "NOT IMPLEMENTED",
                        color = Color.White,
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                    )
                }
            }
            Spacer(Modifier.height(4.dp))
            Text(reason, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun DisputeDialog(onDismiss: () -> Unit, onConfirm: (String) -> Unit) {
    var reason by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Dispute — secondary inspection") },
        text = {
            Column {
                Text("A reason is required and will be logged to the audit trail — this never silently clears the traveler.")
                Spacer(Modifier.height(12.dp))
                OutlinedTextField(
                    value = reason,
                    onValueChange = { reason = it },
                    label = { Text("Reason") },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            Button(onClick = { if (reason.isNotBlank()) onConfirm(reason) }, enabled = reason.isNotBlank()) {
                Text("Flag for secondary inspection")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Cancel") }
        },
    )
}
