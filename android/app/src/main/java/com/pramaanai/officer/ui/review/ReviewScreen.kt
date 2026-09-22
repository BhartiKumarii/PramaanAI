package com.pramaanai.officer.ui.review

import android.graphics.BitmapFactory
import android.widget.Toast
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ButtonDefaults
import com.pramaanai.officer.ui.workflow.signalTitle
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
import androidx.compose.material3.CardDefaults
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
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.pramaanai.officer.data.ScreeningRepository
import com.pramaanai.officer.data.model.RegistryHit
import com.pramaanai.officer.data.model.RiskSignalBreakdown
import com.pramaanai.officer.data.model.ScreeningQueueItem
import com.pramaanai.officer.data.model.ScreeningStatus
import com.pramaanai.officer.data.remote.AuditEventResponse
import com.pramaanai.officer.data.remote.BlockchainVerifyResponse
import com.pramaanai.officer.ui.components.MatchTypeTag
import com.pramaanai.officer.ui.components.RiskBadge
import com.pramaanai.officer.ui.theme.AccentGreen
import com.pramaanai.officer.ui.theme.BackgroundDark
import com.pramaanai.officer.ui.theme.Gray100
import com.pramaanai.officer.ui.theme.Gray500
import com.pramaanai.officer.ui.theme.Gray600
import com.pramaanai.officer.ui.theme.Ink900
import com.pramaanai.officer.R
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
    var showFlagDialog by remember { mutableStateOf(false) }
    var showSendDialog by remember { mutableStateOf(false) }
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

    Scaffold(topBar = { TopAppBar(title = { Text(stringResource(R.string.title_screening_review)) }) }) { padding ->
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

            item { CapturedPhotos(currentItem) }
            item { Spacer(Modifier.height(16.dp)) }

            if (currentItem.registryHits.isNotEmpty()) {
                item { Text(stringResource(R.string.registry_hits_title), style = MaterialTheme.typography.titleMedium) }
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
                item { com.pramaanai.officer.ui.components.IdentityClusterGraph(currentItem.identityGraph.members) }
                item { Spacer(Modifier.height(16.dp)) }
            }

            item { Text(stringResource(R.string.signal_breakdown_title), style = MaterialTheme.typography.titleMedium) }
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

            item { Text(stringResource(R.string.audit_history_title), style = MaterialTheme.typography.titleMedium) }
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
                    item { Text(stringResource(R.string.no_audit_trail), style = MaterialTheme.typography.bodySmall, color = Gray500) }
                } else {
                    items(trail) { event ->
                        AuditEventRow(event)
                        Spacer(Modifier.height(8.dp))
                    }
                }
            } ?: item { Text(stringResource(R.string.loading_text), style = MaterialTheme.typography.bodySmall, color = Gray500) }

            item { Spacer(Modifier.height(24.dp)) }
            // A Field Officer sends a case to Immigration; only an
            // Immigration Officer's authorised decision (Clear / Secondary
            // Review / Hold-Refer, made on the web console) is final — see
            // CLAUDE.md. "Dispute" still exists as a local flag-for-
            // secondary-inspection note on the underlying verification
            // record; it does not by itself forward or finalize the case.
            if (currentItem.status == ScreeningStatus.SENT) {
                item {
                    Card(colors = CardDefaults.cardColors(containerColor = Gray100)) {
                        Text(
                            "Case forwarded to Immigration Officer",
                            modifier = Modifier.padding(16.dp),
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.SemiBold,
                        )
                    }
                }
            } else {
                item {
                    Text(
                        "Reasons are filled in automatically from this screening's own checks — nothing to type.",
                        style = MaterialTheme.typography.bodySmall,
                        color = Gray600,
                    )
                }
                item { Spacer(Modifier.height(12.dp)) }
                item {
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        OutlinedButton(
                            onClick = { showFlagDialog = true },
                            modifier = Modifier.weight(1f).height(52.dp),
                        ) { Text("Flag for review") }
                        Button(
                            onClick = { showSendDialog = true },
                            modifier = Modifier.weight(1f).height(52.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = AccentGreen, contentColor = BackgroundDark),
                        ) { Text("Send to Immigration") }
                    }
                }
                item { Spacer(Modifier.height(16.dp)) }
            }
        }
    }

    val reasons = item?.let { flaggedReasons(context, it) }.orEmpty()

    if (showFlagDialog) {
        ReasonDialog(
            title = "Flag for secondary inspection",
            intro = "These reasons were recorded automatically from the checks on this screening. Nothing needs to be typed.",
            reasons = reasons,
            confirmLabel = "Flag for secondary inspection",
            onDismiss = { showFlagDialog = false },
            onConfirm = {
                scope.launch {
                    try {
                        repository.disputeOnBackend(screeningId, reasons.joinToString("; "))
                        Toast.makeText(context, "Flagged for secondary inspection — logged to the audit trail", Toast.LENGTH_LONG).show()
                        showFlagDialog = false
                        onBack()
                    } catch (e: Exception) {
                        showFlagDialog = false
                        Toast.makeText(context, friendlyActionError(context, "flag this screening", e), Toast.LENGTH_LONG).show()
                    }
                }
            },
        )
    }

    if (showSendDialog) {
        ReasonDialog(
            title = "Send to Immigration Officer",
            intro = "The case goes to the Immigration Officer's queue with the reasons below attached. They make the final decision.",
            reasons = reasons,
            confirmLabel = "Send to Immigration",
            onDismiss = { showSendDialog = false },
            onConfirm = {
                scope.launch {
                    try {
                        repository.sendCaseToImmigration(screeningId, reasons.joinToString("\n") { "• $it" })
                        Toast.makeText(context, "Case forwarded to Immigration Officer", Toast.LENGTH_LONG).show()
                        showSendDialog = false
                        onBack()
                    } catch (e: Exception) {
                        showSendDialog = false
                        Toast.makeText(context, friendlyActionError(context, "send this case", e), Toast.LENGTH_LONG).show()
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
            "${getLocalizedDocumentType(item.documentType)} · ${item.nationality} · ${item.checkpoint}",
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
                    Text(getLocalizedDecision(risk.decision), style = MaterialTheme.typography.bodySmall, color = Gray600)
                }
            }
            Spacer(Modifier.height(8.dp))
            HorizontalDivider()
            Spacer(Modifier.height(8.dp))
            Text(stringResource(R.string.top_reason), style = MaterialTheme.typography.labelMedium)
            Text(com.pramaanai.officer.data.humanTopReason(risk.topReason), style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Composable
private fun CapturedPhotos(item: ScreeningQueueItem) {
    val hasDoc = item.documentImagePath != null
    val hasSelfie = item.selfieImagePath != null
    val hasBack = item.documentBackImagePath != null
    if (!hasDoc && !hasSelfie) return

    Column {
        Text(stringResource(R.string.captured_document), style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
            if (hasDoc) {
                Column(modifier = Modifier.weight(1f)) {
                    DocumentImageWithOverlay(item)
                    Spacer(Modifier.height(4.dp))
                    Text("Document", style = MaterialTheme.typography.labelSmall, color = Gray500)
                }
            }
            if (hasBack) {
                Column(modifier = Modifier.weight(1f)) {
                    val backBmp = remember(item.documentBackImagePath) {
                        BitmapFactory.decodeFile(item.documentBackImagePath)
                    }
                    if (backBmp != null) {
                        Image(
                            bitmap = backBmp.asImageBitmap(),
                            contentDescription = "Document back side",
                            modifier = Modifier
                                .fillMaxWidth()
                                .aspectRatio(0.9f)
                                .background(Color(0xFF121212), RoundedCornerShape(8.dp)),
                            contentScale = androidx.compose.ui.layout.ContentScale.Fit,
                        )
                    }
                    Spacer(Modifier.height(4.dp))
                    Text("Back side", style = MaterialTheme.typography.labelSmall, color = Gray500)
                }
            }
            if (hasSelfie) {
                Column(modifier = Modifier.weight(1f)) {
                    val selfieBmp = remember(item.selfieImagePath) {
                        BitmapFactory.decodeFile(item.selfieImagePath)
                    }
                    if (selfieBmp != null) {
                        Image(
                            bitmap = selfieBmp.asImageBitmap(),
                            contentDescription = "Live photo",
                            modifier = Modifier
                                .fillMaxWidth()
                                .aspectRatio(0.9f)
                                .background(Color(0xFF121212), RoundedCornerShape(8.dp)),
                            contentScale = androidx.compose.ui.layout.ContentScale.Crop,
                        )
                    } else {
                        Box(
                            modifier = Modifier.fillMaxWidth().aspectRatio(0.9f).background(Color(0xFF1A1A1A), RoundedCornerShape(8.dp)),
                            contentAlignment = Alignment.Center,
                        ) { Text("Not available", style = MaterialTheme.typography.labelSmall, color = Gray500) }
                    }
                    Spacer(Modifier.height(4.dp))
                    Text("Live photo", style = MaterialTheme.typography.labelSmall, color = Gray500)
                }
            }
        }
    }
}

@Composable
private fun DocumentImageWithOverlay(item: ScreeningQueueItem) {
    val path = item.documentImagePath ?: return
    val boxedSignals = item.risk?.breakdown?.filter { it.location != null } ?: emptyList()

    val decoded = remember(path) {
        BitmapFactory.decodeFile(path)?.let { Triple(it.asImageBitmap(), it.width, it.height) }
    } ?: return

    val (imageBitmap, originalWidth, originalHeight) = decoded
    if (originalWidth <= 0 || originalHeight <= 0) return

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
                    topLeft = Offset(loc.x * scaleX, loc.y * scaleY),
                    size = Size(loc.width * scaleX, loc.height * scaleY),
                    style = Stroke(width = 4f),
                )
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
                color = if (result.chainValid) BackgroundDark else Color.White,
                fontWeight = FontWeight.Bold,
                style = MaterialTheme.typography.labelSmall,
                modifier = Modifier
                    .background(if (result.chainValid) AccentGreen else Color(0xFF757575), RoundedCornerShape(6.dp))
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
                Text("Doc #${hit.documentNumber} · match strength ${"%.0f".format(hit.confidence * 100)}%", style = MaterialTheme.typography.labelSmall)
            }
            MatchTypeTag(hit.matchType)
        }
    }
}

