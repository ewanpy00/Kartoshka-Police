package ae.kartoshka.gatekeeper.logic

import java.security.MessageDigest
import kotlin.math.ceil
import kotlin.math.ln
import kotlin.math.max

/**
 * Bloom filter of the police-confirmed blocklist, rebuilt after every sync. Lookups need no network and
 * take microseconds. A false positive (about 1 in 10,000 at the default size) only means core is asked
 * before the block page shows; offline, a hit blocks.
 */
class Bloom(private val bits: Int, private val hashes: Int) {
    private val words = LongArray((bits + 63) / 64)

    fun put(value: String) = positions(value).forEach { words[it ushr 6] = words[it ushr 6] or (1L shl (it and 63)) }

    fun mightContain(value: String): Boolean = positions(value).all { words[it ushr 6] and (1L shl (it and 63)) != 0L }

    private fun positions(value: String): IntArray {
        val digest = MessageDigest.getInstance("SHA-256").digest(value.toByteArray())
        var h1 = 0L
        var h2 = 0L
        for (i in 0 until 8) {
            h1 = (h1 shl 8) or (digest[i].toLong() and 0xff)
            h2 = (h2 shl 8) or (digest[i + 8].toLong() and 0xff)
        }
        return IntArray(hashes) { i -> Math.floorMod(h1 + i * h2, bits.toLong()).toInt() }
    }

    companion object {
        fun of(domains: Collection<String>, falsePositive: Double = 1e-4): Bloom {
            val n = max(domains.size, 1000)
            val m = ceil(-n * ln(falsePositive) / (ln(2.0) * ln(2.0))).toInt()
            val k = max(1, Math.round(m.toDouble() / n * ln(2.0)).toInt())
            return Bloom(m, k).also { bloom -> domains.forEach(bloom::put) }
        }
    }
}
