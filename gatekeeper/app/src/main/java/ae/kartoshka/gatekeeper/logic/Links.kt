package ae.kartoshka.gatekeeper.logic

import java.net.IDN
import java.net.URI

/** URL helpers shared by the link handler, the share target and the offline scorer. */
object Links {
    private val IN_TEXT = Regex(
        """(?i)\b((?:https?://)[^\s<>"'«»]+|(?:www\.)?[a-z0-9؀-ۿ-]+(?:\.[a-z0-9؀-ۿ-]+)*\.[a-z]{2,24}(?:/[^\s<>"'«»]*)?)"""
    )
    private val TRAILING = setOf('.', ',', ';', ':', '!', '?', ')', ']', '}', '،', '؛')
    private val SECOND_LEVELS = setOf("co", "com", "net", "org", "gov", "ac", "edu")

    /** Every link in a pasted SMS, with `https://` added to bare names; at most [limit]. */
    fun extract(text: String, limit: Int = 5): List<String> {
        val found = LinkedHashSet<String>()
        for (match in IN_TEXT.findAll(text)) {
            var raw = match.value
            while (raw.isNotEmpty() && raw.last() in TRAILING) raw = raw.dropLast(1)
            val url = if (raw.startsWith("http://", true) || raw.startsWith("https://", true)) raw else "https://$raw"
            if (host(url) != null) found += url
            if (found.size >= limit) break
        }
        return found.toList()
    }

    /** Lower-case ASCII (punycode) host of an http(s) URL, or null. */
    fun host(url: String): String? {
        val uri = try { URI(url.trim()) } catch (e: Exception) { return null }
        val scheme = uri.scheme?.lowercase() ?: return null
        if (scheme != "http" && scheme != "https") return null
        val raw = uri.host ?: uri.rawAuthority?.substringAfterLast('@')?.substringBefore(':') ?: return null
        return try { IDN.toASCII(raw.trimEnd('.'), IDN.ALLOW_UNASSIGNED).lowercase() } catch (e: Exception) { null }
    }

    fun unicodeHost(host: String): String = try { IDN.toUnicode(host) } catch (e: Exception) { host }

    fun hasUserinfo(url: String): Boolean = try { URI(url.trim()).rawUserInfo != null } catch (e: Exception) { false }

    fun isIp(host: String): Boolean = host.matches(Regex("""\d{1,3}(\.\d{1,3}){3}""")) || host.startsWith("[")

    /** The host and each parent name, most specific first: a.b.example.com, b.example.com, example.com. */
    fun parents(host: String): List<String> {
        val labels = host.split('.')
        return (0 until labels.size - 1).map { labels.drop(it).joinToString(".") }
    }

    /** Labels without the public suffix (approximate: the TLD, plus `co.`/`com.` style second levels). */
    fun nameLabels(host: String): List<String> {
        val labels = host.split('.')
        val cut = if (labels.size > 2 && labels[labels.size - 2] in SECOND_LEVELS && labels.last().length == 2) 2 else 1
        return labels.dropLast(cut)
    }

    fun tld(host: String): String = host.substringAfterLast('.')

    /** `tamm-pay.top` → `tamm-pay[.]top`, for anything shown as text. */
    fun defang(host: String): String = host.replace(".", "[.]")
}
