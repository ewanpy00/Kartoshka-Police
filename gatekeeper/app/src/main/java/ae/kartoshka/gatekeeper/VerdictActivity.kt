package ae.kartoshka.gatekeeper

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.content.res.ColorStateList
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.google.android.material.button.MaterialButton
import com.google.android.material.divider.MaterialDivider
import ae.kartoshka.gatekeeper.logic.Links
import ae.kartoshka.gatekeeper.logic.Page
import ae.kartoshka.gatekeeper.logic.Reason
import ae.kartoshka.gatekeeper.logic.SafeAction
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

/**
 * The warn interstitial and the block page, Arabic first (section 3). Buttons: Go to the real service,
 * Go back, Open anyway (warn only), Report to police, and Details (the resident X-ray and safe preview).
 * Everything from the page or the link is shown as plain text; the domain is defanged.
 */
class VerdictActivity : AppCompatActivity() {
    private val app get() = application as GatekeeperApp

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val blocked = intent.getBooleanExtra(EXTRA_BLOCKED, true)
        val page = intent.getStringExtra(EXTRA_PAGE)?.let(::decode) ?: return finish()
        setContentView(R.layout.activity_verdict)

        val heroColor = getColor(if (blocked) R.color.block_hero else R.color.warn_hero)
        window.statusBarColor = heroColor
        findViewById<View>(R.id.verdict_hero).setBackgroundColor(heroColor)
        val icon = findViewById<ImageView>(R.id.verdict_icon)
        icon.setImageResource(if (blocked) R.drawable.ic_block else R.drawable.ic_warning)
        findViewById<TextView>(R.id.title_ar).text = getString(if (blocked) R.string.block_title_ar else R.string.warn_title_ar)
        findViewById<TextView>(R.id.title_en).text = getString(if (blocked) R.string.block_title_en else R.string.warn_title_en)
        findViewById<TextView>(R.id.domain).text = Links.host(page.url)?.let { Links.defang(Links.unicodeHost(it)) } ?: ""
        app.catalog.brand(page.brandId)?.let { brand ->
            findViewById<View>(R.id.brand_card).visibility = View.VISIBLE
            findViewById<TextView>(R.id.brand).text = getString(R.string.imitates, brand.nameAr, brand.nameEn)
        }

        val list = findViewById<LinearLayout>(R.id.reasons)
        val reasonTint = ColorStateList.valueOf(getColor(if (blocked) R.color.risk else R.color.amber))
        page.reasons.take(6).forEachIndexed { i, reason ->
            if (i > 0) list.addView(MaterialDivider(this).apply { dividerColor = getColor(R.color.hairline) })
            val row = LayoutInflater.from(this).inflate(R.layout.item_reason, list, false)
            row.findViewById<ImageView>(R.id.reason_icon).imageTintList = reasonTint
            row.findViewById<TextView>(R.id.reason_ar).text = reason.ar
            row.findViewById<TextView>(R.id.reason_en).text = reason.en
            list.addView(row)
        }
        if (!page.fromCore) findViewById<View>(R.id.offline_note).visibility = View.VISIBLE

        findViewById<MaterialButton>(R.id.safe_action).apply {
            val action = page.safeAction
            if (action == null) visibility = View.GONE else {
                text = "${action.labelAr}\n${action.labelEn}"
                setOnClickListener { Browsers.open(this@VerdictActivity, action.url); finish() }
            }
        }
        findViewById<View>(R.id.close).setOnClickListener { finish() }
        findViewById<View>(R.id.go_back).setOnClickListener { finish() }
        findViewById<View>(R.id.open_anyway).apply {
            visibility = if (blocked) View.GONE else View.VISIBLE
            setOnClickListener { Browsers.open(this@VerdictActivity, page.url); finish() }
        }
        findViewById<MaterialButton>(R.id.report).setOnClickListener { report(page.url, it as MaterialButton) }
        findViewById<View>(R.id.details).setOnClickListener {
            startActivity(Intent(this, ResidentActivity::class.java).putExtra(ResidentActivity.EXTRA_PATH, ResidentActivity.checkPath(page.url)))
        }

        if (savedInstanceState == null) {
            Motion.popIn(icon, from = 0.3f)
            if (blocked) Motion.shake(icon, delayMs = 420)
            Motion.stagger(listOf(findViewById(R.id.verdict_body), findViewById(R.id.verdict_actions)), startMs = 150, stepMs = 90)
        }
    }

    private fun report(url: String, button: MaterialButton) {
        button.isEnabled = false
        lifecycleScope.launch {
            val result = withContext(Dispatchers.IO) { runCatching { app.core.report(url) } }
            result.onSuccess { app.store.saveReport(it.reportId, it.token, url) }
            Toast.makeText(this@VerdictActivity, if (result.isSuccess) R.string.report_sent else R.string.report_failed, Toast.LENGTH_LONG).show()
            button.isEnabled = result.isFailure
        }
    }

    companion object {
        private const val EXTRA_PAGE = "page"
        private const val EXTRA_BLOCKED = "blocked"

        fun intent(context: Context, page: Page, blocked: Boolean): Intent =
            Intent(context, VerdictActivity::class.java).putExtra(EXTRA_PAGE, encode(page)).putExtra(EXTRA_BLOCKED, blocked)

        fun encode(page: Page): String = JSONObject()
            .put("url", page.url).put("brand", page.brandId).put("check_id", page.checkId)
            .put("from_core", page.fromCore).put("deep", page.deepRunning)
            .put("reasons", JSONArray(page.reasons.map { JSONObject().put("code", it.code).put("en", it.en).put("ar", it.ar) }))
            .put("safe_action", page.safeAction?.let { JSONObject().put("label_en", it.labelEn).put("label_ar", it.labelAr).put("url", it.url) })
            .toString()

        fun decode(text: String): Page {
            val o = JSONObject(text)
            val reasons = o.getJSONArray("reasons")
            val action = o.optJSONObject("safe_action")
            return Page(
                url = o.getString("url"),
                brandId = o.optString("brand").takeIf { it.isNotEmpty() && !o.isNull("brand") },
                reasons = (0 until reasons.length()).map { reasons.getJSONObject(it).let { r -> Reason(r.getString("code"), r.getString("en"), r.getString("ar")) } },
                safeAction = action?.let { SafeAction(it.getString("label_en"), it.getString("label_ar"), it.getString("url")) },
                checkId = o.optString("check_id").takeIf { it.isNotEmpty() && !o.isNull("check_id") },
                fromCore = o.optBoolean("from_core"),
                deepRunning = o.optBoolean("deep"),
            )
        }
    }
}
