package com.pramaanai.officer.data.sync

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.Constraints
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.pramaanai.officer.data.CHECKPOINT
import com.pramaanai.officer.data.local.AuditLogStore
import com.pramaanai.officer.data.local.LocalScreeningStore
import com.pramaanai.officer.data.local.PendingSubmissionQueue
import com.pramaanai.officer.data.model.AuditLogEntry
import com.pramaanai.officer.data.remote.AuthSession
import com.pramaanai.officer.data.remote.RetrofitClient
import com.pramaanai.officer.data.screeningResponseToQueueItem
import java.io.IOException
import java.util.UUID
import kotlinx.coroutines.flow.first
import retrofit2.HttpException

/** Drains [PendingSubmissionQueue] once connectivity returns — the other
 * half of ScreeningRepository.submitScreening's offline path. Enqueued
 * with a NetworkType.CONNECTED constraint, so WorkManager itself only
 * even starts this when the OS thinks there's a network (the actual
 * submission attempt is still the real test — see [ConnectivityMonitor]
 * for why "OS thinks there's a network" isn't trusted on its own
 * elsewhere in the app). */
class PendingSubmissionWorker(
    context: Context,
    params: WorkerParameters,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        if (!AuthSession.isLoggedIn()) return Result.retry()

        val queue = PendingSubmissionQueue.getInstance(applicationContext)
        val store = LocalScreeningStore.getInstance(applicationContext)
        val auditLog = AuditLogStore.getInstance(applicationContext)
        val api = RetrofitClient.apiService
        val checkpoint = AuthSession.checkpointName ?: CHECKPOINT

        val pending = queue.observeAll().first()
        if (pending.isEmpty()) return Result.success()

        var anyStillOffline = false
        for (submission in pending) {
            try {
                val response = api.screenDocument(AuthSession.bearerHeader(), submission.request)
                val item = screeningResponseToQueueItem(
                    response,
                    submission.travelerName,
                    submission.request.documentType,
                    submission.request.nationality,
                    checkpoint,
                    mrzText = submission.request.mrzText,
                )
                store.upsert(item)
                store.remove(submission.id) // supersede the OFFLINE_QUEUED placeholder
                queue.remove(submission.id)
                auditLog.append(
                    AuditLogEntry(
                        id = UUID.randomUUID().toString(),
                        timestamp = System.currentTimeMillis(),
                        officer = AuthSession.username ?: "unknown",
                        action = "Queued screening synced",
                        record = item.id,
                        result = "score=${item.risk?.score} level=${item.risk?.level} decision=${item.risk?.decision}",
                    ),
                )
            } catch (e: IOException) {
                // Still genuinely unreachable — leave it queued, retry later.
                anyStillOffline = true
            } catch (e: HttpException) {
                // A real server-side rejection (bad request, auth expired,
                // etc.) — retrying the same payload won't help. Remove
                // from the queue and log the real failure rather than
                // retrying forever or silently dropping it.
                queue.remove(submission.id)
                auditLog.append(
                    AuditLogEntry(
                        id = UUID.randomUUID().toString(),
                        timestamp = System.currentTimeMillis(),
                        officer = AuthSession.username ?: "unknown",
                        action = "Queued screening failed to sync",
                        record = null,
                        result = "HTTP ${e.code()}: ${e.message()}",
                    ),
                )
            }
        }
        return if (anyStillOffline) Result.retry() else Result.success()
    }

    companion object {
        private const val WORK_NAME = "pending_submission_sync"

        /** Call after any submission is queued, and once at app start, so
         * a pending item gets drained as soon as WorkManager sees a
         * connected network — never left waiting on a fixed poll
         * interval alone. */
        fun enqueue(context: Context) {
            val request = OneTimeWorkRequestBuilder<PendingSubmissionWorker>()
                .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                .build()
            WorkManager.getInstance(context).enqueueUniqueWork(
                WORK_NAME,
                androidx.work.ExistingWorkPolicy.REPLACE,
                request,
            )
        }
    }
}
