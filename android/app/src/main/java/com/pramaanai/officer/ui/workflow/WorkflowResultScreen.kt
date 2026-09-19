package com.pramaanai.officer.ui.workflow

import android.widget.Toast
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.material.icons.filled.RemoveCircleOutline
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import com.pramaanai.officer.data.model.RiskResult
import com.pramaanai.officer.ui.components.LocalPhoto
import com.pramaanai.officer.ui.theme.BorderDark
import com.pramaanai.officer.ui.theme.CardDark
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Circle
import androidx.compose.material.icons.filled.Error
import androidx.compose.material.icons.filled.WarningAmber
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
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
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.pramaanai.officer.R
import com.pramaanai.officer.data.ScreeningRepository
import com.pramaanai.officer.data.model.ScreeningQueueItem
import com.pramaanai.officer.data.model.ScreeningStatus
import com.pramaanai.officer.data.model.ValidationFinding
import com.pramaanai.officer.ui.components.ConfidenceTag
import com.pramaanai.officer.ui.components.GridPatternBackground
import com.pramaanai.officer.ui.components.IdentityClusterGraph
import com.pramaanai.officer.ui.components.WorkflowStepper
import com.pramaanai.officer.ui.review.ReasonDialog
import com.pramaanai.officer.ui.review.flaggedReasons
import com.pramaanai.officer.ui.review.friendlyActionError
import com.pramaanai.officer.ui.theme.AccentGreen
import com.pramaanai.officer.ui.theme.BackgroundDark
import com.pramaanai.officer.ui.theme.Gray100
import com.pramaanai.officer.ui.theme.Gray200
import com.pramaanai.officer.ui.theme.Gray500
import com.pramaanai.officer.ui.theme.Gray600
import com.pramaanai.officer.ui.theme.Ink900
import com.pramaanai.officer.ui.theme.SuccessGreen
import com.pramaanai.officer.ui.theme.WarningAmber
import com.pramaanai.officer.ui.theme.DestructiveRed
import com.pramaanai.officer.ui.theme.White
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
    var showClearDialog by remember { mutableStateOf(false) }
    var showSecondaryDialog by remember { mutableStateOf(false) }
    var showHoldDialog by remember { mutableStateOf(false) }
    var showSendDialog by remember { mutableStateOf(false) }

    LaunchedEffect(screeningId) { item = repository.getById(screeningId) }

    Scaffold(topBar = { TopAppBar(title = { Text("New Screening") }) }) { padding ->
        GridPatternBackground(modifier = Modifier.padding(padding)) {
            val currentItem = item
            if (currentItem == null) {
                Column(Modifier.fillMaxSize().padding(16.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                    CircularProgressIndicator()
                }
                return@GridPatternBackground
            }

            Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
                Column(Modifier.padding(bottom = 16.dp)) { WorkflowStepper(currentStep = step) }
                LazyColumn(modifier = Modifier.weight(1f).fillMaxWidth()) {
                    item {
                        when (step) {
                            2 -> ExtractionStep(currentItem)
                            3 -> VerificationStep(currentItem)
                            4 -> ScreeningStep(currentItem)
                            5 -> RiskAssessmentStep(currentItem)
                            6 -> ReviewStep(currentItem)
                            7 -> CompleteStep(currentItem)
                        }
                        Spacer(Modifier.height(24.dp))
                    }
                }
                Row(modifier = Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    if (step in 3..6) {
                        OutlinedButton(onClick = { step-- }, modifier = Modifier.weight(1f)) { Text("Back") }
                    }
                    when (step) {
                        in 2..5 -> Button(
                            onClick = { step++ },
                            colors = ButtonDefaults.buttonColors(containerColor = AccentGreen, contentColor = BackgroundDark),
                            modifier = Modifier.weight(1f),
                        ) { Text("Next") }
                        6 -> {
                            Button(
                                onClick = { showClearDialog = true },
                                colors = ButtonDefaults.buttonColors(containerColor = SuccessGreen, contentColor = BackgroundDark),
                                modifier = Modifier.weight(1f),
                            ) { Text(stringResource(R.string.common_clear), maxLines = 1) }
                            OutlinedButton(
                                onClick = { showSecondaryDialog = true },
                                modifier = Modifier.weight(1f),
                            ) { Text(stringResource(R.string.common_secondary_review), maxLines = 1) }
                            OutlinedButton(
                                onClick = { showHoldDialog = true },
                                modifier = Modifier.weight(1f),
                            ) { Text(stringResource(R.string.common_hold_refer), maxLines = 1) }
                        }
                        7 -> Button(
                            onClick = onComplete,
                            colors = ButtonDefaults.buttonColors(containerColor = AccentGreen, contentColor = BackgroundDark),
                            modifier = Modifier.weight(1f),
                        ) { Text("Back to Queue") }
                    }
                }
            }
        }
    }

    val reasons = item?.let { flaggedReasons(it) }.orEmpty()

    if (showClearDialog) {
        AlertDialog(
            onDismissRequest = { showClearDialog = false },
            title = { Text("Clear this screening") },
            text = { Text("This traveler is cleared to proceed. This decision will be logged and cannot be undone.") },
            confirmButton = {
                Button(
                    onClick = {
                        scope.launch {
                            try {
                                repository.decideCaseOnBackend(screeningId, "CLEAR", null)
                                item = repository.getById(screeningId)
                                showClearDialog = false
                                step = 7
                            } catch (e: Exception) {
                                showClearDialog = false
                                Toast.makeText(context, friendlyActionError("clear this screening", e), Toast.LENGTH_LONG).show()
                            }
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = SuccessGreen, contentColor = BackgroundDark)
                ) {
                    Text("Clear")
                }
            },
            dismissButton = {
                TextButton(onClick = { showClearDialog = false }) {
                    Text("Cancel")
                }
            }
        )
    }

    if (showSecondaryDialog) {
        ReasonDialog(
            title = "Secondary Review Required",
            intro = "This case requires additional review. The reasons below will be attached.",
            reasons = reasons,
            confirmLabel = "Send for Secondary Review",
            onDismiss = { showSecondaryDialog = false },
            onConfirm = {
                scope.launch {
                    try {
                        repository.decideCaseOnBackend(screeningId, "SECONDARY_REVIEW", reasons.joinToString("; "))
                        item = repository.getById(screeningId)
                        showSecondaryDialog = false
                        step = 7
                    } catch (e: Exception) {
                        showSecondaryDialog = false
                        Toast.makeText(context, friendlyActionError("send for secondary review", e), Toast.LENGTH_LONG).show()
                    }
                }
            },
        )
    }

    if (showHoldDialog) {
        ReasonDialog(
            title = "Hold / Refer",
            intro = "This traveler should be held for further investigation or referred. The reasons below will be attached.",
            reasons = reasons,
            confirmLabel = "Hold / Refer",
            onDismiss = { showHoldDialog = false },
            onConfirm = {
                scope.launch {
                    try {
                        repository.decideCaseOnBackend(screeningId, "HOLD_REFER", reasons.joinToString("; "))
                        item = repository.getById(screeningId)
                        showHoldDialog = false
                        step = 7
                    } catch (e: Exception) {
                        showHoldDialog = false
                        Toast.makeText(context, friendlyActionError("hold/refer this case", e), Toast.LENGTH_LONG).show()
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
                        item = repository.getById(screeningId)
                        showSendDialog = false
                        step = 7
                    } catch (e: Exception) {
                        showSendDialog = false
                        Toast.makeText(context, friendlyActionError("send this case", e), Toast.LENGTH_LONG).show()
                    }
                }
            },
        )
    }
}

