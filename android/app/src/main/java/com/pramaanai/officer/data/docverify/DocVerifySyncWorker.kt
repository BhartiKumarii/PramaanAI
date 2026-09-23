package com.pramaanai.officer.data.docverify

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.pramaanai.officer.data.remote.AuthSession
import com.pramaanai.officer.data.remote.RetrofitClient
import retrofit2.HttpException
import java.util.concurrent.TimeUnit

/** Drains the encrypted offline document-verification queue once a network
 * is available. The server runs the full verification at sync time and
 * records captured_offline=true — the registry was NOT checked at capture
 * time, and the app never claimed it was. */
class DocVerifySyncWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        if (!AuthSession.isLoggedIn()) return Result.retry()
        val queue = EncryptedDocVerifyQueue.get(applicationContext)
        var retry = false
        for (item in queue.all()) {
            try {
                val outcome = RetrofitClient.docVerifyApi.verifyRegions(AuthSession.bearerHeader(),
                    item.request.copy(capturedOffline = true, openCase = true))
                outcome.id?.let { CaptureStore.get(applicationContext).link(item.request.clientRequestId, it) }
                DocVerifyRepository(applicationContext).uploadEvidence(outcome)
                queue.remove(item.id)
            } catch (e: HttpException) {
                // 4xx = the server rejected the payload itself; keeping it would retry forever.
                if (e.code() in 400..499 && e.code() != 401 && e.code() != 429) queue.remove(item.id) else retry = true
            } catch (e: Exception) {
                android.util.Log.w("DocVerifySync", "queued item ${item.id} not sent: ${e.javaClass.simpleName}: ${e.message}")
                retry = true
            }
        }
        return if (retry) Result.retry() else Result.success()
    }

    companion object {
        private const val WORK_NAME = "docverify_queue_sync"
        fun enqueue(context: Context) {
            val request = OneTimeWorkRequestBuilder<DocVerifySyncWorker>()
                .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
                .build()
            WorkManager.getInstance(context).enqueueUniqueWork(WORK_NAME, ExistingWorkPolicy.KEEP, request)
        }
    }
}
