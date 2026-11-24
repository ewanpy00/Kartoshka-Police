<script setup lang="ts">
// Gatekeeper's Home as drawn in the showcase: header, protection on, the link box, recent checks, tabs.
// `typed` is the text in the box; `caret` shows the cursor; the slot sits over the Check button (for a Tap).
defineProps<{ ar: boolean; typed?: string; caret?: boolean; pressed?: boolean }>()
</script>

<template>
  <div class="home">
    <div class="top">
      <div class="status"><span>10:44</span><span>5G<i /></span></div>
      <div class="brandrow">
        <span class="mark"><svg viewBox="0 0 24 24"><path d="M12 2.5 4 5.5v6c0 4.7 3.4 9 8 10 4.6-1 8-5.3 8-10v-6l-8-3z" /><path d="m8.5 12 2.5 2.5 4.5-5" /></svg></span>
        <span><b>{{ ar ? 'الحارس' : 'Gatekeeper' }}</b><br /><span class="sub">{{ ar ? 'حماية من روابط الاحتيال' : 'Scam link protection' }}</span></span>
      </div>
    </div>
    <div class="pad stack">
      <div class="card on">
        <span class="ok"><svg class="i" viewBox="0 0 24 24"><path d="M12 2.5 4 5.5v6c0 4.7 3.4 9 8 10 4.6-1 8-5.3 8-10v-6l-8-3z" /><path d="m8.5 12 2.5 2.5 4.5-5" /></svg></span>
        <span><b>{{ ar ? 'الحماية مفعّلة' : 'Protection is on' }}</b><br />
          <span class="small muted">{{ ar ? 'تُفحص الروابط قبل فتحها' : 'Links are checked before they open' }}</span></span>
      </div>
      <div class="card">
        <b>{{ ar ? 'افحص رابطًا' : 'Check a link' }}</b>
        <div class="input" :class="{ focus: caret }">
          <svg class="i" viewBox="0 0 24 24"><path d="M10 14a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1M14 10a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1" /></svg>
          <span v-if="typed" class="mono typed">{{ typed }}<i v-if="caret" class="caret" /></span>
          <span v-else class="muted">{{ ar ? 'الرابط أو عنوان الموقع' : 'Link or website address' }}<i v-if="caret" class="caret" /></span>
        </div>
        <div class="btn" :class="{ pressed }">
          <svg class="i" viewBox="0 0 24 24"><path d="M10.5 4a6.5 6.5 0 1 1 0 13 6.5 6.5 0 0 1 0-13zM15.5 15.5 21 21" /></svg>
          {{ ar ? 'افحص هذا الرابط' : 'Check this link' }}<slot />
        </div>
      </div>
      <div class="stats">
        <div class="card"><b class="r">18</b><span class="small muted">{{ ar ? 'احتيال محظور هنا' : 'scams blocked here' }}</span></div>
        <div class="card"><b>1,284</b><span class="small muted">{{ ar ? 'مواقع أكدتها الشرطة' : 'police-confirmed sites' }}</span></div>
      </div>
    </div>
    <div class="tabs">
      <span class="on"><svg class="i" viewBox="0 0 24 24"><path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" /></svg>{{ ar ? 'الرئيسية' : 'Home' }}</span>
      <span><svg class="i" viewBox="0 0 24 24"><path d="M5 21V4h9l1 2h4v9h-6l-1-2H5" /></svg>{{ ar ? 'بلاغاتي' : 'Reports' }}</span>
      <span><svg class="i" viewBox="0 0 24 24"><path d="M12 12 19 5M21 12a9 9 0 1 1-9-9M17 12a5 5 0 1 1-5-5" /></svg>{{ ar ? 'الرادار' : 'Radar' }}</span>
    </div>
  </div>
</template>

<style scoped>
.home { position: absolute; inset: 0; }
.top { background: linear-gradient(160deg, var(--hero), var(--hero-2)); color: #fff; padding-bottom: 46px; border-radius: 0 0 26px 26px; }
.ph.light .top { --hero: #151925; --hero-2: #232a3b; }
.brandrow { display: flex; align-items: center; gap: 12px; padding: 12px 20px 0; line-height: 1.2; }
.brandrow b { font-size: 21px; }
.sub { font-size: 13px; color: #b9c0cc; }
.mark { display: grid; place-items: center; width: 46px; height: 46px; border-radius: 50%; background: rgb(255 255 255 / 0.1); }
.mark svg { width: 26px; height: 26px; fill: #d7b14e; stroke: #151925; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.stack { display: grid; gap: 12px; margin-top: -32px; }
.on { display: flex; gap: 12px; align-items: center; line-height: 1.3; }
.ok { display: grid; place-items: center; width: 42px; height: 42px; border-radius: 50%; background: var(--allow-soft); color: var(--allow); flex: none; }
.card > b { display: block; font-size: 16.5px; margin-bottom: 10px; }
.input { display: flex; align-items: center; gap: 10px; height: 50px; padding: 0 14px; border: 1px solid var(--line); border-radius: 14px; margin-bottom: 10px; color: var(--muted);
  transition: border-color 150ms; }
.input.focus { border-color: var(--accent); border-width: 2px; }
.typed { color: var(--text); font-size: 14.5px; }
.caret { display: inline-block; width: 2px; height: 18px; margin-inline-start: 1px; vertical-align: -3px; background: var(--accent); animation: blink 0.9s steps(1) infinite; }
@keyframes blink { 50% { opacity: 0; } }
.btn { position: relative; transition: transform 120ms; }
.btn.pressed { transform: scale(0.97); filter: brightness(1.1); }
.stats { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.stats .card { display: grid; gap: 2px; }
.stats b { font-size: 26px; font-variant-numeric: tabular-nums; }
.stats b.r { color: var(--block); }
</style>
