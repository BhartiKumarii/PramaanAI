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
import com.pramaanai.officer.ui.theme.AccentGreen
import com.pramaanai.officer.ui.theme.Gray500
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
                    .padding(horizontal = 16.dp, vertical = 8.dp),
            ) {
                Text(
                    stringResource(R.string.new_screening_select_prompt),
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    stringResource(R.string.new_screening_select_desc),
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
                                onContinue(
                                    ScreeningData(
                                        documentType = option.type,
                                        checkpointCode = selectedCheckpoint?.code,
                                    )
                                )
                            },
                        colors = CardDefaults.cardColors(),
                    ) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(horizontal = 16.dp, vertical = 14.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween,
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.weight(1f)) {
                                Icon(
                                    option.icon,
                                    contentDescription = null,
                                    modifier = Modifier.size(28.dp),
                                    tint = AccentGreen,
                                )
                                Spacer(Modifier.width(14.dp))
                                Column {
                                    Text(
                                        stringResource(option.type.labelRes),
                                        style = MaterialTheme.typography.titleSmall,
                                        fontWeight = FontWeight.SemiBold,
                                        color = Ink900,
                                    )
                                    Text(
                                        stringResource(option.type.subtitleRes),
                                        style = MaterialTheme.typography.labelSmall,
                                        color = Gray500,
                                    )
                                }
                            }
                            Icon(
                                Icons.AutoMirrored.Filled.ArrowForward,
                                contentDescription = stringResource(R.string.title_capture),
                                tint = AccentGreen,
                            )
                        }
                    }
                }
            }
        }
    }
}
