// The offline product tour bundled into the Gatekeeper APK (assets/tour, built by vite.tour.config.ts):
// the phone-only showcase on its own, with no router and no API. The app passes the language as #lang=ar
// and the theme as #light (Showcase.vue reads both from the hash).
import { createApp, h } from 'vue'
import { lang } from '../i18n'
import Showcase from '../pages/Showcase.vue'

const requested = new URLSearchParams(location.hash.slice(1)).get('lang')
if (requested === 'ar' || requested === 'en') lang.value = requested
createApp({ render: () => h(Showcase, { phone: true }) }).mount('#app')