@Composable
fun StepCard(title: String, content: @Composable androidx.compose.foundation.layout.ColumnScope.() -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = CardDark),
        border = BorderStroke(1.dp, BorderDark),
        shape = RoundedCornerShape(14.dp),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            if (title.isNotBlank()) {
                Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(12.dp))
            }
            content()
        }
    }
}

// Fields the backend's cross-check actually reads (see
// app/services/validation/cross_check.py), in the order an officer would
// read a passport's data page. Always listed — a field the scan couldn't
// read shows as "Not detected" rather than silently disappearing.
private val EXTRACTED_FIELD_ORDER = listOf(
    "name" to "Full name",
    "passport_number" to "Document number",
    "nationality" to "Nationality",
    "date_of_birth" to "Date of birth",
    "gender" to "Gender",
    "date_of_expiry" to "Date of expiry",
)

@Composable
/** [wholeImage] letterboxes the photo so nothing is cropped — used for the
 * document, where an officer needs to see every printed line, not a face-
 * centred crop. */
fun PhotoTile(caption: String, path: String?, modifier: Modifier = Modifier, wholeImage: Boolean = false) {
    Column(modifier = modifier) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .aspectRatio(0.9f)
                .clip(RoundedCornerShape(10.dp))
                .background(BackgroundDark)
                .border(1.dp, BorderDark, RoundedCornerShape(10.dp)),
            contentAlignment = Alignment.Center,
        ) {
            LocalPhoto(
                path = path,
                modifier = Modifier.fillMaxSize(),
                contentScale = if (wholeImage) androidx.compose.ui.layout.ContentScale.Fit else androidx.compose.ui.layout.ContentScale.Crop,
            )
        }
        Spacer(Modifier.height(6.dp))
        Text(caption, style = MaterialTheme.typography.labelSmall, color = Gray500)
    }
}

