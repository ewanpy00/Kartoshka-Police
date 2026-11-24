package ae.kartoshka.gatekeeper.logic

import org.json.JSONObject

data class Reason(val code: String, val en: String, val ar: String)
data class SourceState(val id: String, val status: String)

/** Core's `/v1/check` response (the fields Gatekeeper uses). */
data class Verdict(
    val checkId: String,
    val url: String,
    val verdict: String,          // allow | warn | block | pending
    val score: Int,
    val stage: String,
    val brand: String?,
    val safeAction: SafeAction?,
    val reasons: List<Reason>,
    val sources: List<SourceState>,
    val deepStatus: String?,
    val evidenceId: String?,
) {
    companion object {
        fun fromJson(text: String): Verdict {
            val o = JSONObject(text)
            val action = o.optJSONObject("safe_action")
            val reasons = o.optJSONArray("reasons")
            val sources = o.optJSONArray("sources")
            fun str(key: String) = if (o.isNull(key)) null else o.optString(key)
            return Verdict(
                checkId = o.getString("check_id"),
                url = o.getString("url"),
                verdict = o.getString("verdict"),
                score = o.optInt("score"),
                stage = o.optString("stage", "fast"),
                brand = str("brand"),
                safeAction = action?.let { SafeAction(it.getString("label_en"), it.getString("label_ar"), it.getString("url")) },
                reasons = (0 until (reasons?.length() ?: 0)).map { i ->
                    reasons!!.getJSONObject(i).let { Reason(it.optString("code"), it.optString("en"), it.optString("ar")) }
                },
                sources = (0 until (sources?.length() ?: 0)).map { i ->
                    sources!!.getJSONObject(i).let { SourceState(it.optString("id"), it.optString("status")) }
                },
                deepStatus = str("deep_status"),
                evidenceId = str("evidence_id"),
            )
        }
    }
}
