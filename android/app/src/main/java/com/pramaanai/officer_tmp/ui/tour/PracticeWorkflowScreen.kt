package com.bordershield.officer.ui.tour

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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.bordershield.officer.data.PracticeScreeningData
import com.bordershield.officer.data.model.ScreeningStatus
import com.bordershield.officer.ui.components.MatchTypeTag
import com.bordershield.officer.ui.components.WorkflowStepper
import com.bordershield.officer.ui.theme.Gray600
import com.bordershield.officer.ui.theme.Ink900
import com.bordershield.officer.ui.theme.White
import com.bordershield.officer.ui.workflow.CheckRow
import com.bordershield.officer.ui.workflow.CompleteStep
import com.bordershield.officer.ui.workflow.ExtractionStep
import com.bordershield.officer.ui.workflow.RiskAssessmentStep
import com.bordershield.officer.ui.workflow.ReviewStep
import com.bordershield.officer.ui.workflow.ScreeningStep
import com.bordershield.officer.ui.workflow.StepCard
import com.bordershield.officer.ui.workflow.VerificationStep

/** The hands-on half of the first-login guided tour: the exact same 7-step
 * workflow UI as a real screening, driven by static sample data. No network
 * call and no local-store write happens anywhere in this screen — Clear and
 * Flag are no-ops that only change what's shown on screen. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PracticeWorkflowScreen(onFinished: () -> Unit) {
    var step by remember { mutableStateOf(1) }
    var notes by remember { mutableStateOf("") }
    var practiceDecision by remember { mutableStateOf<ScreeningStatus?>(null) }
    val item = PracticeScreeningData.sample

    Scaffold(topBar = { TopAppBar(title = { Text("Practice Screening") }) }) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding)) {
            PracticeBanner()
            Column(Modifier.padding(16.dp)) { WorkflowStepper(currentStep = step) }
            LazyColumn(modifier = Modifier.weight(1f).fillMaxWidth().padding(horizontal = 16.dp)) {
                item {
                    when (step) {
                        1 -> DocumentStepPlaceholder()
                        2 -> ExtractionStep(item)
                        3 -> VerificationConceptStep(item)
                        4 -> ScreeningConceptStep(item)
                        5 -> RiskAssessmentStep(item)
                        6 -> ReviewStep(notes, onNotesChange = { notes = it })
                        7 -> CompleteStep(item.copy(status = practiceDecision ?: ScreeningStatus.PENDING))
                    }
                    Spacer(Modifier.height(24.dp))
                }
            }
            Row(modifier = Modifier.fillMaxWidth().padding(16.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                if (step in 2..6) {
                    OutlinedButton(onClick = { step-- }, modifier = Modifier.weight(1f)) { Text("Back") }
                }
                when (step) {
                    in 1..5 -> Button(
                        onClick = { step++ },
                        colors = ButtonDefaults.buttonColors(containerColor = Ink900, contentColor = White),
                        modifier = Modifier.weight(1f),
                    ) { Text("Next") }
                    6 -> {
                        OutlinedButton(
                            onClick = { practiceDecision = ScreeningStatus.DISPUTED; step = 7 },
                            modifier = Modifier.weight(1f),
                        ) { Text("Flag / Further review") }
                        Button(
                            onClick = { practiceDecision = ScreeningStatus.CLEARED; step = 7 },
                            colors = ButtonDefaults.buttonColors(containerColor = Ink900, contentColor = White),
                            modifier = Modifier.weight(1f),
                        ) { Text("Clear") }
                    }
                    7 -> Button(
                        onClick = onFinished,
                        colors = ButtonDefaults.buttonColors(containerColor = Ink900, contentColor = White),
                        modifier = Modifier.weight(1f),
                    ) { Text("Finish practice") }
                }
            }
        }
    }
}

@Composable
private fun PracticeBanner() {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(Ink900)
            .padding(horizontal = 16.dp, vertical = 8.dp),
    ) {
        Text(
            "PRACTICE MODE — sample data, nothing is saved",
            color = White,
            style = MaterialTheme.typography.labelSmall,
            fontWeight = FontWeight.Bold,
        )
    }
}

@Composable
private fun DocumentStepPlaceholder() {
    StepCard("Document Scanning") {
        Text(
            "In a real screening this step captures or uploads the document photo. Practice mode " +
                "skips straight to a sample document's already-extracted data.",
            style = MaterialTheme.typography.bodySmall,
            color = Gray600,
        )
    }
}

/** Same real Verification content as a live screening, plus two explicit,
 * anchored example rows so the guided tour can spotlight the Detected vs
 * Verified distinction concretely. */
@Composable
private fun VerificationConceptStep(item: com.bordershield.officer.data.model.ScreeningQueueItem) {
    StepCard("Document Verification") {
        Text("Two different things are being checked here — don't read them as the same signal:", style = MaterialTheme.typography.bodySmall, color = Gray600)
        Spacer(Modifier.height(8.dp))
        CheckRow(
            "Document readable (Detected)",
            true,
            "Detected",
            modifier = Modifier.tourAnchor("detected_example"),
        )
        Text(
            "\"Detected\" — OCR found this field on the image. It says nothing about whether the field is correct.",
            style = MaterialTheme.typography.labelSmall,
            color = Gray600,
            modifier = Modifier.padding(bottom = 8.dp),
        )
        CheckRow(
            "MRZ checksum composite (Verified)",
            true,
            "Verified",
            modifier = Modifier.tourAnchor("verified_example"),
        )
        Text(
            "\"Verified\" — the backend's validation engine actually ran a check (a checksum, a rule) and confirmed it.",
            style = MaterialTheme.typography.labelSmall,
            color = Gray600,
        )
    }
    Spacer(Modifier.height(16.dp))
    VerificationStep(item)
}

/** Same real Screening content, plus the sample's real EXACT and FUZZY
 * registry hits shown side by side so the tour can spotlight the
 * distinction with a concrete example instead of a generic tooltip. */
@Composable
private fun ScreeningConceptStep(item: com.bordershield.officer.data.model.ScreeningQueueItem) {
    StepCard("Registry match types") {
        Text(
            "Never treat these the same way — an EXACT hit is a confirmed document-number match; a " +
                "FUZZY hit is only a name similarity and needs officer judgment.",
            style = MaterialTheme.typography.bodySmall,
            color = Gray600,
        )
        Spacer(Modifier.height(10.dp))
        item.registryHits.forEach { hit ->
            Row(modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
                Column(Modifier.weight(1f)) {
                    Text(hit.fullName, fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodySmall)
                    Text(hit.registryReason, style = MaterialTheme.typography.labelSmall, color = Gray600)
                }
                MatchTypeTag(
                    hit.matchType,
                    modifier = Modifier.tourAnchor(if (hit.matchType == "EXACT") "exact_tag_example" else "fuzzy_tag_example"),
                )
            }
        }
    }
    Spacer(Modifier.height(16.dp))
    ScreeningStep(item)
}