@Composable
fun ExtractedFieldRow(label: String, value: String?) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 7.dp),
        verticalAlignment = Alignment.Top,
    ) {
        Text(label, style = MaterialTheme.typography.bodySmall, color = Gray600, modifier = Modifier.weight(0.42f))
        if (value.isNullOrBlank()) {
            Text(
                "Not detected",
                style = MaterialTheme.typography.bodySmall,
                color = Gray500,
                fontStyle = FontStyle.Italic,
                textAlign = TextAlign.End,
                modifier = Modifier.weight(0.58f),
            )
        } else {
            Text(
                value,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold,
                textAlign = TextAlign.End,
                modifier = Modifier.weight(0.58f),
            )
        }
    }
    Box(Modifier.fillMaxWidth().height(1.dp).background(BorderDark))
}

@Composable
fun ExtractionStep(item: ScreeningQueueItem) {
    StepCard("Information Extraction") {
        // The actual captured photos (kept on this device only) — an
        // officer reading extracted text should be able to see what it was
        // read from.
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
            PhotoTile("Document photo", item.documentImagePath, Modifier.weight(1f), wholeImage = true)
            PhotoTile("Live capture", item.selfieImagePath, Modifier.weight(1f))
        }
        Spacer(Modifier.height(14.dp))
        val ocr = item.ocr
        if (ocr == null) {
            Text("No OCR result on this record.", style = MaterialTheme.typography.bodySmall, color = Gray500)
            return@StepCard
        }
        ConfidenceTag(ocr.ocrConfidence)
        Spacer(Modifier.height(6.dp))
        EXTRACTED_FIELD_ORDER.forEach { (key, label) -> ExtractedFieldRow(label, ocr.fields[key]) }
        ocr.fields.filterKeys { key -> EXTRACTED_FIELD_ORDER.none { it.first == key } }.forEach { (key, value) ->
            ExtractedFieldRow(key.replace("_", " ").replaceFirstChar { it.uppercase() }, value)
        }
        val mrzLines = (ocr.mrzLines as List<String>?).orEmpty()
        if (mrzLines.isNotEmpty()) {
            Spacer(Modifier.height(12.dp))
            Text("Machine-readable zone", style = MaterialTheme.typography.labelMedium, color = Gray600)
            Spacer(Modifier.height(6.dp))
            Text(
                mrzLines.joinToString("\n"),
                style = MaterialTheme.typography.labelSmall,
                fontFamily = FontFamily.Monospace,
                color = Gray600,
                modifier = Modifier
                    .fillMaxWidth()
                    .background(BackgroundDark, RoundedCornerShape(8.dp))
                    .padding(10.dp),
            )
        }
        Spacer(Modifier.height(12.dp))
        Text(
            "Read from the document on this device — nothing here was typed in by hand. " +
                "A misread value shows up as an inconsistency in the checks that follow.",
            style = MaterialTheme.typography.labelSmall,
            color = Gray500,
        )
    }
}

// ---- Checks ---------------------------------------------------------

