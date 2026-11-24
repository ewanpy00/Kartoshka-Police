package ae.kartoshka.gatekeeper.logic

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

class LogicTest {
    private val catalog = Catalog.fromJson(File("src/main/assets/brands.json").readText())
    private val lexical = Lexical(catalog)

    private fun verdict(v: String, score: Int, brand: String? = null, deep: String? = null) = Verdict(
        "c1", "https://x.top/", v, score, "fast", brand, null,
        listOf(Reason("RISKY_TLD", "The .top ending…", "النهاية…")), emptyList(), deep, null,
    )

    @Test fun extractsLinksFromArabicSms() {
        val sms = "عزيزي العميل، لديك مخالفة مرورية. ادفع الآن: tamm-fines-pay.top/pay?id=4 أو https://rta-ae.xyz/x."
        assertEquals(listOf("https://tamm-fines-pay.top/pay?id=4", "https://rta-ae.xyz/x"), Links.extract(sms))
        assertEquals(emptyList<String>(), Links.extract("see you at 5.30 tomorrow"))
    }

    @Test fun hostsAreAsciiAndParentsAreChecked() {
        assertEquals("xn--tmm-qla.com", Links.host("https://tämm.com/a"))
        assertNull(Links.host("javascript:alert(1)"))
        assertEquals(listOf("a.b.example.com", "b.example.com", "example.com"), Links.parents("a.b.example.com"))
        assertEquals("tamm-pay[.]top", Links.defang("tamm-pay.top"))
    }

    @Test fun officialDomainsAreAllowedLocally() {
        val score = lexical.score("https://www.tamm.abudhabi/wb/adp/pay-traffic-fines")
        assertTrue(score.official)
        assertEquals(Action.Forward, Decision.decide("https://www.tamm.abudhabi/", score, false, Remote.Offline, catalog))
    }

    @Test fun lookalikeScoresHighAndOffersTheRealService() {
        val url = "https://tamm-fines-pay.top/pay"
        val score = lexical.score(url)
        assertEquals("tamm", score.brandId)
        assertTrue("score ${score.score}", score.score > Decision.BLOCK_ABOVE)
        val action = catalog.safeAction("tamm", url)
        assertNotNull(action)
        assertTrue(action!!.url.startsWith("https://www.tamm.abudhabi/"))
    }

    @Test fun shortTokensMatchWholeWordsOnly() {
        assertEquals("rta", lexical.score("https://rta-fines.com/").brandId)
        assertNull(lexical.score("https://portal.example.com/").brandId)
    }

    @Test fun coreVerdictWins() {
        val local = lexical.score("https://tamm-fines-pay.top/pay")
        assertEquals(Action.Forward, Decision.decide("u", local, false, Remote.Answer(verdict("allow", 10)), catalog))
        val warn = Decision.decide("u", local, false, Remote.Answer(verdict("warn", 50, "tamm", "queued")), catalog)
        assertTrue(warn is Action.Warn && warn.page.deepRunning && warn.page.safeAction != null)
        assertTrue(Decision.decide("u", local, false, Remote.Answer(verdict("block", 90)), catalog) is Action.Block)
    }

    @Test fun timeoutRules() {
        val low = lexical.score("https://bakery-dubai.com/menu")
        val high = lexical.score("https://tamm-fines-pay.top/pay")
        assertEquals(Action.Forward, Decision.decide("u", low, false, Remote.Timeout, catalog))
        assertEquals(Action.Checking, Decision.decide("u", high, false, Remote.Timeout, catalog))
        assertTrue(Decision.afterWait("u", high, false, catalog) is Action.Block)
        assertTrue(Decision.decide("u", high, false, Remote.Offline, catalog) is Action.Block)
        val listed = Decision.decide("https://clean-name.com/", low, true, Remote.Timeout, catalog)
        assertTrue(listed is Action.Block && (listed as Action.Block).page.reasons.first().code == "POLICE_CONFIRMED")
        val pending = Remote.Answer(verdict("pending", 0))
        assertEquals(Action.Forward, Decision.decide("u", low, false, pending, catalog))
    }

    @Test fun bloomHasNoFalseNegatives() {
        val domains = (1..5000).map { "scam$it.top" }
        val bloom = Bloom.of(domains)
        assertTrue(domains.all(bloom::mightContain))
        val falsePositives = (1..20000).count { bloom.mightContain("clean$it.com") }
        assertTrue("false positives $falsePositives", falsePositives < 20)
        assertFalse(Bloom.of(emptyList()).mightContain("example.com"))
    }

    @Test fun parsesCoreVerdict() {
        val v = Verdict.fromJson("""{"check_id":"abc","url":"https://x.top/","final_url":null,"verdict":"warn","score":55,
            "stage":"fast","brand":"tamm","safe_action":{"label_en":"Pay fines in TAMM","label_ar":"ادفع","url":"https://www.tamm.abudhabi/"},
            "reasons":[{"code":"RISKY_TLD","weight":null,"source":"kartoshka","en":"e","ar":"a"}],
            "sources":[{"id":"gsb","status":"skipped","detail":null}],"preview":null,"deep_status":"queued","campaign_id":null,"evidence_id":null}""")
        assertEquals("warn", v.verdict)
        assertEquals("Pay fines in TAMM", v.safeAction?.labelEn)
        assertEquals("queued", v.deepStatus)
        assertNull(v.evidenceId)
    }
}
