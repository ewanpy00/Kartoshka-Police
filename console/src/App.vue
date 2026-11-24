<script setup lang="ts">
// Shell in the style of the admin console on main (PR #2): demo banner, top bar with the KP mark, language and
// theme switches, and a side menu (a scrolling strip under 900px). /live has no shell.
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import HealthStrip from './components/HealthStrip.vue'
import { lang, t } from './i18n'
import type { MessageKey } from './i18n/en'
import { session, signOut } from './session'
import { theme, type Theme } from './theme'

const router = useRouter()
const route = useRoute()
// Until the first route resolves nothing is matched; keep the chrome hidden so /live never flashes it.
const bare = computed(() => route.matched.length === 0 || route.meta.bare === true)

const NAV: { name: string; label: MessageKey; icon: string }[] = [
  { name: 'queue', label: 'nav.queue', icon: 'M2 3.5h12M2 8h12M2 12.5h8' },
  { name: 'live', label: 'nav.live', icon: 'M8 8h.01M5.2 10.8a4 4 0 0 1 0-5.6M10.8 5.2a4 4 0 0 1 0 5.6M3.1 12.9a7 7 0 0 1 0-9.8M12.9 3.1a7 7 0 0 1 0 9.8' },
  { name: 'hunter', label: 'nav.hunter', icon: 'M1.5 8h3l2-5 3 10 2-5h3' },
  { name: 'campaigns', label: 'nav.campaigns', icon: 'M5.5 5h5M5 5.5l2 5M11 6.5l-2 4M4 2.2a1.8 1.8 0 1 1 0 3.6 1.8 1.8 0 0 1 0-3.6ZM12 3.2a1.8 1.8 0 1 1 0 3.6 1.8 1.8 0 0 1 0-3.6ZM8 10.2a1.8 1.8 0 1 1 0 3.6 1.8 1.8 0 0 1 0-3.6Z' },
  { name: 'takedowns', label: 'nav.takedowns', icon: 'M2 5l6-3 6 3v1H2zM3.5 7v5M8 7v5M12.5 7v5M2 13.5h12' },
  { name: 'impact', label: 'nav.impact', icon: 'M2 13.5h12M4 11V7M8 11V3M12 11V8' },
  { name: 'quality', label: 'nav.quality', icon: 'M8 1.5l1.9 3.9 4.3.6-3.1 3 .7 4.3L8 11.3l-3.8 2 .7-4.3-3.1-3 4.3-.6z' },
  { name: 'health', label: 'nav.health', icon: 'M1.5 8h3l1.5-3 3 6 1.5-3h4' },
]
const THEMES: { value: Theme; label: MessageKey; icon: string }[] = [
  { value: 'system', label: 'theme.system', icon: 'M2 3h12v8H2zM5.5 14h5M8 11v3' },
  { value: 'light', label: 'theme.light', icon: 'M8 5a3 3 0 1 1 0 6 3 3 0 0 1 0-6ZM8 1.5V3M8 13v1.5M1.5 8H3M13 8h1.5M3.4 3.4l1 1M11.6 11.6l1 1M3.4 12.6l1-1M11.6 4.4l1-1' },
  { value: 'dark', label: 'theme.dark', icon: 'M13.5 9.5A5.5 5.5 0 0 1 6.5 2.5a5.5 5.5 0 1 0 7 7z' },
]

const initials = computed(() => (session.value?.name ?? '').split(/\s+/).map((w) => w[0] ?? '').join('').slice(0, 2).toUpperCase())

// The side menu sticks under the header, whose height changes with the banner wrapping and the phone layout.
const head = ref<HTMLElement | null>(null)
let observer: ResizeObserver | null = null
onMounted(() => {
  if (typeof ResizeObserver === 'undefined') return
  observer = new ResizeObserver(() => {
    if (head.value) document.documentElement.style.setProperty('--head-h', `${head.value.getBoundingClientRect().height}px`)
  })
  if (head.value) observer.observe(head.value)
})
onBeforeUnmount(() => observer?.disconnect())

function leave() {
  signOut()
  router.push({ name: 'login' })
}
</script>

<template>
  <div v-if="!bare" ref="head" class="app-head">
    <div class="banner" role="status">{{ t('demo.banner') }}</div>
    <header class="topbar">
      <RouterLink :to="{ name: 'queue' }" class="brand-block">
        <span class="mark" aria-hidden="true">KP</span>
        <strong class="brand">{{ t('app.title') }}</strong>
      </RouterLink>
      <div class="topbar-end">
        <HealthStrip v-if="session" class="health" />
        <div class="seg" role="group" aria-label="Language">
          <button type="button" :aria-pressed="lang === 'en'" @click="lang = 'en'">EN</button>
          <button type="button" :aria-pressed="lang === 'ar'" @click="lang = 'ar'">عربي</button>
        </div>
        <div class="seg icons" role="group" aria-label="Theme">
          <button v-for="item in THEMES" :key="item.value" type="button" :aria-pressed="theme === item.value"
                  :title="t(item.label)" :aria-label="t(item.label)" @click="theme = item.value">
            <svg viewBox="0 0 16 16" aria-hidden="true"><path :d="item.icon" /></svg>
          </button>
        </div>
        <template v-if="session">
          <span class="user"><span class="avatar" aria-hidden="true">{{ initials }}</span><span class="user-name">{{ session.name }}</span></span>
          <button class="ghost" @click="leave">{{ t('nav.signout') }}</button>
        </template>
      </div>
    </header>
  </div>

  <div v-if="session && !bare" class="shell">
    <nav class="sidenav" aria-label="Sections">
      <RouterLink v-for="item in NAV" :key="item.name" :to="{ name: item.name }"
                  :class="{ 'router-link-active': route.name === item.name || (item.name === 'queue' && route.name === 'case') || (item.name === 'campaigns' && route.name === 'campaign') }">
        <svg viewBox="0 0 16 16" aria-hidden="true"><path :d="item.icon" /></svg>
        <span>{{ t(item.label) }}</span>
        <span v-if="item.name === 'live'" class="live-dot" />
      </RouterLink>
    </nav>
    <div class="content">
      <RouterView v-slot="{ Component, route: current }">
        <Transition name="page" mode="out-in">
          <component :is="Component" :key="current.matched[0]?.path" />
        </Transition>
      </RouterView>
    </div>
  </div>
  <RouterView v-else v-slot="{ Component, route: current }">
    <Transition name="page" mode="out-in">
      <component :is="Component" :key="current.matched[0]?.path" />
    </Transition>
  </RouterView>
