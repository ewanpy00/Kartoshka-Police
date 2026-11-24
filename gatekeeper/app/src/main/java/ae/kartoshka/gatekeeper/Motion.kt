package ae.kartoshka.gatekeeper

import android.animation.ObjectAnimator
import android.animation.PropertyValuesHolder
import android.animation.ValueAnimator
import android.view.View
import android.view.animation.DecelerateInterpolator
import android.view.animation.OvershootInterpolator

/**
 * The few animations the app uses. They follow the system "animator duration scale", so with animations
 * turned off in the phone's settings everything appears at once.
 */
object Motion {
    /** A gold ring that grows and fades behind a shield, over and over. */
    fun pulse(ring: View, periodMs: Long = 1400): ValueAnimator =
        ObjectAnimator.ofPropertyValuesHolder(
            ring,
            PropertyValuesHolder.ofFloat(View.SCALE_X, 0.85f, 1.7f),
            PropertyValuesHolder.ofFloat(View.SCALE_Y, 0.85f, 1.7f),
            PropertyValuesHolder.ofFloat(View.ALPHA, 0.9f, 0f),
        ).apply {
            duration = periodMs
            repeatCount = ValueAnimator.INFINITE
            interpolator = DecelerateInterpolator()
            start()
        }

    /** Scale a view in from small with a slight overshoot. */
    fun popIn(view: View, delayMs: Long = 0, from: Float = 0.6f) {
        view.scaleX = from
        view.scaleY = from
        view.alpha = 0f
        view.animate().scaleX(1f).scaleY(1f).alpha(1f).setStartDelay(delayMs).setDuration(450)
            .setInterpolator(OvershootInterpolator(1.6f)).start()
    }

    /** Slide views up into place one after another. */
    fun stagger(views: List<View>, startMs: Long = 0, stepMs: Long = 60) {
        val distance = 24f * (views.firstOrNull()?.resources?.displayMetrics?.density ?: 1f)
        views.forEachIndexed { i, view ->
            view.alpha = 0f
            view.translationY = distance
            view.animate().alpha(1f).translationY(0f).setStartDelay(startMs + i * stepMs).setDuration(380)
                .setInterpolator(DecelerateInterpolator()).start()
        }
    }

    /** A short horizontal shake, for the block icon. */
    fun shake(view: View, delayMs: Long = 0) {
        val d = 6f * view.resources.displayMetrics.density
        ObjectAnimator.ofFloat(view, View.TRANSLATION_X, 0f, -d, d, -d, d, -d / 2, d / 2, 0f).apply {
            duration = 480
            startDelay = delayMs
            start()
        }
    }
}
