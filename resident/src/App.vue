<script setup lang="ts">
import { embedded } from './embedded'
import { lang, tr } from './i18n'

// Outline icons (24px grid), drawn with currentColor so they follow the active tab colour.
const ICONS = {
  home: 'M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z',
  sms: 'M4 4h16a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H8l-4 4V5a1 1 0 0 1 1-1zM8 10h.01M12 10h.01M16 10h.01',
  reports: 'M5 21V4h9l1 2h4v9h-6l-1-2H5',
  radar: 'M12 12 19 5M21 12a9 9 0 1 1-9-9M17 12a5 5 0 1 1-5-5M12 12h.01',
}
</script>

<template>
  <header v-if="!embedded" class="top">
    <RouterLink to="/" class="brand">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2 4 5v6c0 5 3.4 9.7 8 11 4.6-1.3 8-6 8-11V5z" /><path d="m8.5 12 2.5 2.5 4.5-5" /></svg>
      {{ tr('Kartoshka link check', 'كارتوشكا · فحص الروابط') }}
    </RouterLink>
    <button class="lang" @click="lang = lang === 'ar' ? 'en' : 'ar'">{{ lang === 'ar' ? 'English' : 'العربية' }}</button>
  </header>
  <RouterView />
  <nav v-if="!embedded" class="tabs">
    <RouterLink v-for="[to, icon, en, ar] in ([['/', 'home', 'Home', 'الرئيسية'], ['/sms', 'sms', 'Paste SMS', 'لصق رسالة'], ['/reports', 'reports', 'My reports', 'بلاغاتي'], ['/radar', 'radar', 'Scam radar', 'رادار الاحتيال']] as const)" :key="to" :to="to">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path :d="ICONS[icon]" /></svg>
      <span>{{ tr(en, ar) }}</span>
    </RouterLink>
  </nav>
</template>

<style scoped>
svg { width: 1.35rem; height: 1.35rem; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.top { display: flex; align-items: center; justify-content: space-between; padding: 0.7rem 1rem; background: var(--header); color: var(--on-header);
  border-bottom: 1px solid var(--line); }
.brand { display: inline-flex; align-items: center; gap: 0.5rem; color: var(--on-header); font-weight: 700; text-decoration: none; }
.brand svg { color: var(--header-gold); }
.lang { min-height: 2.2rem; padding: 0.2rem 0.8rem; background: transparent; color: var(--on-header); border-color: rgb(255 255 255 / 0.35); border-radius: 999px; }
.tabs { position: fixed; inset-inline: 0; bottom: 0; display: grid; grid-template-columns: repeat(4, 1fr); background: var(--surface);
  border-top: 1px solid var(--line); padding-bottom: env(safe-area-inset-bottom); }
.tabs a { display: grid; justify-items: center; gap: 0.15rem; padding: 0.55rem 0.2rem 0.6rem; color: var(--muted); text-decoration: none;
  font-size: 0.75rem; font-weight: 600; }
.tabs a.router-link-exact-active { color: var(--accent); }
.tabs a.router-link-exact-active svg { background: var(--grey-soft); border-radius: 999px; padding: 0.15rem 0.9rem; width: 3.2rem; box-sizing: content-box; }
</style>
