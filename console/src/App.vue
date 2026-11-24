<script setup lang="ts">
import { useRouter } from 'vue-router'
import HealthStrip from './components/HealthStrip.vue'
import { lang, t, toggleLang } from './i18n'
import { session, signOut } from './session'

const router = useRouter()
const nav = [
  ['queue', 'nav.queue'],
  ['hunter', 'nav.hunter'],
  ['campaigns', 'nav.campaigns'],
  ['takedowns', 'nav.takedowns'],
  ['impact', 'nav.impact'],
  ['quality', 'nav.quality'],
  ['health', 'nav.health'],
] as const

function leave() {
  signOut()
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="demo-banner">{{ t('demo.banner') }}</div>
  <header v-if="session" class="top">
    <strong class="brand">{{ t('app.title') }}</strong>
    <nav>
      <RouterLink v-for="[name, label] in nav" :key="name" :to="{ name }">{{ t(label) }}</RouterLink>
    </nav>
    <span class="spacer" />
    <HealthStrip />
    <button class="ghost" @click="toggleLang">{{ lang === 'ar' ? 'English' : 'العربية' }}</button>
    <span class="muted small">{{ session.name }}</span>
    <button class="ghost" @click="leave">{{ t('nav.signout') }}</button>
  </header>
  <RouterView v-slot="{ Component }">
    <component :is="Component" />
  </RouterView>
</template>

<style scoped>
.demo-banner { background: #2b3440; color: #fff; text-align: center; font-size: 0.8rem; padding: 0.2rem; }
.top { display: flex; align-items: center; gap: 1rem; padding: 0.5rem 1.25rem; background: var(--surface); border-bottom: 1px solid var(--line); flex-wrap: wrap; }
.brand { font-size: 0.95rem; }
nav { display: flex; gap: 0.25rem; flex-wrap: wrap; }
nav a { padding: 0.3rem 0.6rem; border-radius: 6px; color: var(--muted); text-decoration: none; font-weight: 550; }
nav a.router-link-active { background: var(--accent-soft); color: var(--accent); }
.spacer { flex: 1; }
</style>