/** PASS / REVIEW / ALERT / NOT_RUN — each with its own icon *and* word, so
 * meaning never rests on color alone. NOT_RUN is deliberately distinct from
 * PASS: a check that didn't run on this device must never look like a clean
 * result. */
enum class CheckState { PASS, REVIEW, ALERT, NOT_RUN }

data class CheckItem(val label: String, val state: CheckState, val detail: String?)

private fun RiskResult?.signal(name: String) = this?.breakdown?.firstOrNull { it.signal == name }

private fun signalCheck(risk: RiskResult?, signal: String, label: String, notRunDetail: String): CheckItem {
    val s = risk.signal(signal) ?: return CheckItem(label, CheckState.NOT_RUN, notRunDetail)
    val state = when {
        s.rawRisk <= 0.0001 -> CheckState.PASS
        s.rawRisk >= 0.7 -> CheckState.ALERT
        else -> CheckState.REVIEW
    }
    return CheckItem(label, state, s.reason)
}

private fun prettyCheck(check: String) = check.replace("_", " ").replaceFirstChar { it.uppercase() }

private fun documentChecks(item: ScreeningQueueItem): List<CheckItem> = buildList {
    val readable = item.ocr != null && item.ocr.fields.values.any { it.isNotBlank() }
    add(
        CheckItem(
            "Document read",
            if (readable) CheckState.PASS else CheckState.REVIEW,
            if (readable) "${item.ocr!!.fields.values.count { it.isNotBlank() }} field(s) read from the document"
            else "No fields could be read — rescan the document in better light",
        ),
    )
    val findings = item.validation?.findings
    if (findings.isNullOrEmpty()) {
        add(CheckItem("Document validation", CheckState.NOT_RUN, "No checksum or cross-check evidence was available"))
    } else {
        findings.forEach { f ->
            add(
                CheckItem(
                    prettyCheck(f.check),
                    when {
                        f.status == "PASS" -> CheckState.PASS
                        f.severity == "HIGH" -> CheckState.ALERT
                        else -> CheckState.REVIEW
                    },
                    f.reason,
                ),
            )
        }
    }
    add(signalCheck(item.risk, "citizen_registry", "Citizen registry match", "Not evaluated for this screening"))
    add(signalCheck(item.risk, "duplicate_document", "Duplicate / reused document", "Not evaluated for this screening"))
}

private fun screeningChecks(item: ScreeningQueueItem): List<CheckItem> = buildList {
    add(
        CheckItem(
            "Watchlist registry (demo data)",
            if (item.registryHits.isEmpty()) CheckState.PASS else CheckState.ALERT,
            if (item.registryHits.isEmpty()) "No matching entry in the mock watchlist"
            else item.registryHits.joinToString("; ") { "${it.matchType} match on ${it.fullName} (${it.registryReason})" },
        ),
    )
    add(signalCheck(item.risk, "face_detection", "Face in live capture", "Not run on this device"))
    val face = item.face
    add(
        if (face == null) CheckItem("Face match", CheckState.NOT_RUN, "Needs both a document photo and a live capture")
        else CheckItem("Face match", if (face.match) CheckState.PASS else CheckState.REVIEW, face.reason),
    )
    val liveness = item.livenessStatus
    add(
        if (liveness == null) CheckItem("Liveness / spoof check", CheckState.NOT_RUN, "Not computed on this device")
        else CheckItem("Liveness / spoof check", if (liveness == "LIVE") CheckState.PASS else CheckState.REVIEW, item.livenessReason),
    )
    val tampering = item.tampering
    add(
        if (tampering == null) CheckItem("Document forensics (ELA)", CheckState.NOT_RUN, "Not computed on this device")
        else CheckItem(
            "Document forensics (ELA)",
            if (tampering.tamperingRisk < 0.5) CheckState.PASS else CheckState.REVIEW,
            tampering.findings.firstOrNull()?.reason ?: "Tampering risk ${(tampering.tamperingRisk * 100).toInt()}%",
        ),
    )
    val deepfake = item.deepfakeStatus
    add(
        if (deepfake == null || deepfake == "NOT_IMPLEMENTED") CheckItem("Deepfake heuristic", CheckState.NOT_RUN, "Not computed on this device")
        else CheckItem("Deepfake heuristic", CheckState.PASS, item.deepfakeReason),
    )
    val graph = item.identityGraph
    add(
        if (graph == null) CheckItem("Identity graph", CheckState.NOT_RUN, "Needs a live capture to compare against earlier records")
        else CheckItem(
            "Identity graph",
            if (graph.status == "CLUSTER_FOUND") CheckState.ALERT else CheckState.PASS,
            graph.reason,
        ),
    )
}

