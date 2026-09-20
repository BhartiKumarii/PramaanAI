package com.pramaanai.officer.ui.alerts

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
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
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.pramaanai.officer.R
import com.pramaanai.officer.data.ScreeningRepository
import com.pramaanai.officer.data.local.ReadAlertsStore
import com.pramaanai.officer.data.model.AlertCategory
import com.pramaanai.officer.data.model.AlertItem
import com.pramaanai.officer.ui.components.EmptyState
import com.pramaanai.officer.ui.theme.AccentGreen
import com.pramaanai.officer.ui.theme.Gray100
import com.pramaanai.officer.ui.theme.Gray200
import com.pramaanai.officer.ui.theme.Gray500
import com.pramaanai.officer.ui.theme.Ink900
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@Composable
fun AlertsScreen(repository: ScreeningRepository, padding: PaddingValues, onOpenScreening: (String) -> Unit) {
    val alerts by repository.observeAlerts().collectAsStateWithLifecycle(initialValue = emptyList())
    val context = LocalContext.current
    val readStore = ReadAlertsStore.getInstance(context)
    val readIds by readStore.readIds.collectAsStateWithLifecycle()
    val unreadCount = alerts.count { it.id !in readIds }

    if (alerts.isEmpty()) {
        Column(modifier = Modifier.fillMaxSize().padding(padding)) {
            EmptyState(stringResource(R.string.alerts_empty_title), stringResource(R.string.alerts_empty_subtitle))
        }
        return
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(padding).padding(horizontal = 12.dp),
    ) {
        if (unreadCount > 0) {
            item(key = "mark_all_read") {
                Row(
                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                    horizontalArrangement = Arrangement.End,
                ) {
                    TextButton(onClick = { readStore.markAllRead(alerts.map { it.id }) }) {
                        Text(stringResource(R.string.alerts_mark_all_read), color = AccentGreen)
                    }
                }
            }
        }
        items(alerts, key = { it.id }) { alert ->
            val isRead = alert.id in readIds
            AlertRow(alert, isRead = isRead, onClick = {
                readStore.markRead(alert.id)
                onOpenScreening(alert.screeningId)
            })
            Spacer(Modifier.height(8.dp))
        }
    }
}

@Composable
private fun categoryLabel(category: AlertCategory): String = when (category) {
    AlertCategory.DOCUMENT_REVIEW_REQUIRED -> stringResource(R.string.alert_document_review)
    AlertCategory.RISK_ASSESSMENT_REVIEW -> stringResource(R.string.alert_risk_review)
    AlertCategory.DUPLICATE_RECORD -> stringResource(R.string.alert_duplicate)
    AlertCategory.INCOMPLETE_INFORMATION -> stringResource(R.string.alert_incomplete)
    AlertCategory.VERIFICATION_REQUIRED -> stringResource(R.string.alert_verification)
}

@Composable
private fun AlertRow(alert: AlertItem, isRead: Boolean, onClick: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
        border = BorderStroke(1.dp, if (isRead) Gray200 else AccentGreen.copy(alpha = 0.4f)),
        shape = RoundedCornerShape(10.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (isRead) MaterialTheme.colorScheme.surface else AccentGreen.copy(alpha = 0.05f),
        ),
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    if (!isRead) {
                        Box(
                            modifier = Modifier
                                .size(8.dp)
                                .background(AccentGreen, CircleShape),
                        )
                        Spacer(Modifier.width(8.dp))
                    }
                    Text(
                        categoryLabel(alert.category).uppercase(),
                        style = MaterialTheme.typography.labelSmall,
                        color = Ink900,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier
                            .background(Gray100, RoundedCornerShape(6.dp))
                            .padding(horizontal = 8.dp, vertical = 3.dp),
                    )
                }
                Text(timeAgo(alert.createdAt, LocalContext.current.resources), style = MaterialTheme.typography.labelSmall, color = Gray500)
            }
            Spacer(Modifier.height(6.dp))
            Text(alert.travelerName, fontWeight = if (isRead) FontWeight.Normal else FontWeight.SemiBold)
            Text(alert.description, style = MaterialTheme.typography.bodySmall, color = Gray500)
        }
    }
}

private fun timeAgo(timestamp: Long, res: android.content.res.Resources): String {
    val diffMs = System.currentTimeMillis() - timestamp
    val minutes = diffMs / (60 * 1000)
    return when {
        minutes < 1 -> res.getString(R.string.time_just_now)
        minutes < 60 -> res.getString(R.string.time_minutes_ago, minutes.toInt())
        minutes < 60 * 24 -> res.getString(R.string.time_hours_ago, (minutes / 60).toInt())
        else -> SimpleDateFormat("dd MMM", Locale.getDefault()).format(Date(timestamp))
    }
}
