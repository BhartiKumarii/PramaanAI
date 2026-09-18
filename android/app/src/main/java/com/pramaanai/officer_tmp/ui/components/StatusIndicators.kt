package com.bordershield.officer.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Circle
import androidx.compose.material.icons.filled.Error
import androidx.compose.material.icons.filled.WarningAmber
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.foundation.layout.Spacer
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.bordershield.officer.R
import com.bordershield.officer.ui.theme.Gray100
import com.bordershield.officer.ui.theme.Gray200
import com.bordershield.officer.ui.theme.Gray500
import com.bordershield.officer.ui.theme.Gray600
import com.bordershield.officer.ui.theme.Ink900
import com.bordershield.officer.ui.theme.White

private data class BadgeStyle(val icon: ImageVector, val label: String, val bg: Color, val fg: Color)

/** Risk level is always icon + label, never color alone — a strict
 * grayscale palette can't rely on hue to distinguish severity. */
@Composable
fun RiskBadge(level: String, modifier: Modifier = Modifier) {
    val style = when (level) {
        "HIGH_RISK" -> BadgeStyle(Icons.Filled.Error, stringResource(R.string.risk_high), Ink900, White)
        "MEDIUM_RISK" -> BadgeStyle(Icons.Filled.WarningAmber, stringResource(R.string.risk_medium), Gray200, Ink900)
        "LOW_RISK" -> BadgeStyle(Icons.Filled.CheckCircle, stringResource(R.string.risk_low), Gray100, Gray600)
        else -> BadgeStyle(Icons.Filled.Circle, stringResource(R.string.risk_pending), Gray100, Gray600)
    }
    Row(
        modifier = modifier
            .background(style.bg, RoundedCornerShape(6.dp))
            .padding(horizontal = 10.dp, vertical = 5.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(style.icon, contentDescription = null, tint = style.fg, modifier = Modifier.size(14.dp))
        Spacer(Modifier.width(6.dp))
        Text(style.label, color = style.fg, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold)
    }
}

/** EXACT vs FUZZY must never collapse into one flag — rendered as a filled
 * vs. outlined chip (shape, not color) so it still reads correctly in
 * grayscale. */
@Composable
fun MatchTypeTag(matchType: String, modifier: Modifier = Modifier) {
    val isExact = matchType == "EXACT"
    Box(
        modifier = modifier
            .then(
                if (isExact) Modifier.background(Ink900, RoundedCornerShape(6.dp))
                else Modifier.border(1.dp, Ink900, RoundedCornerShape(6.dp)),
            )
            .padding(horizontal = 10.dp, vertical = 4.dp),
    ) {
        Text(
            stringResource(if (isExact) R.string.match_exact else R.string.match_fuzzy),
            color = if (isExact) White else Ink900,
            style = MaterialTheme.typography.labelSmall,
            fontWeight = FontWeight.Bold,
        )
    }
}

@Composable
fun SystemStatusIndicator(label: String = stringResource(R.string.system_operational), modifier: Modifier = Modifier) {
    Row(modifier = modifier, verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(8.dp).background(Ink900, CircleShape))
        Spacer(Modifier.width(6.dp))
        Text(label, style = MaterialTheme.typography.labelMedium, color = Gray600)
    }
}

/** A single overall OCR confidence applies per extracted field — the
 * backend doesn't return per-field confidence, so this doesn't fabricate
 * one. */
@Composable
fun ConfidenceTag(confidence: Double, modifier: Modifier = Modifier) {
    val label = when {
        confidence >= 0.85 -> "High confidence"
        confidence >= 0.6 -> "Medium confidence"
        else -> "Low confidence"
    }
    Text(
        "$label · ${(confidence * 100).toInt()}%",
        style = MaterialTheme.typography.labelSmall,
        color = Gray600,
        modifier = modifier,
    )
}

@Composable
fun EmptyState(title: String, message: String, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier.fillMaxWidth().padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.height(4.dp))
        Text(message, style = MaterialTheme.typography.bodySmall, color = Gray600, textAlign = TextAlign.Center)
    }
}

/** The 7-step progress header (01..07) required across the new-screening
 * workflow. */
@Composable
fun WorkflowStepper(currentStep: Int, modifier: Modifier = Modifier) {
    val stepLabels = listOf(
        stringResource(R.string.step_document),
        stringResource(R.string.step_extraction),
        stringResource(R.string.step_verification),
        stringResource(R.string.step_screening),
        stringResource(R.string.step_risk_assessment),
        stringResource(R.string.step_review),
        stringResource(R.string.step_complete),
    )
    Row(
        modifier = modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
        verticalAlignment = Alignment.Top,
    ) {
        stepLabels.forEachIndexed { index, label ->
            val stepNumber = index + 1
            val done = stepNumber < currentStep
            val active = stepNumber == currentStep
            Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.width(64.dp)) {
                Box(
                    modifier = Modifier.size(26.dp).background(if (done || active) Ink900 else Gray200, CircleShape),
                    contentAlignment = Alignment.Center,
                ) {
                    if (done) {
                        Icon(Icons.Filled.Check, contentDescription = null, tint = White, modifier = Modifier.size(14.dp))
                    } else {
                        Text(
                            "%02d".format(stepNumber),
                            color = if (active) White else Gray600,
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.Bold,
                        )
                    }
                }
                Spacer(Modifier.height(4.dp))
                Text(
                    label,
                    style = MaterialTheme.typography.labelSmall,
                    color = if (active) Ink900 else Gray500,
                    textAlign = TextAlign.Center,
                )
            }
        }
    }
}
