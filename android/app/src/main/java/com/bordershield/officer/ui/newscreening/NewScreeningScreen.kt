package com.bordershield.officer.ui.newscreening

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

private val DOCUMENT_TYPES = listOf("passport", "national_id", "visa")

/** Collects the fields the real backend's POST /documents/screen requires
 * (document_type, nationality) plus a display name for the queue, before
 * handing off to the camera flow. Phase 2 had no such step since every
 * screening was pre-baked mock data. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NewScreeningScreen(onContinue: (travelerName: String, documentType: String, nationality: String) -> Unit) {
    var travelerName by remember { mutableStateOf("") }
    var nationality by remember { mutableStateOf("") }
    var documentType by remember { mutableStateOf(DOCUMENT_TYPES.first()) }

    Scaffold(topBar = { TopAppBar(title = { Text("New Screening") }) }) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp)) {
            OutlinedTextField(
                value = travelerName,
                onValueChange = { travelerName = it },
                label = { Text("Traveler name") },
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(16.dp))
            OutlinedTextField(
                value = nationality,
                onValueChange = { nationality = it.uppercase() },
                label = { Text("Nationality") },
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(16.dp))
            Text("Document type", style = MaterialTheme.typography.labelLarge)
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                DOCUMENT_TYPES.forEach { type ->
                    FilterChip(
                        selected = documentType == type,
                        onClick = { documentType = type },
                        label = { Text(type.replace("_", " ")) },
                    )
                }
            }
            Spacer(Modifier.height(24.dp))
            Button(
                onClick = { onContinue(travelerName.trim(), documentType, nationality.trim()) },
                enabled = travelerName.isNotBlank() && nationality.isNotBlank(),
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Continue to capture") }
        }
    }
}
