<script setup lang="ts">
import { lang, tr } from './i18n'
</script>

<template>
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
.top { display: flex; align-items: center; justify-content: space-between; padding: 0.6rem 1rem; background: var(--accent); color: #fff; }
.brand { color: #fff; font-weight: 700; text-decoration: none; }
.lang { min-height: 2.2rem; padding: 0.2rem 0.7rem; background: transparent; color: #fff; border-color: rgb(255 255 255 / 0.5); }
.tabs { position: fixed; inset-inline: 0; bottom: 0; display: grid; grid-template-columns: repeat(4, 1fr); background: var(--surface);
  border-top: 1px solid var(--line); padding-bottom: env(safe-area-inset-bottom); }
.tabs a { text-align: center; padding: 0.8rem 0.2rem; color: var(--muted); text-decoration: none; font-size: 0.85rem; font-weight: 600; }
.tabs a.router-link-exact-active { color: var(--accent); }
</style>
