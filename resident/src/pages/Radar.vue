<script setup lang="ts">
// Scam radar: what is active now in the UAE, by brand. Domains appear only when officer-confirmed, defanged
// and never as links, so the radar never advertises a live scam.
import { onMounted, onUnmounted, ref } from 'vue'
import { radar, type Radar } from '../api'
import { lang, tr } from '../i18n'

const data = ref<Radar | null>(null)
const error = ref('')
let timer: number | undefined

async function load() {
  try {
    data.value = await radar()
    error.value = ''
  } catch (e) {
    error.value = (e as Error).message
  }
}

onMounted(() => {
  load()
  timer = window.setInterval(load, 60_000)
})
onUnmounted(() => window.clearInterval(timer))
</script>

<template>
  <main>
    <h1>{{ tr('Scam radar', 'رادار الاحتيال') }}</h1>
    <p v-if="error" class="error">{{ error }}</p>
    <template v-if="data">
      <section class="card">
        <p v-for="h in data.headlines" :key="h.category"><strong>{{ lang === 'ar' ? h.ar : h.en }}</strong></p>
        <p class="muted small">{{ tr(`New today: ${data.totals.new_today} · yesterday: ${data.totals.yesterday} · confirmed by police: ${data.totals.confirmed}`,
                                     `جديد اليوم: ${data.totals.new_today} · أمس: ${data.totals.yesterday} · أكدتها الشرطة: ${data.totals.confirmed}`) }}</p>
        <p v-if="!data.totals.active" class="muted">{{ tr('No active scam sites right now.', 'لا توجد مواقع احتيال نشطة الآن.') }}</p>
      </section>
      <section v-for="b in data.brands" :key="b.brand_id" class="card stack">
        <div class="head"><h2>{{ lang === 'ar' ? b.brand_ar : b.brand }}</h2>
          <span class="badge block">{{ b.active }}</span></div>
        <p class="small muted">{{ tr(`${b.confirmed} confirmed by police, ${b.suspected} suspected · new today ${b.new_today}`,
                                     `${b.confirmed} أكدتها الشرطة، ${b.suspected} مشتبه بها · جديد اليوم ${b.new_today}`) }}</p>
        <p v-if="b.tip_en">💡 {{ lang === 'ar' ? b.tip_ar : b.tip_en }}</p>
        <p v-if="b.examples.length" class="small">{{ tr('Fake sites', 'مواقع مزيفة') }}: <span v-for="d in b.examples" :key="d" class="domain">{{ d }} </span></p>
        <a v-if="b.safe_action" class="button safe" :href="b.safe_action.url" rel="noopener">{{ lang === 'ar' ? b.safe_action.label_ar : b.safe_action.label_en }}</a>
      </section>
    </template>
  </main>
</template>

<style scoped>
.head { display: flex; justify-content: space-between; align-items: center; }
</style>
