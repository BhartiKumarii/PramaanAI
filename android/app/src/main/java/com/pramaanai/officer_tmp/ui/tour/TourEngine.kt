package com.bordershield.officer.ui.tour

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.ui.layout.boundsInRoot
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.bordershield.officer.ui.theme.Ink900
import com.bordershield.officer.ui.theme.White

/** Where a real, currently-composed UI element is on screen, keyed by the id
 * given to [Modifier.tourAnchor]. Backs the spotlight — the overlay always
 * highlights the actual live element, never a mocked-up illustration. */
object TourAnchors {
    val positions = mutableStateMapOf<String, Rect>()
}

fun Modifier.tourAnchor(id: String): Modifier = this.onGloballyPositioned { coordinates ->
    TourAnchors.positions[id] = coordinates.boundsInRoot()
}

data class TourStep(
    val id: String,
    val anchorId: String? = null,
    val title: String,
    val body: String,
    val ctaLabel: String? = null,
    val onCta: (() -> Unit)? = null,
)

/** Session-scoped tour state, same pattern as AuthSession — a single guided
 * tour runs at a time, driven from whichever screen is currently visible. */
object TourState {
    var active by mutableStateOf(false)
    var stepIndex by mutableStateOf(0)
    var steps: List<TourStep> = emptyList()
    var onFinished: (() -> Unit)? = null

    val currentStep: TourStep?
        get() = steps.getOrNull(stepIndex)

    fun start(steps: List<TourStep>, onFinished: (() -> Unit)? = null) {
        this.steps = steps
        this.stepIndex = 0
        this.onFinished = onFinished
        active = true
    }

    fun next() {
        if (stepIndex < steps.lastIndex) stepIndex++ else finish()
    }

    fun back() {
        if (stepIndex > 0) stepIndex--
    }

    fun skip() = finish()

    fun finish() {
        active = false
        onFinished?.invoke()
        onFinished = null
    }
}

/** Draws the darkened scrim with a bright cutout around the current step's
 * live anchor (plain geometry — four scrim rectangles around the anchor
 * bounds — rather than a blend-mode punch-hole, so it renders reliably
 * without an offscreen compositing layer), plus a fixed bottom tooltip card
 * with Back/Next/Skip controls. Renders nothing when no tour is active, or
 * when the current step's anchor hasn't mounted on the visible screen yet. */
@Composable
fun TourOverlay() {
    // Reading `active` first (and returning based on it) is what actually
    // gives this composable a snapshot-state dependency that changes value
    // when a tour starts — stepIndex alone can stay at 0 across a restart
    // and would never trigger a recomposition on its own.
    if (!TourState.active) return
    val step = TourState.currentStep ?: return
    val anchorRect = step.anchorId?.let { TourAnchors.positions[it] }
    if (step.anchorId != null && anchorRect == null) return

    androidx.compose.foundation.layout.BoxWithConstraints(Modifier.fillMaxSize()) {
        val screenHeightPx = with(androidx.compose.ui.platform.LocalDensity.current) { maxHeight.toPx() }
        Canvas(Modifier.fillMaxSize()) {
            val scrim = Color.Black.copy(alpha = 0.6f)
            if (anchorRect == null) {
                drawRect(scrim)
            } else {
                val pad = 12f
                val l = (anchorRect.left - pad).coerceAtLeast(0f)
                val t = (anchorRect.top - pad).coerceAtLeast(0f)
                val r = (anchorRect.right + pad).coerceAtMost(size.width)
                val b = (anchorRect.bottom + pad).coerceAtMost(size.height)
                drawRect(scrim, topLeft = Offset(0f, 0f), size = Size(size.width, t))
                drawRect(scrim, topLeft = Offset(0f, b), size = Size(size.width, size.height - b))
                drawRect(scrim, topLeft = Offset(0f, t), size = Size(l, b - t))
                drawRect(scrim, topLeft = Offset(r, t), size = Size(size.width - r, b - t))
                drawRoundRect(
                    color = White,
                    topLeft = Offset(l, t),
                    size = Size(r - l, b - t),
                    cornerRadius = CornerRadius(12f, 12f),
                    style = Stroke(width = 4f),
                )
            }
        }

        // An anchor in the bottom half of the screen (the bottom nav, for
        // instance) would otherwise sit directly under a bottom-fixed
        // tooltip, hiding the very thing being spotlighted — so the tooltip
        // flips to the top in that case instead.
        val tooltipAtTop = anchorRect != null && anchorRect.center.y > screenHeightPx / 2f
        Card(
            modifier = Modifier
                .align(if (tooltipAtTop) Alignment.TopCenter else Alignment.BottomCenter)
                .fillMaxWidth()
                .padding(16.dp),
            colors = CardDefaults.cardColors(containerColor = White),
            shape = RoundedCornerShape(14.dp),
        ) {
            Column(Modifier.padding(18.dp)) {
                Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    TourState.steps.forEachIndexed { index, _ ->
                        Box(
                            Modifier
                                .size(6.dp)
                                .background(
                                    if (index == TourState.stepIndex) Ink900 else Ink900.copy(alpha = 0.2f),
                                    CircleShape,
                                ),
                        )
                    }
                }
                Spacer(Modifier.height(10.dp))
                Text(step.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(6.dp))
                Text(step.body, style = MaterialTheme.typography.bodyMedium)
                Spacer(Modifier.height(16.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    TextButton(onClick = { TourState.skip() }) { Text("Skip tour") }
                    Spacer(Modifier.weight(1f))
                    if (TourState.stepIndex > 0 && step.onCta == null) {
                        TextButton(onClick = { TourState.back() }) { Text("Back") }
                    }
                    if (step.onCta != null) {
                        Button(
                            onClick = step.onCta,
                            colors = ButtonDefaults.buttonColors(containerColor = Ink900, contentColor = White),
                        ) { Text(step.ctaLabel ?: "Continue") }
                    } else {
                        Button(
                            onClick = { TourState.next() },
                            colors = ButtonDefaults.buttonColors(containerColor = Ink900, contentColor = White),
                        ) { Text(if (TourState.stepIndex == TourState.steps.lastIndex) "Finish" else "Next") }
                    }
                }
            }
        }
    }
}
