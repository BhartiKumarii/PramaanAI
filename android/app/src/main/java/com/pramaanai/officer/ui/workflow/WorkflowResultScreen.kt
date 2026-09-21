package com.pramaanai.officer.ui.workflow

import android.widget.Toast
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
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
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Share
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
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
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
import com.pramaanai.officer.data.humanSignalTitle
import com.pramaanai.officer.data.humanSignalReason
import com.pramaanai.officer.data.humanTopReason
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
    var showSendDialog by remember { mutableStateOf(false) }

    LaunchedEffect(screeningId) { item = repository.getById(screeningId) }

    Scaffold(topBar = { TopAppBar(title = { Text(stringResource(R.string.new_screening_title)) }) }) { padding ->
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
                            4 -> RiskAssessmentStep(currentItem)
                            5 -> ReviewStep(currentItem)
                            6 -> CompleteStep(currentItem)
                        }
                        Spacer(Modifier.height(24.dp))
                    }
                }
                Row(modifier = Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    if (step in 3..5) {
                        OutlinedButton(onClick = { step-- }, modifier = Modifier.weight(1f)) { Text(stringResource(R.string.common_back)) }
                    }
                    when (step) {
                        in 2..4 -> Button(
                            onClick = { step++ },
                            colors = ButtonDefaults.buttonColors(containerColor = AccentGreen, contentColor = BackgroundDark),
                            modifier = Modifier.weight(1f),
                        ) { Text(stringResource(R.string.common_next)) }
                        5 -> {
                            Button(
                                onClick = { showSendDialog = true },
                                colors = ButtonDefaults.buttonColors(containerColor = AccentGreen, contentColor = BackgroundDark),
                                modifier = Modifier.weight(1f),
                            ) { Text(stringResource(R.string.submit_for_review), maxLines = 1) }
                        }
                        6 -> Button(
                            onClick = onComplete,
                            colors = ButtonDefaults.buttonColors(containerColor = AccentGreen, contentColor = BackgroundDark),
                            modifier = Modifier.weight(1f),
                        ) { Text(stringResource(R.string.back_to_queue)) }
                    }
                }
            }
        }
    }

    val reasons = item?.let { flaggedReasons(context, it) }.orEmpty()

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
                        step = 6
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

/** Per-document field schema: (ocr_key, display_label).
 * Only fields in this list are shown for that document type.
 * If a field is applicable but not read, it shows "Unable to read" — never "Not detected".
 * Fields NOT in this list for a given doc type are hidden entirely. */