@Composable
private fun SignalRow(signal: RiskSignalBreakdown) {
    val state = when {
        signal.rawRisk <= 0.0001 -> "Passed" to Color(0xFF43A047)
        signal.rawRisk >= 0.7    -> "Alert" to Color(0xFFE53935)
        else                     -> "Review" to Color(0xFFFFA726)
    }
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp)) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Text(com.pramaanai.officer.data.humanSignalTitle(signal.signal), fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
                Text(
                    state.first,
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                    color = state.second,
                    modifier = Modifier
                        .background(state.second.copy(alpha = 0.14f), RoundedCornerShape(6.dp))
                        .padding(horizontal = 8.dp, vertical = 3.dp),
                )
            }
            Spacer(Modifier.height(4.dp))
            Text(com.pramaanai.officer.data.humanSignalReason(signal.signal, signal.reason), style = MaterialTheme.typography.bodySmall)
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
                        stringResource(R.string.not_implemented),
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

// Helper functions to translate backend values to localized strings
@Composable
private fun getLocalizedDocumentType(documentType: String): String {
    return when (documentType.lowercase()) {
        "passport" -> stringResource(R.string.document_passport)
        "national_id" -> stringResource(R.string.document_national_id)
        "driving_license" -> stringResource(R.string.document_driving_license)
        "aadhaar" -> stringResource(R.string.document_aadhaar)
        "pan_card" -> stringResource(R.string.document_pan_card)
        "voter_id" -> stringResource(R.string.document_voter_id)
        else -> documentType.replaceFirstChar { it.uppercase() }
    }
}

