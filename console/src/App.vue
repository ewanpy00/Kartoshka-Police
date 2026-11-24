<script setup lang="ts">
import { nextTick, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { locale, setLocale, t } from './i18n'
import { officer, officerName, signIn, signOut } from './session'
import { refreshStats, useStats } from './stats'

const route = useRoute()
const { awaiting } = useStats()

onMounted(() => {
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
watch(officer, (value) => {
  if (value) void refreshStats()
})
</script>

<template>
  <div class="banner" role="status">{{ t('demoBanner') }}</div>
  <header class="topbar">
    <div class="brand-block">
      <span class="mark" aria-hidden="true">KP</span>
      <strong class="brand">{{ t('appTitle') }}</strong>
    </div>
    <div class="topbar-end">
      <div class="seg" role="group" :aria-label="t('languageLabel')">
        <button type="button" :aria-pressed="locale === 'en'" @click="setLocale('en')">{{ t('langEn') }}</button>
        <button type="button" :aria-pressed="locale === 'ar'" @click="setLocale('ar')">{{ t('langAr') }}</button>
      </div>
      <template v-if="officer">
        <span class="user">
          <span class="avatar" aria-hidden="true">{{ t('userInitials') }}</span>
          <span class="user-name">{{ officerName() }}</span>
        </span>
        <button class="secondary" @click="signOut">{{ t('signOut') }}</button>
      </template>
    </div>
  </header>
  <div v-if="officer" class="shell">
    <nav class="sidenav" :aria-label="t('navLabel')">
      <RouterLink to="/queue" :class="{ 'router-link-active': route.path.startsWith('/queue') }">
        <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2 3.5h12M2 8h12M2 12.5h8" /></svg>
        <span>{{ t('navQueue') }}</span>
        <span v-if="awaiting !== null" class="count-badge">{{ awaiting }}</span>
      </RouterLink>
      <RouterLink to="/feed">
        <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M1.5 8h3l2-5 3 10 2-5h3" /></svg>
        <span>{{ t('navFeed') }}</span>
      </RouterLink>
      <RouterLink to="/campaigns">
        <svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="4" cy="4" r="1.8" /><circle cx="12" cy="5" r="1.8" /><circle cx="8" cy="12" r="1.8" /><path d="M5.5 5l5 0M5 5.5l2 5M11 6.5l-2 4" /></svg>
        <span>{{ t('navCampaigns') }}</span>
      </RouterLink>
      <RouterLink to="/helplines">
        <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 2.5h3l1 3-1.8 1.2a8 8 0 003.6 3.6L10.5 8.5l3 1v3a1 1 0 01-1 1A10 10 0 012.5 3.5a1 1 0 011-1z" /></svg>
        <span>{{ t('navHelplines') }}</span>
      </RouterLink>
      <RouterLink to="/takedowns">
        <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2 5l6-3 6 3v1H2zM3.5 7v5M8 7v5M12.5 7v5M2 13.5h12" /></svg>
        <span>{{ t('navTakedowns') }}</span>
      </RouterLink>
      <RouterLink to="/chain">
        <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M6.5 9.5l3-3M5 7.5L3.5 9a2.1 2.1 0 003 3L8 10.5M8 5.5L9.5 4a2.1 2.1 0 013 3L11 8.5" /></svg>
        <span>{{ t('navChain') }}</span>
      </RouterLink>
      <RouterLink to="/audit">
        <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 1.500h6l3 3v10H4zM9.5 1.500v3.500h3.500M6 8h5M6 11h5" /></svg>
        <span>{{ t('navAudit') }}</span>
      </RouterLink>
    </nav>
    <main class="content">
      <RouterView />
    </main>
  </div>
  <main v-else class="signed-out">
    <section class="panel signin">
      <h1>{{ t('signInTitle') }}</h1>
      <button @click="signIn">{{ t('signInButton') }}</button>
    </section>
  </main>
</template>
