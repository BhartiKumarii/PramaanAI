package com.pramaanai.officer.data

import com.pramaanai.officer.data.model.ScreeningQueueItem
import com.pramaanai.officer.data.model.ScreeningStatus
import java.util.Calendar

/** Pure derivations over the real local queue — every number here traces
 * back to an actual submitted/decided screening, never a placeholder. There
 * is no real "average processing time" tracked by this build (no start/end
 * timestamps are recorded around backend processing), so that metric is
 * deliberately omitted rather than fabricated. */

/** [label] is the short axis label; [fullLabel] is the readable form shown
 * when a bar is tapped ("Fri, 18 Sep" / "14:00–15:00"). */
data class DailyCount(val label: String, val count: Int, val fullLabel: String = label)

data class AnalyticsSummary(
    val total: Int,
    val today: Int,
    val thisWeek: Int,
    val thisMonth: Int,
    val pending: Int,
    val cleared: Int,
    val disputed: Int,
    val lowRisk: Int,
    val mediumRisk: Int,
    val highRisk: Int,
    val documentsScanned: Int,
    val reviewRate: Double, // fraction of decided cases that were disputed
    // null when there's no prior day to compare against yet — never a
    // fabricated 0% or "steady" trend on a genuinely absent baseline.
    val todayVsYesterdayPct: Int?,
)

private fun startOfDay(): Long = Calendar.getInstance().apply {
    set(Calendar.HOUR_OF_DAY, 0); set(Calendar.MINUTE, 0); set(Calendar.SECOND, 0); set(Calendar.MILLISECOND, 0)
}.timeInMillis

private fun daysAgo(days: Int): Long = startOfDay() - days.toLong() * 24 * 60 * 60 * 1000

fun computeAnalytics(items: List<ScreeningQueueItem>): AnalyticsSummary {
    val today = startOfDay()
    val yesterday = daysAgo(1)
    val weekAgo = daysAgo(7)
    val monthAgo = daysAgo(30)
    val decided = items.count { it.status != ScreeningStatus.PENDING }
    val todayCount = items.count { it.submittedAt >= today }
    val yesterdayCount = items.count { it.submittedAt in yesterday until today }
    val hasYesterdayBaseline = items.any { it.submittedAt < today }
    val trend = when {
        !hasYesterdayBaseline -> null
        yesterdayCount == 0 -> if (todayCount == 0) 0 else 100
        else -> ((todayCount - yesterdayCount) * 100) / yesterdayCount
    }
    return AnalyticsSummary(
        total = items.size,
        today = items.count { it.submittedAt >= today },
        thisWeek = items.count { it.submittedAt >= weekAgo },
        thisMonth = items.count { it.submittedAt >= monthAgo },
        pending = items.count { it.status == ScreeningStatus.PENDING },
        cleared = items.count { it.status == ScreeningStatus.CLEARED },
        disputed = items.count { it.status == ScreeningStatus.DISPUTED },
        lowRisk = items.count { it.risk?.level == "LOW_RISK" },
        mediumRisk = items.count { it.risk?.level == "MEDIUM_RISK" },
        highRisk = items.count { it.risk?.level == "HIGH_RISK" },
        documentsScanned = items.count { it.documentImagePath != null },
        reviewRate = if (decided == 0) 0.0 else items.count { it.status == ScreeningStatus.DISPUTED }.toDouble() / decided,
        todayVsYesterdayPct = trend,
    )
}

/** Submission counts for the last [days] calendar days, oldest first. A
 * 7-day window labels bars by weekday; anything longer labels by
 * day-of-month, because 30 repeated weekday names ("Sat Sun Mon …") are
 * unreadable on a phone-width axis. */
fun dailyActivity(items: List<ScreeningQueueItem>, days: Int = 7): List<DailyCount> {
    val weekdays = listOf("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
    val months = listOf("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    return (days - 1 downTo 0).map { offset ->
        val dayStart = daysAgo(offset)
        val dayEnd = dayStart + 24 * 60 * 60 * 1000
        val cal = Calendar.getInstance().apply { timeInMillis = dayStart }
        val weekday = weekdays[cal.get(Calendar.DAY_OF_WEEK) - 1]
        val dayOfMonth = cal.get(Calendar.DAY_OF_MONTH)
        val label = if (days <= 7) weekday else dayOfMonth.toString()
        val full = "$weekday, $dayOfMonth ${months[cal.get(Calendar.MONTH)]}"
        DailyCount(label, items.count { it.submittedAt in dayStart until dayEnd }, full)
    }
}

/** Today's submissions bucketed by hour (0–23) — backs the "Today" chart. */
fun hourlyActivity(items: List<ScreeningQueueItem>): List<DailyCount> {
    val dayStart = startOfDay()
    val hourMs = 60 * 60 * 1000L
    return (0 until 24).map { hour ->
        val from = dayStart + hour * hourMs
        val label = "%02d".format(hour)
        DailyCount(label, items.count { it.submittedAt in from until from + hourMs }, "%02d:00–%02d:00".format(hour, (hour + 1) % 24))
    }
}
