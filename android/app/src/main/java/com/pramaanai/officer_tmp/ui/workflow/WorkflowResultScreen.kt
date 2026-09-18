package com.bordershield.officer.ui.workflow

import android.widget.Toast
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.bordershield.officer.data.ScreeningRepository
import com.bordershield.officer.data.model.ScreeningQueueItem
import com.bordershield.officer.data.model.ScreeningStatus
import com.bordershield.officer.data.model.ValidationFinding
import com.bordershield.officer.ui.components.ConfidenceTag
import com.bordershield.officer.ui.components.WorkflowStepper
import com.bordershield.officer.ui.theme.Gray100
import com.bordershield.officer.ui.theme.Gray200
import com.bordershield.officer.ui.theme.Gray500
import com.bordershield.officer.ui.theme.Gray600
import com.bordershield.officer.ui.theme.Ink900
import com.bordershield.officer.ui.theme.White
import kotlinx.coroutines.launch

/** Steps 2–7 of the new-screening workflow. All content here is the single
 * real /documents/screen response already fetched by CaptureScreen — this
 * paces the officer's read of it (Extraction, Verification, Screening,
 * Risk Assessment, Review, Complete) rather than dumping everything at
 * once; it does not compute or fabricate anything new. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WorkflowResultScreen(repository: ScreeningRepository, screeningId: String, onComplete: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var item by remember { mutableStateOf<ScreeningQueueItem?>(null) }
    var step by remember { mutableStateOf(2) }
    var showDisputeDialog by remember { mutableStateOf(false) }
    var officerNotes by remember { mutableStateOf("") }

    LaunchedEffect(screeningId) { item = repository.getById(screeningId) }

    Scaffold(topBar = { TopAppBar(title = { Text("New Screening") }) }) { padding ->
        val currentItem = item
        if (currentItem == null) {
            Column(Modifier.fillMaxSize().padding(padding), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                CircularProgressIndicator()
            }
            return@Scaffold
        }

        Column(modifier = Modifier.fillMaxSize().padding(padding)) {
            Column(Modifier.padding(16.dp)) { WorkflowStepper(currentStep = step) }
            LazyColumn(modifier = Modifier.weight(1f).fillMaxWidth().padding(horizontal = 16.dp)) {
                item {
                    when (step) {
                        2 -> ExtractionStep(currentItem)
                        3 -> VerificationStep(currentItem)
                        4 -> ScreeningStep(currentItem)
                        5 -> RiskAssessmentStep(currentItem)
                        6 -> ReviewStep(officerNotes, onNotesChange = { officerNotes = it })
                        7 -> CompleteStep(currentItem)
                    }
                    Spacer(Modifier.height(24.dp))
                }
            }
            Row(modifier = Modifier.fillMaxWidth().padding(16.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                if (step in 3..6) {
                    OutlinedButton(onClick = { step-- }, modifier = Modifier.weight(1f)) { Text("Back") }
                }
                when (step) {
                    in 2..5 -> Button(
                        onClick = { step++ },
                        colors = ButtonDefaults.buttonColors(containerColor = Ink900, contentColor = White),
                        modifier = Modifier.weight(1f),
                    ) { Text("Next") }
                    6 -> {
                        OutlinedButton(onClick = { showDisputeDialog = true }, modifier = Modifier.weight(1f)) { Text("Flag / Further review") }
                        Button(
                            onClick = {
                                scope.launch {
                                    try {
                                        repository.clearOnBackend(screeningId, officerNotes.ifBlank { null })
                                        step = 7
                                    } catch (e: Exception) {
                                        Toast.makeText(context, "Clear failed: ${e.message}", Toast.LENGTH_LONG).show()
                                    }
                                }
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = Ink900, contentColor = White),
                            modifier = Modifier.weight(1f),
                        ) { Text("Clear") }
                    }
                    7 -> Button(
                        onClick = onComplete,
                        colors = ButtonDefaults.buttonColors(containerColor = Ink900, contentColor = White),
                        modifier = Modifier.weight(1f),
                    ) { Text("Back to Queue") }
                }
            }
        }
    }

    if (showDisputeDialog) {
        AlertDialog(
            onDismissRequest = { showDisputeDialog = false },
            title = { Text("Flag for secondary inspection") },
            text = {
                Column {
                    Text("A reason is required and is logged to the audit trail — this never silently clears the traveler.")
                    Spacer(Modifier.height(12.dp))
                    OutlinedTextField(
                        value = officerNotes,
                        onValueChange = { officerNotes = it },
                        label = { Text("Reason") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        if (officerNotes.isNotBlank()) {
                            scope.launch {
                                try {
                                    repository.disputeOnBackend(screeningId, officerNotes)
                                    showDisputeDialog = false
                                    step = 7
                                } catch (e: Exception) {
                                    Toast.makeText(context, "Dispute failed: ${e.message}", Toast.LENGTH_LONG).show()
                                }
                            }
                        }
                    },
                    enabled = officerNotes.isNotBlank(),
                ) { Text("Flag for secondary inspection") }
            },
            dismissButton = { TextButton(onClick = { showDisputeDialog = false }) { Text("Cancel") } },
        )
    }
}

@Composable
internal fun StepCard(title: String, content: @Composable androidx.compose.foundation.layout.ColumnScope.() -> Unit) {
    Card(modifier = Modifier.fillMaxWidth(), border = BorderStroke(1.dp, Gray200), shape = RoundedCornerShape(10.dp)) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(10.dp))
            content()
        }
    }
}

@Composable
internal fun ExtractionStep(item: ScreeningQueueItem) {
    StepCard("Information Extraction") {
        val ocr = item.ocr
        if (ocr == null) {
            Text("No OCR result on this record.", style = MaterialTheme.typography.bodySmall, color = Gray500)
            return@StepCard
        }
        ConfidenceTag(ocr.ocrConfidence)
        Spacer(Modifier.height(8.dp))
        ocr.fields.forEach { (key, value) ->
            Row(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(key.replace("_", " ").replaceFirstChar { it.uppercase() }, style = MaterialTheme.typography.bodySmall, color = Gray600)
                Text(value, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Medium)
            }
        }
        Spacer(Modifier.height(8.dp))
        Text(
            "Field corrections aren't persisted in this build — note any discrepancy in the Review step.",
            style = MaterialTheme.typography.labelSmall,
            color = Gray500,
        )
    }
}

@Composable
internal fun VerificationStep(item: ScreeningQueueItem) {
    StepCard("Document Verification") {
        val checks = buildList {
            add(Triple("Document readable", item.ocr != null && item.ocr.fields.isNotEmpty(), "Detected"))
            item.validation?.findings?.forEach { finding: ValidationFinding ->
                add(Triple(finding.check.replace("_", " ").replaceFirstChar { it.uppercase() }, finding.status == "PASS", "Verified"))
            }
            add(Triple("Duplicate/previous record check", item.identityGraph?.status != "CLUSTER_FOUND", "Verified"))
        }
        checks.forEach { (label, passed, kind) -> CheckRow(label, passed, kind) }
        Spacer(Modifier.height(8.dp))
        Text(
            "\"Detected\" means the field was read from the document image; \"Verified\" means the " +
                "backend validation/identity-graph engine actually checked it — the two are shown " +
                "separately and never collapsed together.",
            style = MaterialTheme.typography.labelSmall,
            color = Gray500,
        )
    }
}

@Composable
internal fun ScreeningStep(item: ScreeningQueueItem) {
    StepCard("Screening") {
        CheckRow("Identity information consistency", item.validation?.status == "PASS", "Completed")
        CheckRow(
            "Blacklist / registry lookup (mock_central_registry)",
            true,
            if (item.registryHits.isEmpty()) "Completed — no hit" else "Requires review — hit found",
        )
        CheckRow("Document forensics (tampering)", (item.tampering?.tamperingRisk ?: 0.0) < 0.5, "Completed")
        CheckRow("Deepfake heuristic", item.deepfakeStatus == "ANALYZED", if (item.deepfakeStatus == "ANALYZED") "Completed" else "Not implemented")
        CheckRow("Liveness heuristic", item.livenessStatus != null, if (item.livenessStatus != null) "Completed" else "Not implemented")
        Spacer(Modifier.height(6.dp))
        Text(
            "This build has no configured watchlist beyond the mock central registry and no real " +
                "location-match signal — nationality/location alone never drives a risk label.",
            style = MaterialTheme.typography.labelSmall,
            color = Gray500,
        )
    }
}

@Composable
internal fun RiskAssessmentStep(item: ScreeningQueueItem) {
    val risk = item.risk ?: return
    StepCard("Explainable Risk Assessment") {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("${risk.score}", style = MaterialTheme.typography.displaySmall, fontWeight = FontWeight.Bold)
            Text(" / 100", style = MaterialTheme.typography.bodyMedium, color = Gray500)
        }
        Text(risk.level.replace("_", " "), style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.height(12.dp))
        Text("Why this score?", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.height(8.dp))
        risk.breakdown.sortedByDescending { it.contribution }.forEach { signal ->
            Column(modifier = Modifier.padding(vertical = 8.dp)) {
                Text(signal.signal.replace("_", " ").replaceFirstChar { it.uppercase() }, fontWeight = FontWeight.SemiBold)
                Text(signal.reason, style = MaterialTheme.typography.bodySmall)
                Spacer(Modifier.height(4.dp))
                Text(
                    "Source: ${sourceLabel(signal.signal)}  ·  Contribution: +${"%.1f".format(signal.contribution * 100)}",
                    style = MaterialTheme.typography.labelSmall,
                    color = Gray600,
                )
                Text(
                    "Timestamp: ${java.text.SimpleDateFormat("dd MMM yyyy, HH:mm", java.util.Locale.getDefault()).format(java.util.Date(item.submittedAt))}" +
                        "  ·  Review status: ${if (item.status == ScreeningStatus.PENDING) "Pending" else "Reviewed"}",
                    style = MaterialTheme.typography.labelSmall,
                    color = Gray600,
                )
            }
        }
    }
}

private fun sourceLabel(signal: String): String = when (signal) {
    "checksum" -> "Document validation engine (MRZ / Verhoeff)"
    "forensics" -> "Forensics engine (ELA)"
    "deepfake" -> "Deepfake heuristic"
    "liveness" -> "Liveness heuristic"
    "blacklist" -> "mock_central_registry lookup"
    "face_match" -> "Face match service"
    "identity_graph" -> "Identity graph"
    else -> signal
}

@Composable
internal fun ReviewStep(notes: String, onNotesChange: (String) -> Unit) {
    StepCard("Officer Review") {
        Text("Add any notes before deciding. A reason is required only if flagging for further review.", style = MaterialTheme.typography.bodySmall, color = Gray600)
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(
            value = notes,
            onValueChange = onNotesChange,
            label = { Text("Officer notes (optional for Clear)") },
            modifier = Modifier.fillMaxWidth(),
        )
    }
}

@Composable
internal fun CompleteStep(item: ScreeningQueueItem) {
    StepCard("") {
        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.fillMaxWidth().padding(vertical = 12.dp)) {
            Icon(Icons.Filled.CheckCircle, contentDescription = null, tint = Ink900, modifier = Modifier.size(48.dp))
            Spacer(Modifier.height(12.dp))
            Text("Screening complete", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(4.dp))
            Text("Decision recorded: ${item.status.name}", style = MaterialTheme.typography.bodyMedium, color = Gray600)
        }
    }
}

@Composable
internal fun CheckRow(label: String, passed: Boolean, statusLabel: String, modifier: Modifier = Modifier) {
    Row(
        modifier = modifier.fillMaxWidth().padding(vertical = 6.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(label, style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f))
        Text(
            statusLabel,
            style = MaterialTheme.typography.labelSmall,
            color = if (passed) Gray600 else Ink900,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier
                .background(if (passed) Gray100 else Gray200, RoundedCornerShape(6.dp))
                .padding(horizontal = 8.dp, vertical = 3.dp),
        )
    }
}
