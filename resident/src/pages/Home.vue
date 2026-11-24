<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { radar, type Radar } from '../api'
import { lang, tr } from '../i18n'

const router = useRouter()
const input = ref('')
const data = ref<Radar | null>(null)

onMounted(async () => {
  try {
    data.value = await radar()
  } catch {
    data.value = null
  }
})

function submit() {
  const url = input.value.trim()
  if (!url) return
  router.push({ name: 'check', query: { url: /^https?:\/\//i.test(url) ? url : `https://${url}` } })
}
</script>

<template>
  <main>
    <form class="card stack" @submit.prevent="submit">
      <h1>{{ tr('Got a link in a message?', 'وصلك رابط في رسالة؟') }}</h1>
      <p class="muted">{{ tr('Check it here before you open it. We look it up and open it in a sandbox, not on your phone.', 'افحصه هنا قبل أن تفتحه. نتحقق منه ونفتحه في بيئة معزولة، وليس على هاتفك.') }}</p>
      <input v-model="input" dir="ltr" inputmode="url" autocomplete="off" placeholder="https://…" />
      <button class="primary">{{ tr('Check a link', 'افحص رابطًا') }}</button>
      <RouterLink to="/sms" class="button">{{ tr('Paste a whole SMS', 'الصق رسالة كاملة') }}</RouterLink>
    </form>

    <RouterLink to="/radar" class="card radar">
      <h2>{{ tr('Scam radar', 'رادار الاحتيال') }}</h2>
      <template v-if="data && data.totals.active">
        <p v-for="h in data.headlines.slice(0, 2)" :key="h.category"><strong>{{ lang === 'ar' ? h.ar : h.en }}</strong></p>
        <p class="muted small">{{ tr(`New today: ${data.totals.new_today}`, `جديد اليوم: ${data.totals.new_today}`) }} ·
          {{ tr(`yesterday: ${data.totals.yesterday}`, `أمس: ${data.totals.yesterday}`) }}</p>
      </template>
      <p v-else class="muted">{{ tr('No active scam sites right now.', 'لا توجد مواقع احتيال نشطة الآن.') }}</p>
    </RouterLink>
  </main>
</template>

<style scoped>
.radar { display: block; color: inherit; text-decoration: none; }
</style>
