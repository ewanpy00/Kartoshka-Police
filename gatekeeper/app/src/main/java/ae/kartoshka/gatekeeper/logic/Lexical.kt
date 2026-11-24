package ae.kartoshka.gatekeeper.logic

/** One reason, in both languages. [weight] stays on the phone; the screens show only the text. */
data class LocalReason(val code: String, val weight: Int, val en: String, val ar: String)

data class LocalScore(val score: Int, val reasons: List<LocalReason>, val brandId: String?, val official: Boolean)

/**
 * The tiny on-device scorer (ARCHITECTURE.md section 3): a subset of core's lexical features with core's
 * weights (core/app/fast/lexical.py, core/app/verdict/reasons.py). No network. It only decides what to
 * do while core is slow or unreachable; core's verdict always wins when it arrives in time.
 */
class Lexical(private val catalog: Catalog) {
    fun score(url: String): LocalScore {
        val host = Links.host(url) ?: return LocalScore(0, emptyList(), null, false)
        catalog.official(host)?.let { return LocalScore(0, emptyList(), it.id, true) }
        val reasons = mutableListOf<LocalReason>()
        var brand: Brand? = null
        val labels = Links.nameLabels(host)
        val words = labels.flatMap { it.split('-') }.filter { it.isNotEmpty() }
        val squashed = labels.joinToString("") { it.replace("-", "") }
        val path = url.substringAfter(host, "").lowercase()

        if (!Links.isIp(host)) {
            for (b in catalog.brands) {
                val token = b.tokens.firstOrNull { t -> if (t.length >= 5) t in squashed else words.any { it == t } }
                if (token != null) {
                    brand = b
                    reasons += LocalReason("BRAND_IN_DOMAIN", 40,
                        "Domain uses '$token' but is not an official ${b.nameEn} domain",
                        "النطاق يستخدم اسم '$token' لكنه ليس نطاقًا رسميًا لـ${b.nameAr}")
                    break
                }
            }
        }
        if (host.contains("xn--")) {
            reasons += LocalReason("PUNYCODE", 10, "Domain is written in encoded international characters", "النطاق مكتوب بأحرف دولية مشفّرة")
        }
        val actions = (words + Regex("[a-z]+").findAll(path).map { it.value }).filter { it in ACTION_WORDS }.distinct()
        if (actions.isNotEmpty()) {
            val inHost = words.any { it in ACTION_WORDS }
            reasons += LocalReason("ACTION_WORDS", if (inHost) 10 else 5,
                "Address contains pressure words: ${actions.take(4).joinToString(", ")}",
                "العنوان يحتوي على كلمات ضغط: ${actions.take(4).joinToString("، ")}")
            if (brand != null) {
                reasons += LocalReason("BRAND_ACTION", 15, "A ${brand.nameEn} name is combined with a payment or login word",
                    "اسم ${brand.nameAr} مقرون بكلمة دفع أو تسجيل دخول")
            }
        }
        val tld = Links.tld(host)
        if (tld in RISKY_TLDS) {
            reasons += LocalReason("RISKY_TLD", 15, "The .$tld ending is common on scam sites", "النهاية ‎.$tld‎ شائعة في مواقع الاحتيال")
        }
        if (Links.isIp(host)) {
            reasons += LocalReason("IP_HOST", 25, "Link points to a bare IP address instead of a name", "الرابط يشير إلى عنوان IP مباشر بدلًا من اسم")
        }
        if (Links.hasUserinfo(url)) {
            reasons += LocalReason("USERINFO", 15, "Link hides its real destination after an @ sign", "الرابط يخفي وجهته الحقيقية بعد علامة @")
        }
        if (FREE_HOSTING.any { host.endsWith(".$it") }) {
            reasons += LocalReason("FREE_HOSTING", 20, "Page is on a free hosting service", "الصفحة على خدمة استضافة مجانية")
        }
        if (host.length > 45) reasons += LocalReason("LONG_HOST", 5, "Unusually long address", "عنوان طويل بشكل غير معتاد")
        if (labels.size - 1 >= 3) {
            reasons += LocalReason("MANY_SUBDOMAINS", 10, "Address has many nested subdomains", "العنوان يحتوي على نطاقات فرعية متداخلة كثيرة")
        }
        return LocalScore(reasons.sumOf { it.weight }.coerceAtMost(100), reasons, brand?.id, false)
    }

    companion object {
        val ACTION_WORDS = """pay payment payments fine fines verify verification renew renewal refund update secure security login
            signin logon account unlock blocked suspend suspended confirm otp wallet bonus reward rewards claim prize gift
            delivery parcel customs track tracking toll unpaid due urgent alert invoice bill kyc reactivate recover
            redeliver redelivery release reschedule service portal online card auth sso recovery connect
            restore validate validation appeal violation locked signup password billing""".split(Regex("\\s+")).toSet()
        val RISKY_TLDS = """top xyz icu shop cyou sbs buzz click live online site vip cc win bond rest lol mom quest cfd fun space
            tk ml ga cf gq pw monster autos today life link work support help info cam bar lat ink mobi""".split(Regex("\\s+")).toSet()
        val FREE_HOSTING = """github.io pages.dev web.app firebaseapp.com vercel.app netlify.app herokuapp.com glitch.me blogspot.com
            weebly.com wixsite.com 000webhostapp.com workers.dev onrender.com ngrok-free.app ngrok.io r2.dev""".split(Regex("\\s+")).toSet()
    }
}
