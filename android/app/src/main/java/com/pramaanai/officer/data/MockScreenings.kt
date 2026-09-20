package com.pramaanai.officer.data

import com.pramaanai.officer.data.model.LocationBox
import com.pramaanai.officer.data.model.RegistryHit
import com.pramaanai.officer.data.model.RiskResult
import com.pramaanai.officer.data.model.RiskSignalBreakdown
import com.pramaanai.officer.data.model.ScreeningQueueItem
import com.pramaanai.officer.data.model.ScreeningStatus

/** Placeholder queue data for Phase 2 — matches the shape of the real
 * backend's /documents/screen response so Phase 3 only has to replace the
 * data source, not the UI or the domain model. Reduced to 0 items so the
 * app shows only real screenings from the backend or locally-captured ones. */
object MockScreenings {

    val all: List<ScreeningQueueItem> = emptyList()
}