@Composable
fun CheckItemRow(check: CheckItem) {
    val (icon, tint, word) = when (check.state) {
        CheckState.PASS -> Triple(Icons.Filled.CheckCircle, SuccessGreen, "Passed")
        CheckState.REVIEW -> Triple(Icons.Filled.WarningAmber, WarningAmber, "Review")
        CheckState.ALERT -> Triple(Icons.Filled.Error, DestructiveRed, "Alert")
        CheckState.NOT_RUN -> Triple(Icons.Filled.RemoveCircleOutline, Gray500, "Not run")
    }
    Row(modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp), verticalAlignment = Alignment.Top) {
        Icon(icon, contentDescription = word, tint = tint, modifier = Modifier.size(20.dp).padding(top = 1.dp))
        Spacer(Modifier.width(12.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(check.label, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium, color = Ink900)
            if (!check.detail.isNullOrBlank()) {
                Text(check.detail, style = MaterialTheme.typography.labelSmall, color = Gray600)
            }
        }
        Spacer(Modifier.width(8.dp))
        Text(word, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.SemiBold, color = tint)
    }
}

@Composable
fun VerificationStep(item: ScreeningQueueItem) {
    StepCard("Document Verification") {
        documentChecks(item).forEach { CheckItemRow(it) }
        Spacer(Modifier.height(6.dp))
        Text(
            "Each line is a real check the backend ran on the values above, with the exact values it " +
                "compared. \"Not run\" means the check couldn't be performed — never a silent pass.",
            style = MaterialTheme.typography.labelSmall,
            color = Gray500,
        )
    }
}

@Composable
fun ScreeningStep(item: ScreeningQueueItem) {
    StepCard("Screening") {
        screeningChecks(item).forEach { CheckItemRow(it) }
        Spacer(Modifier.height(6.dp))
        Text(
            "This build has no configured watchlist beyond the mock registry and no real location-match " +
                "signal — nationality or location alone never drives a risk label.",
            style = MaterialTheme.typography.labelSmall,
            color = Gray500,
        )
    }
}

@Composable
fun RiskAssessmentStep(item: ScreeningQueueItem) {
    VerificationResultCard(item)
}

