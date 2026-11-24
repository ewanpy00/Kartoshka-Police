import { createApp } from 'vue'
import App from './App.vue'
import { locale, setLocale } from './i18n'
import { router } from './router'
import { initTheme } from './theme'
import './style.css'

initTheme()
setLocale(locale.value)
createApp(App).use(router).mount('#app')
