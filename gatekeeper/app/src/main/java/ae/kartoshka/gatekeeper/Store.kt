package ae.kartoshka.gatekeeper

import android.content.Context
import ae.kartoshka.gatekeeper.logic.Bloom
import ae.kartoshka.gatekeeper.logic.Links
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/**
 * On-device state. The blocklist is the public police-confirmed list (no personal data); reports keep
 * their secret token only here. Nothing else about the user is stored.
 */
class Store(context: Context) {
    private val prefs = context.getSharedPreferences("gatekeeper", Context.MODE_PRIVATE)
    private val listFile = File(context.filesDir, "blocklist.txt")
    @Volatile private var bloom: Bloom = Bloom.of(readList())

    var since: String?
        get() = prefs.getString("since", null)
        set(value) = prefs.edit().putString("since", value).apply()

    var syncedAt: Long
        get() = prefs.getLong("synced_at", 0L)
        set(value) = prefs.edit().putLong("synced_at", value).apply()

    /** The browser links are forwarded to, as a package name chosen once by the user. */
    var browser: String?
        get() = prefs.getString("browser", null)
        set(value) = prefs.edit().putString("browser", value).apply()

    val blockedCount: Int get() = prefs.getInt("blocked_count", 0)

    /** How many police-confirmed domains the local list holds. */
    val listedCount: Int get() = prefs.getInt("listed_count", 0)

    fun countBlock() = prefs.edit().putInt("blocked_count", blockedCount + 1).apply()

    /** True when the host or one of its parents is on the confirmed list (a Bloom filter hit). */
    fun listed(host: String): Boolean = Links.parents(host).any { bloom.mightContain(it) }

    @Synchronized
    fun applyDelta(added: List<String>, removed: List<String>, latest: String?) {
        val domains = readList().toMutableSet()
        domains += added
        domains -= removed.toSet()
        listFile.writeText(domains.sorted().joinToString("\n"))
        bloom = Bloom.of(domains)
        prefs.edit().putInt("listed_count", domains.size).apply()
        if (latest != null) since = latest
        syncedAt = System.currentTimeMillis()
    }

    private fun readList(): Set<String> =
        if (listFile.exists()) listFile.readLines().filter { it.isNotBlank() }.toSet() else emptySet()

    /** Same shape as the resident screens' `kp.reports` (resident/src/store.ts), so My reports lists both. */
    fun saveReport(reportId: String, token: String, url: String) {
        val all = JSONArray(prefs.getString("reports", "[]"))
        val at = java.time.Instant.now().toString()
        all.put(JSONObject().put("id", reportId).put("token", token).put("url", url).put("at", at))
        prefs.edit().putString("reports", all.toString()).apply()
    }

    fun reportsJson(): String = prefs.getString("reports", "[]") ?: "[]"
}
