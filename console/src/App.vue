<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { locale, setLocale, t } from './i18n'
import HealthStrip from './components/HealthStrip.vue'
import { navGroups } from './nav'
import { officer, officerName, signIn, signOut } from './session'
import { refreshStats, useStats } from './stats'
import { theme, toggleTheme } from './theme'

const route = useRoute()
const { awaiting } = useStats()

const code = ref('')
const signInError = ref('')
const demoEnvironment = import.meta.env.VITE_DEMO_BANNER === 'true'

async function submitCode(): Promise<void> {
  signInError.value = (await signIn(code.value)) ?? ''
  if (!signInError.value) code.value = ''
}

const head = ref<HTMLElement | null>(null)
let headObserver: ResizeObserver | null = null

onMounted(() => {
  if (typeof ResizeObserver !== 'undefined' && head.value) {
    const el = head.value
    const write = () => document.documentElement.style.setProperty('--head-h', `${el.getBoundingClientRect().height}px`)
    headObserver = new ResizeObserver(write)
    headObserver.observe(el)
    write()
  }
  if (officer.value) void refreshStats()
  void nextTick(() => {
    document.querySelector('.sidenav a.router-link-active')?.scrollIntoView?.({ inline: 'center', block: 'nearest' })
  })
})
watch(
  () => route.fullPath,
  () => {
    void nextTick(() => {
      document.querySelector('.sidenav a.router-link-active')?.scrollIntoView?.({ inline: 'center', block: 'nearest' })
    })
  },
)
onBeforeUnmount(() => headObserver?.disconnect())
watch(officer, (value) => {
  if (value) void refreshStats()
})
</script>

<template>
  <div ref="head" class="app-head">
  <div class="banner" role="status">
    {{ t('demoBanner') }}
    <template v-if="demoEnvironment"><br />{{ t('demoEnvironment') }}</template>
  </div>
  <header class="topbar">
    <div class="brand-block">
      <span class="mark" aria-hidden="true">KP</span>
      <strong class="brand">{{ t('appTitle') }}</strong>
    </div>
    <div class="topbar-end">
      <HealthStrip v-if="officer" />
      <div class="seg" role="group" :aria-label="t('languageLabel')">
        <button type="button" :aria-pressed="locale === 'en'" @click="setLocale('en')">{{ t('langEn') }}</button>
        <button type="button" :aria-pressed="locale === 'ar'" @click="setLocale('ar')">{{ t('langAr') }}</button>
      </div>
      <button
        type="button"
        class="btn ghost theme-toggle"
        :aria-label="theme === 'dark' ? t('themeToLight') : t('themeToDark')"
        :title="theme === 'dark' ? t('themeToLight') : t('themeToDark')"
        :aria-pressed="theme === 'dark'"
        @click="toggleTheme"
      >
        <svg v-if="theme === 'dark'" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="3" /><path d="M8 1.5v1.5M8 13v1.5M1.5 8H3M13 8h1.5M3.4 3.4l1 1M11.6 11.6l1 1M3.4 12.6l1-1M11.6 4.4l1-1" /></svg>
        <svg v-else viewBox="0 0 16 16" aria-hidden="true"><path d="M13.5 9.5A5.5 5.5 0 016.5 2.5a5.5 5.5 0 107 7z" /></svg>
      </button>
      <template v-if="officer">
        <span class="user">
          <span class="avatar" aria-hidden="true">{{ t('userInitials') }}</span>
          <span class="user-name">{{ officerName() }}</span>
        </span>
        <button class="secondary" @click="signOut">{{ t('signOut') }}</button>
      </template>
    </div>
  </header>
  </div>
  <div v-if="officer" class="shell">
    <nav class="sidenav" :aria-label="t('navLabel')">
      <template v-for="group in navGroups" :key="group.label">
        <template v-if="group.items.length">
          <span class="nav-label">{{ t(group.label) }}</span>
          <RouterLink
            v-for="item in group.items"
            :key="item.to"
            :to="item.to"
            :class="{ 'router-link-active': item.to === '/queue' && route.path.startsWith('/queue') }"
          >
            <svg viewBox="0 0 16 16" aria-hidden="true"><path :d="item.icon" /></svg>
            <span>{{ t(item.label) }}</span>
            <span v-if="item.count === 'awaiting' && awaiting !== null" class="count-badge">{{ awaiting }}</span>
          </RouterLink>
        </template>
      </template>
    </nav>
    <main class="content">
      <RouterView />
    </main>
  </div>
  <main v-else class="signed-out">
    <section class="panel signin">
      <h1>{{ t('signInTitle') }}</h1>
      <p class="muted">{{ t('signInDemoLabel') }}</p>
      <form @submit.prevent="submitCode">
        <label for="access-code">{{ t('accessCodeLabel') }}</label>
        <input id="access-code" v-model="code" type="password" autocomplete="off" />
        <p v-if="signInError" class="error" role="alert">{{ signInError }}</p>
        <button type="submit">{{ t('signInButton') }}</button>
      </form>
    </section>
  </main>
</template>
