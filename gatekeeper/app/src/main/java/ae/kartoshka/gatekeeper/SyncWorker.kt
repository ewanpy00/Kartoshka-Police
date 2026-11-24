package ae.kartoshka.gatekeeper

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** Pulls `GET /v1/blocklist?since=` and rebuilds the local filter. */
class SyncWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val app = applicationContext as GatekeeperApp
        try {
            val delta = app.core.blocklist(app.store.since)
            app.store.applyDelta(delta.added, delta.removed, delta.latest)
            Result.success()
        } catch (e: Exception) {
            Result.retry()
        }
    }
}
