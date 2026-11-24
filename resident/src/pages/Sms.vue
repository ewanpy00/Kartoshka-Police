<script setup lang="ts">
// Paste an SMS: every link in it is checked, and the text is read for scam stories.
import { ref } from 'vue'
import { pasteSms, type SmsResult } from '../api'
import { lang, tr } from '../i18n'
import { defang, hostOf } from '../store'

const text = ref('')
const result = ref<SmsResult | null>(null)
const error = ref('')
const busy = ref(false)

async function submit() {
  if (!text.value.trim()) return
  busy.value = true
  error.value = ''
  try {
    result.value = await pasteSms(text.value)
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}

const LABEL = { allow: ['No warning signs', 'لا علامات خطر'], warn: ['Suspicious', 'مشبوه'], block: ['Suspected scam', 'احتيال مشتبه به'], pending: ['Checking', 'قيد الفحص'] } as const
</script>

<template>
  <main>
    <form class="card stack" @submit.prevent="submit">
      <h1>{{ tr('Paste an SMS', 'الصق رسالة نصية') }}</h1>
      <textarea v-model="text" maxlength="4000" :placeholder="tr('Paste the whole message here', 'الصق الرسالة كاملة هنا')" />
      <button class="primary" :disabled="busy">{{ tr('Check the message', 'افحص الرسالة') }}</button>
    </form>
    <p v-if="error" class="error">{{ error }}</p>
    <template v-if="result">
      <section v-if="result.text.category" class="card">
        <h2>{{ tr('What the message says', 'ماذا تقول الرسالة') }}</h2>
        <p>{{ tr(`It reads like a ${result.text.category_en} scam${result.text.urgent ? ' and pushes you to hurry' : ''}.`,
                 `تبدو كرسالة احتيال من نوع ${result.text.category_ar}${result.text.urgent ? ' وتستعجلك' : ''}.`) }}</p>
      </section>
      <p v-if="!result.found_links" class="card muted">{{ tr('No links found in this message.', 'لم نجد روابط في هذه الرسالة.') }}</p>
      <RouterLink v-for="link in result.links" :key="link.check_id" class="card item" :to="{ name: 'check', query: { url: link.url } }">
        <span class="badge" :class="link.verdict">{{ tr(LABEL[link.verdict][0], LABEL[link.verdict][1]) }}</span>
        <span class="domain">{{ defang(hostOf(link.url)) }}</span>
        <span class="small muted">{{ link.reasons[0] ? (lang === 'ar' ? link.reasons[0].ar : link.reasons[0].en) : '' }}</span>
      </RouterLink>
    </template>
  </main>
</template>

<style scoped>
.item { display: grid; gap: 0.3rem; color: inherit; text-decoration: none; }
.item .badge { justify-self: start; }
</style>