@Composable
fun VerificationResultCard(item: ScreeningQueueItem) {
    val risk = item.risk
    val riskLevel = risk?.level ?: "PENDING"
    val riskScore = risk?.score ?: 0

    val (riskColor, riskIcon, riskLabel) = when (riskLevel) {
        "HIGH_RISK" -> Triple(DestructiveRed, Icons.Filled.Error, "HIGH RISK")
        "MEDIUM_RISK" -> Triple(WarningAmber, Icons.Filled.WarningAmber, "MEDIUM RISK")
        "LOW_RISK" -> Triple(SuccessGreen, Icons.Filled.CheckCircle, "LOW RISK")
        else -> Triple(Gray600, Icons.Filled.Circle, "PENDING")
    }
    val checks = documentChecks(item) + screeningChecks(item)
    val passed = checks.count { it.state == CheckState.PASS }
    val flagged = checks.count { it.state == CheckState.REVIEW || it.state == CheckState.ALERT }
    val notRun = checks.count { it.state == CheckState.NOT_RUN }

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = CardDark),
        shape = RoundedCornerShape(16.dp),
        border = BorderStroke(1.5.dp, riskColor.copy(alpha = 0.55f)),
    ) {
        Column(modifier = Modifier.padding(18.dp)) {
            // Who — icon + name/subtitle take the row's remaining width, so a
            // long or unusual name wraps instead of squeezing the score.
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier.size(44.dp).background(riskColor.copy(alpha = 0.15f), CircleShape),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(riskIcon, contentDescription = null, tint = riskColor, modifier = Modifier.size(24.dp))
                }
                Spacer(Modifier.width(14.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        item.travelerName.ifBlank { "Name not read from document" },
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                        color = Ink900,
                    )
                    Text(
                        listOf(item.nationality, item.documentType.replace("_", " "))
                            .filter { it.isNotBlank() }.joinToString(" · "),
                        style = MaterialTheme.typography.bodySmall,
                        color = Gray600,
                    )
                }
            }
            Spacer(Modifier.height(16.dp))

            // How risky — its own row so the label and score can never wrap.
            Row(verticalAlignment = Alignment.Bottom, modifier = Modifier.fillMaxWidth()) {
                Text("$riskScore", style = MaterialTheme.typography.displayMedium, fontWeight = FontWeight.Bold, color = riskColor)
                Text(" / 100", style = MaterialTheme.typography.bodyMedium, color = Gray500, modifier = Modifier.padding(bottom = 8.dp))
                Spacer(Modifier.weight(1f))
                Text(
                    riskLabel,
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.Bold,
                    color = riskColor,
                    maxLines = 1,
                    modifier = Modifier
                        .background(riskColor.copy(alpha = 0.14f), RoundedCornerShape(8.dp))
                        .padding(horizontal = 12.dp, vertical = 6.dp),
                )
            }
            Spacer(Modifier.height(10.dp))
            Box(Modifier.fillMaxWidth().height(6.dp).clip(RoundedCornerShape(3.dp)).background(BorderDark)) {
                Box(
                    Modifier
                        .fillMaxWidth(fraction = (riskScore / 100f).coerceIn(0f, 1f))
                        .fillMaxHeight()
                        .background(riskColor, RoundedCornerShape(3.dp)),
                )
            }
            Spacer(Modifier.height(10.dp))
            Text(
                if (risk?.decision == "MANUAL_REVIEW") "Officer review recommended" else "No review flags raised",
                style = MaterialTheme.typography.labelLarge,
                fontWeight = FontWeight.SemiBold,
                color = Ink900,
            )
            if (!risk?.topReason.isNullOrBlank()) {
                Spacer(Modifier.height(4.dp))
                Text(risk!!.topReason, style = MaterialTheme.typography.bodySmall, color = Gray600)
            }
            Spacer(Modifier.height(6.dp))
            Text(
                "A risk alert to support the officer's judgment — not a finding about the traveler.",
                style = MaterialTheme.typography.labelSmall,
                color = Gray500,
            )

            Spacer(Modifier.height(16.dp))
            Box(Modifier.fillMaxWidth().height(1.dp).background(BorderDark))
            Spacer(Modifier.height(14.dp))

            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("Checks", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold, color = Ink900)
                Text(
                    "$passed passed · $flagged to review · $notRun not run",
                    style = MaterialTheme.typography.labelSmall,
                    color = Gray500,
                )
            }
            Spacer(Modifier.height(4.dp))
            checks.forEach { CheckItemRow(it) }

            if (item.identityGraph?.members != null && item.identityGraph.members.size >= 2) {
                Spacer(Modifier.height(12.dp))
                Box(Modifier.fillMaxWidth().height(1.dp).background(BorderDark))
                Spacer(Modifier.height(12.dp))
                IdentityClusterGraph(members = item.identityGraph.members)
            }

            if (risk != null && risk.breakdown.isNotEmpty()) {
                Spacer(Modifier.height(12.dp))
                Box(Modifier.fillMaxWidth().height(1.dp).background(BorderDark))
                Spacer(Modifier.height(14.dp))
                Text("Risk breakdown", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold, color = Ink900)
                Spacer(Modifier.height(8.dp))
                risk.breakdown.sortedByDescending { it.contribution }.forEach { RiskSignalRow(it) }
            }
        }
    }
}

fun signalTitle(signal: String): String = when (signal) {
    "checksum" -> "Document checks"
    "forensics" -> "Document forensics (ELA)"
    "deepfake" -> "Deepfake heuristic"
    "liveness" -> "Liveness / spoof"
    "blacklist" -> "Watchlist registry"
    "face_match" -> "Face match"
    "face_detection" -> "Face in live capture"
    "identity_graph" -> "Identity graph"
    "duplicate_document" -> "Duplicate / reused document"
    "citizen_registry" -> "Citizen registry"
    else -> signal.replace("_", " ").replaceFirstChar { it.uppercase() }
}