@Composable
private fun getLocalizedDecision(decision: String): String {
    return when (decision.uppercase()) {
        "CLEAR" -> stringResource(R.string.decision_clear)
        "SECONDARY_REVIEW" -> stringResource(R.string.decision_secondary_review)
        "HOLD_REFER" -> stringResource(R.string.decision_hold_refer)
        "REVIEW_REQUIRED" -> stringResource(R.string.decision_review_required)
        else -> decision.replace("_", " ").lowercase().replaceFirstChar { it.uppercase() }
    }
}

@Composable
private fun getLocalizedSignalName(signal: String): String {
    return when (signal.lowercase()) {
        "checksum" -> stringResource(R.string.signal_checksum)
        "face_match" -> stringResource(R.string.signal_face_match)
        "forensics" -> stringResource(R.string.signal_forensics)
        "blacklist" -> stringResource(R.string.signal_blacklist)
        "identity_graph" -> stringResource(R.string.signal_identity_graph)
        "mrz" -> stringResource(R.string.signal_mrz)
        "tampering" -> stringResource(R.string.signal_tampering)
        else -> signal.replace("_", " ").replaceFirstChar { it.uppercase() }
    }
}

@Composable
private fun getLocalizedValidationReason(reason: String): String {
    return when {
        reason.contains("checksum", ignoreCase = true) -> stringResource(R.string.reason_checksum_failed)
        reason.contains("date of birth", ignoreCase = true) || reason.contains("dob", ignoreCase = true) -> stringResource(R.string.reason_dob_mismatch)
        reason.contains("multiple identity", ignoreCase = true) -> stringResource(R.string.reason_multiple_identity)
        reason.contains("face", ignoreCase = true) && reason.contains("match", ignoreCase = true) -> stringResource(R.string.reason_face_mismatch)
        reason.contains("expired", ignoreCase = true) -> stringResource(R.string.reason_document_expired)
        reason.contains("registry", ignoreCase = true) || reason.contains("watchlist", ignoreCase = true) -> stringResource(R.string.reason_registry_hit)
        reason.contains("MRZ", ignoreCase = true) -> stringResource(R.string.reason_mrz_invalid)
        reason.contains("tamper", ignoreCase = true) -> stringResource(R.string.reason_tampering_detected)
        else -> reason
    }
}
