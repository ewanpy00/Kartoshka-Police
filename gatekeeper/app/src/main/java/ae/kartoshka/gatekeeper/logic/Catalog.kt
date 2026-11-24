package ae.kartoshka.gatekeeper.logic

import org.json.JSONArray

data class Service(val keywords: List<String>, val labelEn: String, val labelAr: String, val url: String)

data class Brand(
    val id: String,
    val nameEn: String,
    val nameAr: String,
    val tokens: List<String>,
    val officialDomains: List<String>,
    val services: List<Service>,
)

data class SafeAction(val labelEn: String, val labelAr: String, val url: String)

/** The offline copy of data/brands.yaml (assets/brands.json, written by tools/brands_json.py). */
class Catalog(val brands: List<Brand>) {
    fun brand(id: String?): Brand? = brands.firstOrNull { it.id == id }

    fun official(host: String): Brand? = brands.firstOrNull { b -> b.officialDomains.any { host == it || host.endsWith(".$it") } }

    /** Same rule as core: a service whose keyword is in the URL or SMS text, else the brand's homepage. */
    fun safeAction(brandId: String?, url: String, text: String = ""): SafeAction? {
        val brand = brand(brandId) ?: return null
        val haystack = "$url $text".lowercase()
        brand.services.firstOrNull { s -> s.keywords.any { it.lowercase() in haystack } }
            ?.let { return SafeAction(it.labelEn, it.labelAr, it.url) }
        brand.services.firstOrNull()?.let { return SafeAction(it.labelEn, it.labelAr, it.url) }
        val home = brand.officialDomains.firstOrNull() ?: return null
        return SafeAction("Go to the official ${brand.nameEn} site", "الانتقال إلى موقع ${brand.nameAr} الرسمي", "https://$home")
    }

    companion object {
        fun fromJson(text: String): Catalog {
            val array = JSONArray(text)
            fun strings(a: JSONArray?) = (0 until (a?.length() ?: 0)).map { a!!.getString(it) }
            return Catalog((0 until array.length()).map { i ->
                val o = array.getJSONObject(i)
                val services = o.optJSONArray("services") ?: JSONArray()
                Brand(
                    id = o.getString("id"),
                    nameEn = o.optString("name_en", o.getString("id")),
                    nameAr = o.optString("name_ar", o.getString("id")),
                    tokens = strings(o.optJSONArray("tokens")),
                    officialDomains = strings(o.optJSONArray("official_domains")),
                    services = (0 until services.length()).map { j ->
                        val s = services.getJSONObject(j)
                        Service(strings(s.optJSONArray("keywords")), s.getString("label_en"), s.getString("label_ar"), s.getString("url"))
                    },
                )
            })
        }
    }
}
