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

    /** "system", "en" or "ar" (see Appearance). */
    var language: String
        get() = prefs.getString("language", "system") ?: "system"
        set(value) = prefs.edit().putString("language", value).apply()

    /** "system", "light" or "dark" (see Appearance). */
    var theme: String
        get() = prefs.getString("theme", "system") ?: "system"
        set(value) = prefs.edit().putString("theme", value).apply()

    val blockedCount: Int get() = prefs.getInt("blocked_count", 0)

    /** How many police-confirmed domains the local list holds. */
    val listedCount: Int get() = prefs.getInt("listed_count", 0)

    fun countBlock() = prefs.edit().putInt("blocked_count", blockedCount + 1).apply()

    /** Demo build only: sample counters so Home is not all zeros on a fresh install. */
    fun seedDemo() {
        if (!prefs.contains("demo_seeded")) {
            prefs.edit().putBoolean("demo_seeded", true).putInt("blocked_count", 17)
                .putInt("listed_count", maxOf(listedCount, 1284)).putLong("synced_at", System.currentTimeMillis() - 4 * 60_000).apply()
        }
        if (!prefs.contains("demo_checks_seeded")) {
            prefs.edit().putBoolean("demo_checks_seeded", true).apply()
            addCheck("https://www.tamm.abudhabi/", "allow", null)
            addCheck("https://secure-update.online/", "warn", null)
            addCheck("https://rta-fine-ae.xyz/payment", "block", "RTA")
        }
    }

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

    /**
     * Recent checks for Home: links the user checked on purpose, plus links that Gatekeeper warned about or
     * blocked. Plain safe link taps are not kept, so this never becomes a browsing history. Newest first, 8 at most.
     */
    data class RecentCheck(val url: String, val verdict: String, val brand: String?, val at: Long)

    fun recentChecks(): List<RecentCheck> = runCatching {
        val all = JSONArray(prefs.getString("recent_checks", "[]"))
        (0 until all.length()).map { i ->
            val o = all.getJSONObject(i)
            RecentCheck(o.getString("url"), o.getString("verdict"), o.optString("brand").ifBlank { null }, o.getLong("at"))
        }
    }.getOrDefault(emptyList())

    @Synchronized
    fun addCheck(url: String, verdict: String, brand: String?) {
        if (verdict !in VERDICTS || url.isBlank() || url.length > 2048) return
        val kept = recentChecks().filter { it.url != url }.take(RECENT_MAX - 1)
        val all = JSONArray()
        all.put(JSONObject().put("url", url).put("verdict", verdict).put("brand", brand?.take(60) ?: "").put("at", System.currentTimeMillis()))
        kept.forEach { all.put(JSONObject().put("url", it.url).put("verdict", it.verdict).put("brand", it.brand ?: "").put("at", it.at)) }
        prefs.edit().putString("recent_checks", all.toString()).apply()
    }

    fun clearChecks() = prefs.edit().remove("recent_checks").apply()

    companion object {
        val VERDICTS = setOf("allow", "warn", "block")
        const val RECENT_MAX = 8
    }
}
