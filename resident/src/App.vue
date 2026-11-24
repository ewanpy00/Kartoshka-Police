<script setup lang="ts">
import { lang, tr } from './i18n'

const demoEnvironment = import.meta.env.VITE_DEMO_BANNER === 'true'
</script>

<template>
  <div v-if="demoEnvironment" class="demo" role="status">{{ tr('Demo environment', 'بيئة تجريبية') }}</div>
  <header class="top">
    <RouterLink to="/" class="brand">{{ tr('Kartoshka link check', 'كارتوشكا · فحص الروابط') }}</RouterLink>
    <button class="lang" @click="lang = lang === 'ar' ? 'en' : 'ar'">{{ lang === 'ar' ? 'English' : 'العربية' }}</button>
  </header>
  <RouterView />
  <nav class="tabs">
    <RouterLink to="/">{{ tr('Home', 'الرئيسية') }}</RouterLink>
    <RouterLink to="/sms">{{ tr('Paste SMS', 'لصق رسالة') }}</RouterLink>
    <RouterLink to="/reports">{{ tr('My reports', 'بلاغاتي') }}</RouterLink>
    <RouterLink to="/radar">{{ tr('Scam radar', 'رادار الاحتيال') }}</RouterLink>
  </nav>
</template>

<style scoped>
.demo { padding: var(--space-1) var(--space-4); background: var(--c-selected); color: var(--c-ink); font-size: var(--fs-12); font-weight: 600; text-align: center; border-block-end: 1px solid var(--c-hairline); }
.top { display: flex; align-items: center; justify-content: space-between; padding: var(--space-2) var(--space-4); background: var(--c-surface); color: var(--c-ink); border-block-end: 1px solid var(--c-hairline); }
.brand { color: var(--c-ink); font-weight: 600; text-decoration: none; }
.lang { min-height: 2.2rem; padding: var(--space-1) var(--space-3); font-size: var(--fs-13); }
.tabs { position: fixed; inset-inline: 0; bottom: 0; display: grid; grid-template-columns: repeat(4, 1fr); background: var(--c-surface);
  border-block-start: 1px solid var(--c-hairline); padding-bottom: env(safe-area-inset-bottom); }
.tabs a { text-align: center; padding: var(--space-3) var(--space-1); color: var(--c-muted); text-decoration: none; font-size: var(--fs-13); font-weight: 600; }
.tabs a.router-link-exact-active { color: var(--c-ink); background: var(--c-selected); box-shadow: inset 0 -2px 0 var(--c-accent); }
</style>
