package com.pramaanai.officer.ui.newscreening

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.filled.Badge
import androidx.compose.material.icons.filled.CreditCard
import androidx.compose.material.icons.filled.DirectionsCar
import androidx.compose.material.icons.filled.FlightTakeoff
import androidx.compose.material.icons.filled.Description
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.pramaanai.officer.R
import com.pramaanai.officer.data.ScreeningRepository
import com.pramaanai.officer.data.remote.CheckpointResponse
import com.pramaanai.officer.ui.components.GridPatternBackground
import com.pramaanai.officer.ui.theme.Gray600
import com.pramaanai.officer.ui.theme.Ink900

private data class DocumentTypeOption(val type: DocumentType, val icon: ImageVector)

private val DOCUMENT_TYPE_OPTIONS = listOf(
    DocumentTypeOption(DocumentType.PASSPORT, Icons.Filled.FlightTakeoff),
    DocumentTypeOption(DocumentType.VISA, Icons.Filled.Description),
    DocumentTypeOption(DocumentType.NATIONAL_ID, Icons.Filled.Badge),
    DocumentTypeOption(DocumentType.DRIVING_LICENCE, Icons.Filled.DirectionsCar),
    DocumentTypeOption(DocumentType.PERMIT, Icons.Filled.CreditCard),
)

// One document at a time: pick the type here, scan it on the next screen,
// then review the on-device OCR result — never a blank form to fill in by
// hand before a single photo has been taken. Scanning a second document
// for the same traveler (e.g. a driving licence alongside a passport) is
// just returning to this screen and picking another type.
@OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)
@Composable
fun NewScreeningScreen(
    repository: ScreeningRepository,
    selectedCheckpoint: CheckpointResponse?,
    onContinue: (ScreeningData) -> Unit,
) {
    Scaffold(topBar = { TopAppBar(title = { Text(stringResource(R.string.new_screening_title)) }) }) { padding ->
        GridPatternBackground(modifier = Modifier.padding(padding)) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(16.dp),
            ) {
            Text(
                "What document are you scanning?",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            Spacer(Modifier.height(4.dp))
            Text(
                "Pick one document at a time. You'll scan it, then review what was actually read off it — nothing is typed in by hand first.",
                style = MaterialTheme.typography.bodyMedium,
                color = Gray600,
            )
            if (selectedCheckpoint != null) {
                Spacer(Modifier.height(4.dp))
                Text(
                    text = "${stringResource(R.string.checkpoint_label)}: ${selectedCheckpoint.name} (${selectedCheckpoint.code})",
                    style = MaterialTheme.typography.labelSmall,
                    color = Ink900,
                    fontWeight = FontWeight.Medium,
                )
            }
            Spacer(Modifier.height(20.dp))

            DOCUMENT_TYPE_OPTIONS.forEach { option ->
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(bottom = 12.dp)
                        .clickable {
                            onContinue(ScreeningData(documentType = option.type, checkpointCode = selectedCheckpoint?.code))
                        },
                    colors = CardDefaults.cardColors(),
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(option.icon, contentDescription = null, modifier = Modifier.size(28.dp))
                            Spacer(Modifier.width(16.dp))
                            Text(option.type.displayName, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Medium)
                        }
                        Icon(Icons.AutoMirrored.Filled.ArrowForward, contentDescription = "Scan")
                    }
                }
            }
        }
    }
    }
}