</template>

<style scoped>
.app-head { position: sticky; top: 0; z-index: 30; background: var(--surface); }
.banner { padding: 6px 16px; font-size: 13px; font-weight: 600; text-align: center; color: var(--banner-text); background: var(--banner); border-bottom: 1px solid var(--line); }
.topbar { display: flex; gap: 16px; align-items: center; justify-content: space-between; min-height: 64px; padding-inline: 24px; background: var(--surface); border-bottom: 1px solid var(--line); }
.brand-block { display: flex; gap: 12px; align-items: center; min-width: 0; color: var(--text); text-decoration: none; }
.brand { overflow: hidden; font-size: 16px; text-overflow: ellipsis; white-space: nowrap; }
.mark { display: inline-grid; flex: none; place-items: center; width: 32px; height: 32px; font-size: 12px; font-weight: 700; letter-spacing: 0.04em;
  color: var(--on-primary); background: var(--primary); border-radius: var(--radius-sm); transition: transform var(--dur) var(--ease-spring); }
.brand-block:hover .mark { transform: rotate(-6deg) scale(1.06); }
.topbar-end { display: flex; gap: 12px; align-items: center; margin-inline-start: auto; }
.seg { display: inline-flex; border: 1px solid var(--line); border-radius: var(--radius-sm); overflow: hidden; }
.seg button { padding: 5px 10px; font-size: 13px; color: var(--muted); background: transparent; border: 0; border-radius: 0; font-weight: 500; }
.seg button + button { border-inline-start: 1px solid var(--line); }
.seg button[aria-pressed='true'] { font-weight: 600; color: var(--text); background: var(--selected); }
.seg.icons button { padding: 5px 8px; }
.seg svg, .sidenav svg { width: 16px; height: 16px; flex: none; fill: none; stroke: currentColor; stroke-width: 1.5; stroke-linecap: round; stroke-linejoin: round; }
.user { display: inline-flex; gap: 8px; align-items: center; }
.avatar { display: inline-grid; place-items: center; width: 30px; height: 30px; font-size: 12px; font-weight: 700; color: var(--text); background: var(--selected); border: 1px solid var(--line); border-radius: 50%; }

.shell { display: grid; grid-template-columns: 240px minmax(0, 1fr); align-items: stretch; min-height: calc(100vh - var(--head-h, 95px)); }
.sidenav { position: sticky; top: var(--head-h, 95px); align-self: start; display: flex; flex-direction: column; gap: 2px; height: calc(100dvh - var(--head-h, 95px)); overflow-y: auto;
  padding: 12px; background: var(--surface); border-inline-end: 1px solid var(--line); }
.sidenav a { position: relative; display: flex; gap: 12px; align-items: center; padding: 9px 12px; color: var(--text); text-decoration: none; border-radius: var(--radius-sm);
  transition: background-color var(--dur-fast) ease; }
.sidenav a:hover { background: var(--surface-2); }
.sidenav a.router-link-active { font-weight: 600; background: var(--selected); }
.sidenav a.router-link-active::before { content: ''; position: absolute; inset-inline-start: 0; top: 8px; bottom: 8px; width: 3px; border-radius: 3px; background: var(--accent);
  animation: kp-rise var(--dur) var(--ease-out); }
.live-dot { margin-inline-start: auto; width: 7px; height: 7px; border-radius: 50%; background: var(--block); animation: kp-blink 1.4s infinite; }
.content { min-width: 0; }
.content :deep(.page) { padding: 24px; }

@media (max-width: 1100px) { .health { display: none; } }
@media (max-width: 900px) {
  .topbar { padding-inline: 16px; }
  .shell { grid-template-columns: minmax(0, 1fr); grid-template-rows: auto 1fr; min-height: 0; }
  .sidenav { top: var(--head-h, 95px); z-index: 20; flex-direction: row; height: auto; overflow-x: auto; overflow-y: hidden; padding: 8px 12px; scrollbar-width: none;
    border-inline-end: 0; border-bottom: 1px solid var(--line); }
  .sidenav a { flex: none; white-space: nowrap; }
  .sidenav a.router-link-active::before { top: auto; bottom: 0; left: 12px; right: 12px; width: auto; height: 2px; }
  .content :deep(.page) { padding: 16px; }
}
@media (max-width: 700px) {
  .topbar { flex-wrap: wrap; gap: 8px; padding-block: 8px; }
  .brand-block { flex: 1 1 100%; }
  .topbar-end { flex: 1 1 100%; flex-wrap: nowrap; gap: 8px; margin-inline-start: 0; }
  .avatar, .user-name { display: none; }
  .topbar-end .ghost { margin-inline-start: auto; padding-inline: 8px; }
  .sidenav { top: 0; position: relative; }
}
</style>
