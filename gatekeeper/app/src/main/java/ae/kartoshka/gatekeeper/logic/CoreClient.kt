package ae.kartoshka.gatekeeper.logic

import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.SocketTimeoutException
import java.net.URL
import java.net.URLEncoder

data class BlocklistDelta(val added: List<String>, val removed: List<String>, val latest: String?)
data class Report(val reportId: String, val token: String, val checkId: String)

/**
 * Plain HttpURLConnection client for core (no account, no device id sent with checks). Blocking calls:
 * the app runs them on Dispatchers.IO.
 */
class CoreClient(private val base: String) {
    /** `POST /v1/check` in fast mode inside [budgetMs] (section 3: 400 ms). */
    fun check(url: String, source: String, text: String = "", budgetMs: Int = 400): Remote = try {
        val body = JSONObject().put("url", url).put("source", source).put("mode", "fast").put("text", text.take(4000))
        Remote.Answer(Verdict.fromJson(request("POST", "/v1/check", body.toString(), budgetMs)))
    } catch (e: SocketTimeoutException) {
        Remote.Timeout
    } catch (e: IOException) {
        Remote.Offline
    }

    fun get(checkId: String, timeoutMs: Int = 5000): Verdict =
        Verdict.fromJson(request("GET", "/v1/check/${enc(checkId)}", null, timeoutMs))

    fun blocklist(since: String?): BlocklistDelta {
        val query = if (since != null) "?since=${enc(since)}" else ""
        val o = JSONObject(request("GET", "/v1/blocklist$query", null, 15_000))
        fun rows(key: String) = o.optJSONArray(key)?.let { a -> (0 until a.length()).map { a.getJSONObject(it) } } ?: emptyList()
        val added = rows("domains")
        val removed = rows("removed")
        val latest = (added + removed).map { it.getString("updated_at") }.maxOrNull()
        return BlocklistDelta(added.map { it.getString("domain") }, removed.map { it.getString("domain") }, latest)
    }

    fun report(url: String, note: String = ""): Report {
        val o = JSONObject(request("POST", "/v1/report", JSONObject().put("url", url).put("note", note.take(2000)).toString(), 10_000))
        return Report(o.optString("report_id"), o.optString("token"), o.getString("check_id"))
    }

    private fun request(method: String, path: String, body: String?, timeoutMs: Int): String {
        val connection = URL(base.trimEnd('/') + path).openConnection() as HttpURLConnection
        try {
            connection.requestMethod = method
            connection.connectTimeout = timeoutMs
            connection.readTimeout = timeoutMs
            connection.setRequestProperty("Accept", "application/json")
            if (body != null) {
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json")
                connection.outputStream.use { it.write(body.toByteArray()) }
            }
            val code = connection.responseCode
            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            val text = stream?.bufferedReader()?.use { it.readText() } ?: ""
            if (code !in 200..299) throw IOException("core answered $code: ${text.take(200)}")
            return text
        } finally {
            connection.disconnect()
        }
    }

    private fun enc(value: String) = URLEncoder.encode(value, "UTF-8")
}
