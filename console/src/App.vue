<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import HealthStrip from './components/HealthStrip.vue'
import { lang, t, toggleLang } from './i18n'
import { session, signOut } from './session'
import { cycleTheme, theme } from './theme'

const router = useRouter()
const route = useRoute()
// Until the first route resolves nothing is matched; keep the chrome hidden so /live never flashes it.
const bare = computed(() => route.matched.length === 0 || route.meta.bare === true)
const nav = [
  ['queue', 'nav.queue'],
  ['live', 'nav.live'],
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
  <div v-if="!bare" class="demo-banner">{{ t('demo.banner') }}</div>
  <header v-if="session && !bare" class="top">
    <strong class="brand">{{ t('app.title') }}</strong>
    <nav>
      <RouterLink v-for="[name, label] in nav" :key="name" :to="{ name }">{{ t(label) }}</RouterLink>
    </nav>
    <span class="spacer" />
    <HealthStrip />
    <button class="ghost theme" :title="t(`theme.${theme}`)" :aria-label="t(`theme.${theme}`)" @click="cycleTheme">
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path v-if="theme === 'dark'" d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5Z" />
        <template v-else-if="theme === 'light'"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></template>
        <template v-else><circle cx="12" cy="12" r="8" /><path d="M12 4a8 8 0 0 1 0 16Z" fill="currentColor" /></template>
      </svg>
    </button>
    <button class="ghost" @click="toggleLang">{{ lang === 'ar' ? 'English' : 'العربية' }}</button>
    <span class="muted small">{{ session.name }}</span>
    <button class="ghost" @click="leave">{{ t('nav.signout') }}</button>
  </header>
  <RouterView v-slot="{ Component, route: current }">
    <Transition name="page" mode="out-in">
      <component :is="Component" :key="current.matched[0]?.path" />
    </Transition>
  </RouterView>
</template>

<style scoped>
.demo-banner { background: var(--banner); color: #fff; text-align: center; font-size: 0.8rem; padding: 0.2rem; }
.top { display: flex; align-items: center; gap: 1rem; padding: 0.5rem 1.25rem; background: var(--surface); border-bottom: 1px solid var(--line); flex-wrap: wrap; }
.brand { font-size: 0.95rem; }
nav { display: flex; gap: 0.25rem; flex-wrap: wrap; }
nav a { padding: 0.3rem 0.6rem; border-radius: 6px; color: var(--muted); text-decoration: none; font-weight: 550; }
nav a { transition: background-color var(--dur-fast) ease, color var(--dur-fast) ease; }
nav a:hover { color: var(--text); }
nav a.router-link-active { background: var(--accent-soft); color: var(--accent); }
.theme svg { width: 1.05rem; height: 1.05rem; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; }
.spacer { flex: 1; }
</style>
