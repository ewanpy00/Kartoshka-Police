package ae.kartoshka.gatekeeper.logic

/** What core said, or why it said nothing. */
sealed interface Remote {
    data class Answer(val verdict: Verdict) : Remote
    data object Timeout : Remote      // no answer inside the 400 ms budget
    data object Offline : Remote      // connection failed
}

/** What the phone does with the tapped link. */
sealed interface Action {
    data object Forward : Action                                          // open in the real browser
    data class Warn(val page: Page) : Action                              // interstitial
    data class Block(val page: Page) : Action                             // block page
    data object Checking : Action                                         // "Checking link…" up to 3 s
}

/** Everything the warn or block page shows. Reasons come from core when it answered, else from the phone. */
data class Page(
    val url: String,
    val brandId: String?,
    val reasons: List<Reason>,
    val safeAction: SafeAction?,
    val checkId: String?,
    val fromCore: Boolean,
    val deepRunning: Boolean,
)

/**
 * The decision table of ARCHITECTURE.md section 3. [listed] is a hit in the local blocklist filter.
 * Thresholds are core's bands: under 30 allow, 30 to 70 warn, over 70 block.
 */
object Decision {
    const val WARN_AT = 30
    const val BLOCK_ABOVE = 70

    fun decide(url: String, local: LocalScore, listed: Boolean, remote: Remote, catalog: Catalog, text: String = ""): Action {
        if (local.official) return Action.Forward
        if (remote is Remote.Answer && remote.verdict.verdict != "pending") {
            val v = remote.verdict
            val page = Page(url, v.brand ?: local.brandId, v.reasons, v.safeAction ?: catalog.safeAction(v.brand ?: local.brandId, url, text),
                v.checkId, fromCore = true, deepRunning = v.deepStatus in setOf("queued", "running"))
            return when (v.verdict) {
                "block" -> Action.Block(page)
                "warn" -> Action.Warn(page)
                else -> Action.Forward
            }
        }
        val checkId = (remote as? Remote.Answer)?.verdict?.checkId
        val page = localPage(url, local, listed, catalog, text, checkId)
        if (listed) return Action.Block(page)
        if (local.score < WARN_AT) return Action.Forward
        if (remote is Remote.Offline) return if (local.score > BLOCK_ABOVE) Action.Block(page) else Action.Warn(page)
        return Action.Checking
    }

    /** After "Checking link…" ran out (3 s): warn with what is known. */
    fun afterWait(url: String, local: LocalScore, listed: Boolean, catalog: Catalog, text: String = "", checkId: String? = null): Action {
        val page = localPage(url, local, listed, catalog, text, checkId)
        return if (listed || local.score > BLOCK_ABOVE) Action.Block(page) else Action.Warn(page)
    }

    private fun localPage(url: String, local: LocalScore, listed: Boolean, catalog: Catalog, text: String, checkId: String?): Page {
        val reasons = buildList {
            if (listed) add(Reason("POLICE_CONFIRMED", "Police confirmed this site as a scam", "أكدت الشرطة أن هذا الموقع احتيالي"))
            local.reasons.forEach { add(Reason(it.code, it.en, it.ar)) }
        }
        return Page(url, local.brandId, reasons, catalog.safeAction(local.brandId, url, text), checkId, fromCore = false,
            deepRunning = checkId != null)
    }
}