private fun documentFieldSchema(docType: String, ocrFields: Map<String, String>): List<Pair<String, String>> {
    val dt = docType.lowercase()
    // Pick the best available document-number key
    fun numKey(vararg preferred: String): String =
        preferred.firstOrNull { ocrFields.containsKey(it) } ?: preferred.last()

    return when {
        dt.contains("passport") -> listOf(
            "name"              to "Full name",
            numKey("passport_number", "document_number") to "Passport number",
            "nationality"       to "Nationality",
            "date_of_birth"     to "Date of birth",
            "gender"            to "Gender",
            "date_of_issue"     to "Date of issue",
            "date_of_expiry"    to "Date of expiry",
            "place_of_birth"    to "Place of birth",
            "issuing_authority" to "Issuing authority",
            "cid_number"        to "Citizenship ID",        // Bhutan passports
            "citizenship_id"    to "Citizenship ID",
        )
        dt.contains("visa") -> listOf(
            "name"              to "Full name",
            numKey("visa_number", "document_number") to "Visa number",
            "passport_number"   to "Passport number",
            "nationality"       to "Nationality",
            "date_of_birth"     to "Date of birth",
            "visa_type"         to "Visa type / Category",
            "date_of_issue"     to "Issue date",
            "date_of_expiry"    to "Expiry date",
            "entries"           to "Entries permitted",
            "duration"          to "Duration / Validity",
            "issuing_authority" to "Issued at",
        )
        dt.contains("national") || dt.contains("citizenship") || dt.contains("cid") -> listOf(
            "name"              to "Full name",
            numKey("cid_number", "citizenship_id", "document_number") to "ID number",
            "nationality"       to "Nationality",
            "date_of_birth"     to "Date of birth",
            "gender"            to "Gender",
            "date_of_issue"     to "Date of issue",
            "date_of_expiry"    to "Date of expiry",
            "place_of_birth"    to "Place of birth",
            "issuing_authority" to "Issuing authority",
            "address"           to "Address",
        )
        dt.contains("driving") || dt.contains("licence") || dt.contains("license") -> listOf(
            "name"              to "Full name",
            numKey("dl_number", "document_number") to "Licence number",
            "date_of_birth"     to "Date of birth",
            "gender"            to "Gender",
            "nationality"       to "Nationality",
            "date_of_issue"     to "Date of issue",
            "date_of_expiry"    to "Valid until",
            "issuing_authority" to "Issuing authority",
            "vehicle_classes"   to "Licence categories",
            "blood_group"       to "Blood group",
        )
        dt.contains("permit") || dt.contains("ilp") -> listOf(
            "name"              to "Full name",
            numKey("document_number", "permit_number") to "Permit number",
            "nationality"       to "Nationality",
            "date_of_birth"     to "Date of birth",
            "passport_number"   to "Passport / ID number",
            "visa_type"         to "Permit type",
            "date_of_issue"     to "Valid from",
            "date_of_expiry"    to "Valid until",
            "place_of_birth"    to "Permitted area / Route",
            "issuing_authority" to "Issuing authority",
        )
        else -> listOf(  // fallback for unknown doc type
            "name"              to "Full name",
            numKey("passport_number", "document_number") to "Document number",
            "nationality"       to "Nationality",
            "date_of_birth"     to "Date of birth",
            "gender"            to "Gender",
            "date_of_expiry"    to "Date of expiry",
            "date_of_issue"     to "Date of issue",
            "issuing_authority" to "Issuing authority",
        )
    }.distinctBy { it.first }
}

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
fun ExtractedFieldRow(label: String, value: String?, unableToRead: Boolean = false) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 7.dp),
        verticalAlignment = Alignment.Top,
    ) {
        Text(label, style = MaterialTheme.typography.bodySmall, color = Gray600, modifier = Modifier.weight(0.44f))
        when {
            !value.isNullOrBlank() -> Text(
                value,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold,
                textAlign = TextAlign.End,
                modifier = Modifier.weight(0.56f),
            )
            unableToRead -> Text(
                "Unable to read",
                style = MaterialTheme.typography.bodySmall,
                color = WarningAmber,
                fontStyle = FontStyle.Italic,
                textAlign = TextAlign.End,
                modifier = Modifier.weight(0.56f),
            )
            // value null/blank but not unableToRead → field not applicable, don't render
        }
    }
    Box(Modifier.fillMaxWidth().height(1.dp).background(BorderDark))
}

