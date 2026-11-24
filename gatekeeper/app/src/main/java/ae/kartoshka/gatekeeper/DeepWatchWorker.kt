package ae.kartoshka.gatekeeper

import android.Manifest
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.work.CoroutineWorker
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import ae.kartoshka.gatekeeper.logic.Links
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext

/**
 * After a warn the deep analysis keeps running in core. This polls `GET /v1/check/{id}` for up to three
 * minutes and notifies if the verdict turns to block (section 3).
 */
class DeepWatchWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val app = applicationContext as GatekeeperApp
        val checkId = inputData.getString(KEY_CHECK) ?: return@withContext Result.failure()
        repeat(18) {
            delay(10_000)
            val verdict = try { app.core.get(checkId) } catch (e: Exception) { return@repeat }
            if (verdict.verdict == "block") {
                notifyBlocked(verdict.url, checkId)
                return@withContext Result.success()
            }
            if (verdict.deepStatus !in setOf("queued", "running")) return@withContext Result.success()
        }
        Result.success()
    }

    private fun notifyBlocked(url: String, checkId: String) {
        val context = applicationContext
        if (Build.VERSION.SDK_INT >= 33 &&
            context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return
        val open = Intent(context, ResidentActivity::class.java)
            .putExtra(ResidentActivity.EXTRA_PATH, ResidentActivity.checkPath(url))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        val pending = PendingIntent.getActivity(context, checkId.hashCode(), open, PendingIntent.FLAG_IMMUTABLE)
        val host = Links.host(url)?.let(Links::defang) ?: ""
        val notification = NotificationCompat.Builder(context, GatekeeperApp.CHANNEL_ALERTS)
            .setSmallIcon(R.drawable.ic_shield_check)
            .setContentTitle(context.getString(R.string.notify_blocked_title))
            .setContentText(context.getString(R.string.notify_blocked_text, host))
            .setContentIntent(pending)
            .setAutoCancel(true)
            .build()
        NotificationManagerCompat.from(context).notify(checkId.hashCode(), notification)
    }

    companion object {
        private const val KEY_CHECK = "check_id"

        fun start(context: Context, checkId: String) {
            WorkManager.getInstance(context).enqueue(
                OneTimeWorkRequestBuilder<DeepWatchWorker>().setInputData(workDataOf(KEY_CHECK to checkId)).build()
            )
        }
    }
}