@Composable
fun RiskSignalRow(signal: com.pramaanai.officer.data.model.RiskSignalBreakdown) {
    val contributionPct = (signal.contribution * 100).toInt()
    Column(modifier = Modifier.padding(vertical = 6.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text(
                signalTitle(signal.signal),
                style = MaterialTheme.typography.bodySmall,
                fontWeight = FontWeight.Medium,
                color = Ink900,
            )
            Text(
                "+$contributionPct%",
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.Bold,
                color = AccentGreen,
            )
        }
        Text(
            signal.reason,
            style = MaterialTheme.typography.labelSmall,
            color = Gray600,
        )
        Spacer(Modifier.height(4.dp))
        // Contribution bar
        androidx.compose.foundation.layout.Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(4.dp)
                .background(Gray200, RoundedCornerShape(2.dp)),
        ) {
            androidx.compose.foundation.layout.Box(
                modifier = Modifier
                    .fillMaxWidth(fraction = signal.contribution.toFloat().coerceIn(0f, 1f))
                    .fillMaxHeight()
                    .background(AccentGreen, RoundedCornerShape(2.dp)),
            )
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
fun ReviewStep(item: ScreeningQueueItem) {
    val reasons = flaggedReasons(item)
    StepCard("Officer Review") {
        Text(
            "Decide with your own procedure. If you flag this screening or send it on, the reasons below are recorded automatically — nothing to type.",
            style = MaterialTheme.typography.bodySmall,
            color = Gray600,
        )
        Spacer(Modifier.height(12.dp))
        Text("Raised on this screening", style = MaterialTheme.typography.labelMedium, color = Gray600)
        Spacer(Modifier.height(6.dp))
        reasons.forEach { reason ->
            Row(modifier = Modifier.padding(vertical = 4.dp)) {
                Text("•  ", color = AccentGreen, fontWeight = FontWeight.Bold)
                Text(reason, style = MaterialTheme.typography.bodyMedium)
            }
        }
        Spacer(Modifier.height(10.dp))
        Text(
            "A risk alert to support the officer's judgment — not a finding about the traveler.",
            style = MaterialTheme.typography.labelSmall,
            color = Gray500,
        )
    }
}

@Composable
fun CompleteStep(item: ScreeningQueueItem) {
    val (statusColor, statusIcon, statusText) = when (item.status) {
        ScreeningStatus.CLEARED -> Triple(SuccessGreen, Icons.Filled.CheckCircle, "Cleared")
        ScreeningStatus.DISPUTED -> Triple(WarningAmber, Icons.Filled.WarningAmber, "Flagged for Review")
        ScreeningStatus.SENT -> Triple(AccentGreen, Icons.Filled.CheckCircle, "Sent to Immigration")
        else -> Triple(Gray600, Icons.Filled.CheckCircle, item.status.name)
    }

    StepCard("") {
        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.fillMaxWidth().padding(vertical = 12.dp)) {
            Icon(statusIcon, contentDescription = null, tint = statusColor, modifier = Modifier.size(48.dp))
            Spacer(Modifier.height(12.dp))
            Text("Screening complete", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(4.dp))
            Text("Decision recorded: $statusText", style = MaterialTheme.typography.bodyMedium, color = Gray600)
            if (!item.officerNotes.isNullOrBlank()) {
                Spacer(Modifier.height(8.dp))
                Text("Notes: ${item.officerNotes}", style = MaterialTheme.typography.bodySmall, color = Gray500)
            }
        }
    }
}

@Composable
fun CheckRow(label: String, passed: Boolean, statusLabel: String, modifier: Modifier = Modifier) {
    Row(
        modifier = modifier.fillMaxWidth().padding(vertical = 6.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(label, style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f))
        Text(
            statusLabel,
            style = MaterialTheme.typography.labelSmall,
            color = if (passed) SuccessGreen else WarningAmber,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier
                .background((if (passed) SuccessGreen else WarningAmber).copy(alpha = 0.14f), RoundedCornerShape(6.dp))
                .padding(horizontal = 8.dp, vertical = 3.dp),
        )
    }
}