@Composable
fun ExtractionStep(item: ScreeningQueueItem) {
    val ocr = item.ocr
    val docType = item.documentType ?: ocr?.documentType ?: "unknown"

    StepCard("What was read from this document") {
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
            PhotoTile("Document", item.documentImagePath, Modifier.weight(1f), wholeImage = true)
            if (item.documentBackImagePath != null) {
                PhotoTile("Back side", item.documentBackImagePath, Modifier.weight(1f), wholeImage = true)
            }
            PhotoTile("Live photo", item.selfieImagePath, Modifier.weight(1f))
        }

        if (ocr == null) {
            Spacer(Modifier.height(14.dp))
            Text("Document could not be read — please rescan.", style = MaterialTheme.typography.bodySmall, color = WarningAmber)
            return@StepCard
        }

        Spacer(Modifier.height(14.dp))
        ConfidenceTag(ocr.ocrConfidence)
        Spacer(Modifier.height(6.dp))

        // Show only fields defined for this document type.
        // Applicable field with no value → "Unable to read" (amber warning).
        // Field not in schema for this doc type → hidden.
        val schema = documentFieldSchema(docType, ocr.fields)
        schema.forEach { (key, label) ->
            val value = ocr.fields[key]
            // Show the row whether or not we have a value — it's an applicable field
            ExtractedFieldRow(label, value, unableToRead = value.isNullOrBlank())
        }

        // MRZ section (passports only)
        val mrzLines = ocr.mrzLines.orEmpty()
        if (mrzLines.isNotEmpty()) {
            Spacer(Modifier.height(14.dp))
            Text("Machine-Readable Zone", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.SemiBold, color = Gray600)
            Spacer(Modifier.height(6.dp))
            Text(
                mrzLines.joinToString("\n"),
                style = MaterialTheme.typography.labelSmall,
                fontFamily = FontFamily.Monospace,
                color = AccentGreen,
                modifier = Modifier
                    .fillMaxWidth()
                    .background(BackgroundDark, RoundedCornerShape(8.dp))
                    .padding(10.dp),
            )
        }

        Spacer(Modifier.height(12.dp))
        Text(
            "All values read from the document by this device. " +
                "Nothing was typed in by hand. Fields marked \"Unable to read\" may need a rescan.",
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

@Composable
private fun documentChecks(item: ScreeningQueueItem): List<CheckItem> = buildList {
    val readable = item.ocr != null && item.ocr.fields.values.any { it.isNotBlank() }
    add(
        CheckItem(
            stringResource(R.string.check_document_read),
            if (readable) CheckState.PASS else CheckState.REVIEW,
            if (readable) stringResource(R.string.check_fields_read, item.ocr!!.fields.values.count { it.isNotBlank() })
            else stringResource(R.string.check_rescan_document),
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

@Composable
private fun screeningChecks(item: ScreeningQueueItem): List<CheckItem> = buildList {
    add(
        CheckItem(
            "Watchlist check",
            if (item.registryHits.isEmpty()) CheckState.PASS else CheckState.ALERT,
            if (item.registryHits.isEmpty()) "Document number is not on the watchlist"
            else item.registryHits.joinToString("; ") { "${it.fullName} — ${it.registryReason}" },
        ),
    )
    add(signalCheck(item.risk, "face_detection", "Face detected in live photo", "Live photo not taken or not processed"))
    val face = item.face
    add(
        when {
            face == null -> CheckItem("Face comparison", CheckState.NOT_RUN,
                "Could not compare — either no live photo was taken or no face was found in the document photo. Visually confirm the person matches the document photo.")
            face.match -> CheckItem("Face comparison", CheckState.PASS,
                "The person's face is consistent with the document photo.")
            else -> CheckItem("Face comparison", CheckState.REVIEW,
                "The live photo does not closely match the document photo. Ask the person to face the camera directly and retake if needed.")
        },
    )
    val liveness = item.livenessStatus
    add(
        when {
            liveness == null || liveness == "NOT_IMPLEMENTED" -> CheckItem("Live person check", CheckState.NOT_RUN,
                "Automated check not available. Visually confirm the person is present in front of you.")
            liveness == "LIVE" -> CheckItem("Live person check", CheckState.PASS, "The photo was taken of a live person.")
            liveness == "SUSPECTED_SPOOF" -> CheckItem("Live person check", CheckState.ALERT,
                "The photo may have been taken from a screen or printed image. Ask the person to face the camera directly and retake.")
            else -> CheckItem("Live person check", CheckState.REVIEW, "Result uncertain — retake the live photo in good lighting.")
        },
    )
    val tampering = item.tampering
    add(
        when {
            tampering == null -> CheckItem("Document authenticity", CheckState.NOT_RUN, "Authenticity check not completed.")
            tampering.tamperingRisk < 0.3 -> CheckItem("Document authenticity", CheckState.PASS, "No signs of alteration detected.")
            tampering.tamperingRisk < 0.6 -> CheckItem("Document authenticity", CheckState.REVIEW,
                "Some image inconsistencies detected — physically inspect the document for signs of alteration.")
            else -> CheckItem("Document authenticity", CheckState.ALERT,
                "Significant image inconsistencies detected — this document may have been altered. Do not allow entry without supervisor approval.")
        },
    )
    val deepfake = item.deepfakeStatus
    add(
        when {
            deepfake == null || deepfake == "NOT_IMPLEMENTED" -> CheckItem("Photo authenticity", CheckState.NOT_RUN, "Photo authenticity check not available.")
            deepfake == "ANALYZED" -> CheckItem("Photo authenticity", CheckState.PASS, "The photo appears genuine.")
            else -> CheckItem("Photo authenticity", CheckState.REVIEW, "Photo authenticity could not be confirmed — review the original document.")
        },
    )
    val graph = item.identityGraph
    add(
        when {
            graph == null -> CheckItem("Identity cross-check", CheckState.NOT_RUN,
                "Cross-check against prior records not available — no live photo was taken.")
            graph.status == "CLUSTER_FOUND" -> CheckItem("Identity cross-check", CheckState.ALERT,
                "This person's face or document matches ${graph.clusterSize} other record(s) in the system. See Identity Links below.")
            else -> CheckItem("Identity cross-check", CheckState.PASS,
                "No other records share this identity. This appears to be a first-time crossing or no biometric data was available.")
        },
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
    StepCard("Verification Checks") {
        // ── Section A: Document integrity ──────────────────────────────
        SectionLabel("Document Integrity")
        // 1. Document type match
        val detectedType = item.ocr?.detectedDocumentType?.replace("_", " ")?.lowercase()
        val selectedType = item.documentType?.replace("_", " ")?.lowercase() ?: "unknown"
        CheckItemRow(
            if (detectedType == null) CheckItem("Document type detected", CheckState.NOT_RUN, "Could not determine document type from image.")
            else if (detectedType.contains(selectedType) || selectedType.contains(detectedType))
                CheckItem("Document type detected", CheckState.PASS, "Detected as ${detectedType.replaceFirstChar { it.uppercase() }} — matches selected type.")
            else CheckItem("Document type detected", CheckState.REVIEW,
                "Selected: ${selectedType.replaceFirstChar { it.uppercase() }}. Detected: ${detectedType.replaceFirstChar { it.uppercase() }}. Please confirm the correct document type.")
        )
        // 2. Required fields present
        val ocr = item.ocr
        val schema = if (ocr != null) documentFieldSchema(item.documentType ?: "", ocr.fields) else emptyList()
        val missingCritical = schema.filter { (k, _) ->
            k in listOf("name", "passport_number", "document_number", "dl_number", "cid_number", "visa_number") &&
                ocr?.fields?.get(k).isNullOrBlank()
        }
        CheckItemRow(
            when {
                ocr == null -> CheckItem("Required fields present", CheckState.NOT_RUN, "Document was not scanned.")
                missingCritical.isEmpty() -> CheckItem("Required fields present", CheckState.PASS,
                    "${schema.count { ocr.fields[it.first]?.isNotBlank() == true }} of ${schema.size} fields read successfully.")
                else -> CheckItem("Required fields present", CheckState.REVIEW,
                    "Unable to read: ${missingCritical.joinToString(", ") { it.second }}. Retake the scan in better lighting.")
            }
        )
        // 3. MRZ / checksum validation (from validation findings)
        val mrzFindings = item.validation?.findings?.filter {
            it.check.contains("mrz", ignoreCase = true) || it.check.contains("checksum", ignoreCase = true)
        }
        if (!mrzFindings.isNullOrEmpty()) {
            mrzFindings.forEach { f ->
                CheckItemRow(CheckItem(
                    "MRZ / Checksum — ${f.check.replace("_", " ").replaceFirstChar { it.uppercase() }}",
                    if (f.status == "PASS") CheckState.PASS else if (f.severity == "HIGH") CheckState.ALERT else CheckState.REVIEW,
                    f.reason,
                ))
            }
        } else {
            val hasMrz = ocr?.mrzLines?.isNotEmpty() == true
            CheckItemRow(CheckItem("MRZ / Checksum",
                if (hasMrz) CheckState.PASS else CheckState.NOT_RUN,
                if (hasMrz) "Machine-readable zone was read successfully." else "No machine-readable zone found on this document — normal for some document types."))
        }
        // 4. Expiry / Validity
        val expiryFindings = item.validation?.findings?.filter {
            it.check.contains("expir", ignoreCase = true) || it.check.contains("valid", ignoreCase = true)
        }
        if (!expiryFindings.isNullOrEmpty()) {
            expiryFindings.forEach { f ->
                CheckItemRow(CheckItem(
                    "Validity — ${f.check.replace("_", " ").replaceFirstChar { it.uppercase() }}",
                    if (f.status == "PASS") CheckState.PASS else if (f.severity == "HIGH") CheckState.ALERT else CheckState.REVIEW,
                    f.reason,
                ))
            }
        }
        // 5. Other validation findings
        item.validation?.findings?.filter { f ->
            !f.check.contains("mrz", ignoreCase = true) &&
            !f.check.contains("checksum", ignoreCase = true) &&
            !f.check.contains("expir", ignoreCase = true) &&
            !f.check.contains("valid", ignoreCase = true)
        }?.forEach { f ->
            CheckItemRow(CheckItem(
                f.check.replace("_", " ").replaceFirstChar { it.uppercase() },
                if (f.status == "PASS") CheckState.PASS else if (f.severity == "HIGH") CheckState.ALERT else CheckState.REVIEW,
                f.reason,
            ))
        }

        Spacer(Modifier.height(12.dp))
        // ── Section B: Identity & Person checks ────────────────────────
        SectionLabel("Identity & Person")
        // 6. Face match
        CheckItemRow(when {
            item.face == null -> CheckItem("Face comparison", CheckState.NOT_RUN,
                "No prior face data available for comparison. Visually confirm the person matches the document photo.")
            item.face.match -> CheckItem("Face comparison", CheckState.PASS, "The person's face is consistent with the document photo.")
            else -> CheckItem("Face comparison", CheckState.REVIEW,
                "The live photo does not closely match the document photo. Ask the person to look directly at the camera and retake.")
        })
        // 7. Live person check
        CheckItemRow(when (item.livenessStatus) {
            null, "NOT_IMPLEMENTED" -> CheckItem("Live person present", CheckState.NOT_RUN,
                "Automated check not available. Visually confirm the person is physically present.")
            "LIVE" -> CheckItem("Live person present", CheckState.PASS, "The photo was confirmed to be of a live person.")
            "SUSPECTED_SPOOF" -> CheckItem("Live person present", CheckState.ALERT,
                "The photo may have been taken from a screen or printed image. Ask the person to retake the photo in person.")
            else -> CheckItem("Live person present", CheckState.REVIEW, "Result uncertain — retake the photo in good lighting.")
        })
        // 8. Name / DOB consistency (citizen registry)
        CheckItemRow(signalCheck(item.risk, "citizen_registry", "Name / DOB matches registry", "Not verified against registry for this document."))
        // 9. Duplicate document check
        CheckItemRow(signalCheck(item.risk, "duplicate_document", "Document used before under same name",
            "First time this document number has been screened."))
        // 10. Identity cross-check
        CheckItemRow(when {
            item.identityGraph == null -> CheckItem("Identity cross-check", CheckState.NOT_RUN,
                "No prior records to compare against.")
            item.identityGraph.status == "CLUSTER_FOUND" -> CheckItem("Identity cross-check", CheckState.ALERT,
                "This identity matches ${item.identityGraph.clusterSize} other record(s). See Identity Links in the Risk Assessment step.")
            else -> CheckItem("Identity cross-check", CheckState.PASS, "No matching records found in the system.")
        })

        Spacer(Modifier.height(12.dp))
        // ── Section C: Document authenticity ───────────────────────────
        SectionLabel("Document Authenticity")
        // 11. Watchlist
        CheckItemRow(CheckItem(
            "Watchlist check",
            if (item.registryHits.isEmpty()) CheckState.PASS else CheckState.ALERT,
            if (item.registryHits.isEmpty()) "Document number is not on the watchlist."
            else item.registryHits.joinToString("; ") { "${it.fullName} — ${it.registryReason}" },
        ))
        // 12. Tampering
        CheckItemRow(when {
            item.tampering == null -> CheckItem("Document image integrity", CheckState.NOT_RUN, "Tampering check not completed.")
            item.tampering.tamperingRisk < 0.3 -> CheckItem("Document image integrity", CheckState.PASS, "No signs of alteration detected.")
            item.tampering.tamperingRisk < 0.6 -> CheckItem("Document image integrity", CheckState.REVIEW,
                "Some image inconsistencies — physically inspect the document for signs of alteration.")
            else -> CheckItem("Document image integrity", CheckState.ALERT,
                "Significant inconsistencies — this document may have been altered. Do not allow entry without supervisor approval.")
        })
        // 13. Deepfake / photo authenticity
        CheckItemRow(when {
            item.deepfakeStatus == null || item.deepfakeStatus == "NOT_IMPLEMENTED" ->
                CheckItem("Photo authenticity", CheckState.NOT_RUN, "Automated photo authenticity check not available.")
            item.deepfakeStatus == "ANALYZED" -> CheckItem("Photo authenticity", CheckState.PASS, "The photo appears genuine.")
            else -> CheckItem("Photo authenticity", CheckState.REVIEW, "Photo authenticity could not be confirmed — review the original document.")
        })

        Spacer(Modifier.height(10.dp))
        Text(
            "\"Not run\" means the check was not performed — it is never counted as passing.",
            style = MaterialTheme.typography.labelSmall, color = Gray500,
        )
    }
}

@Composable
private fun SectionLabel(title: String) {
    Row(modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.height(1.dp).weight(1f).background(BorderDark))
        Text(
            "  $title  ",
            style = MaterialTheme.typography.labelSmall,
            fontWeight = FontWeight.SemiBold,
            color = Gray500,
        )
        Box(Modifier.height(1.dp).weight(1f).background(BorderDark))
    }
}

@Composable
fun ScreeningStep(item: ScreeningQueueItem) {
    // ScreeningStep is now merged into VerificationStep — redirect
    VerificationStep(item)
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
        "HIGH_RISK"   -> Triple(DestructiveRed, Icons.Filled.Error, "Review Required")
        "MEDIUM_RISK" -> Triple(WarningAmber, Icons.Filled.WarningAmber, "Review Recommended")
        "LOW_RISK"    -> Triple(SuccessGreen, Icons.Filled.CheckCircle, "No Issues Detected")
        else          -> Triple(Gray600, Icons.Filled.Circle, "Analysis Pending")
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
                if (risk?.decision == "MANUAL_REVIEW") "Review recommended — check findings below" else "No issues detected",
                style = MaterialTheme.typography.labelLarge,
                fontWeight = FontWeight.SemiBold,
                color = Ink900,
            )
            if (!risk?.topReason.isNullOrBlank()) {
                Spacer(Modifier.height(4.dp))
                Text(
                    humanTopReason(risk!!.topReason),
                    style = MaterialTheme.typography.bodySmall,
                    color = Gray600,
                )
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

            val graph = item.identityGraph?.let { g ->
                if (g.members.isNotEmpty() && item.selfieImagePath != null) {
                    val enriched = g.members.mapIndexed { i, m ->
                        if (i == 0) m.copy(imagePath = item.selfieImagePath) else m
                    }
                    g.copy(members = enriched)
                } else g
            }
            if (graph != null && graph.status == "CLUSTER_FOUND") {
                Spacer(Modifier.height(12.dp))
                Box(Modifier.fillMaxWidth().height(1.dp).background(BorderDark))
                Spacer(Modifier.height(12.dp))
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    modifier = Modifier.padding(bottom = 8.dp),
                ) {
                    Icon(Icons.Filled.Share, contentDescription = null, tint = WarningAmber, modifier = Modifier.size(16.dp))
                    Text(
                        "Identity Links — ${graph.clusterSize} linked record${if (graph.clusterSize != 1) "s" else ""}",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.SemiBold,
                        color = WarningAmber,
                    )
                }
                graph.members.take(6).forEach { member ->
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 4.dp)
                            .background(WarningAmber.copy(alpha = 0.06f), RoundedCornerShape(8.dp))
                            .padding(horizontal = 10.dp, vertical = 6.dp),
                        horizontalArrangement = Arrangement.spacedBy(10.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        val imgPath = member.imagePath
                        if (imgPath != null && java.io.File(imgPath).exists()) {
                            val bmp = remember(imgPath) {
                                android.graphics.BitmapFactory.decodeFile(imgPath)
                            }
                            if (bmp != null) {
                                Image(
                                    bitmap = bmp.asImageBitmap(),
                                    contentDescription = member.referenceName,
                                    modifier = Modifier.size(32.dp).clip(CircleShape),
                                    contentScale = ContentScale.Crop,
                                )
                            } else {
                                Icon(Icons.Filled.Person, contentDescription = null, tint = WarningAmber, modifier = Modifier.size(14.dp))
                            }
                        } else {
                            Icon(Icons.Filled.Person, contentDescription = null, tint = WarningAmber, modifier = Modifier.size(14.dp))
                        }
                        Column(modifier = Modifier.weight(1f)) {
                            Text(member.referenceName, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Medium)
                            if (!member.documentNumber.isNullOrBlank()) {
                                Text("Doc: ${member.documentNumber}", style = MaterialTheme.typography.labelSmall, color = Gray600)
                            }
                        }
                        val matchLabel = when (member.faceMatchStatus) {
                            com.pramaanai.officer.data.model.FaceMatchStatus.VERIFIED_MATCH -> "Face match"
                            com.pramaanai.officer.data.model.FaceMatchStatus.PARTIAL_MATCH -> "Partial match"
                            com.pramaanai.officer.data.model.FaceMatchStatus.NEW_FACE -> "New face"
                            com.pramaanai.officer.data.model.FaceMatchStatus.NO_FACE_DATA -> "No photo"
                            else -> "Linked"
                        }
                        Text(matchLabel, style = MaterialTheme.typography.labelSmall, color = WarningAmber)
                    }
                }
                if (graph.members.size > 6) {
                    Text("+${graph.members.size - 6} more", style = MaterialTheme.typography.labelSmall, color = Gray500, modifier = Modifier.padding(top = 4.dp))
                }
                if (graph.members.size >= 2) {
                    Spacer(Modifier.height(8.dp))
                    IdentityClusterGraph(members = graph.members)
                }
            }

        }
    }
}

fun signalTitle(signal: String): String = humanSignalTitle(signal)

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
    val context = androidx.compose.ui.platform.LocalContext.current
    val reasons = flaggedReasons(context, item)
    StepCard(stringResource(R.string.submit_for_review_step_title)) {
        Text(
            stringResource(R.string.submit_for_review_instructions),
            style = MaterialTheme.typography.bodySmall,
            color = Gray600,
        )
        if (reasons.isNotEmpty()) {
            Spacer(Modifier.height(12.dp))
            Text(stringResource(R.string.submit_for_review_findings_title), style = MaterialTheme.typography.labelMedium, color = Gray600)
            Spacer(Modifier.height(6.dp))
            reasons.forEach { reason ->
                Row(modifier = Modifier.padding(vertical = 4.dp)) {
                    Text("•  ", color = AccentGreen, fontWeight = FontWeight.Bold)
                    Text(reason, style = MaterialTheme.typography.bodyMedium)
                }
            }
        }
        Spacer(Modifier.height(10.dp))
        Text(
            stringResource(R.string.submit_for_review_disclaimer),
            style = MaterialTheme.typography.labelSmall,
            color = Gray500,
        )
    }
}

@Composable
fun CompleteStep(item: ScreeningQueueItem) {
    StepCard("") {
        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.fillMaxWidth().padding(vertical = 12.dp)) {
            Icon(Icons.Filled.CheckCircle, contentDescription = null, tint = AccentGreen, modifier = Modifier.size(48.dp))
            Spacer(Modifier.height(12.dp))
            Text(stringResource(R.string.case_submitted_title), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(8.dp))
            Text(
                stringResource(R.string.case_submitted_body),
                style = MaterialTheme.typography.bodySmall,
                color = Gray600,
                textAlign = TextAlign.Center,
            )
            if (!item.officerNotes.isNullOrBlank()) {
                Spacer(Modifier.height(8.dp))
                Text(stringResource(R.string.case_submitted_notes, item.officerNotes!!), style = MaterialTheme.typography.bodySmall, color = Gray500)
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