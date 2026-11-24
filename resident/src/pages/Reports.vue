<script setup lang="ts">
// My reports: the timeline of each report this device sent (Sent → Analysed → In review → Confirmed or
// Rejected → Taken down → Impact). Only this device knows the report ids and tokens.
import { onMounted, ref } from 'vue'
import { reportStatus, type ReportStatus } from '../api'
import { lang, tr } from '../i18n'
import { defang, forgetReport, hostOf, savedReports, type SavedReport } from '../store'

interface Row { saved: SavedReport; status: ReportStatus | null; missing: boolean }
const rows = ref<Row[]>([])

async function load() {
  rows.value = savedReports().map((saved) => ({ saved, status: null, missing: false }))
  await Promise.all(rows.value.map(async (row) => {
    try {
      row.status = await reportStatus(row.saved.id, row.saved.token)
    } catch {
      row.missing = true
    }
  }))
}

function forget(id: string) {
  forgetReport(id)
  rows.value = rows.value.filter((r) => r.saved.id !== id)
}

onMounted(load)
</script>

<template>
  <main>
    <div class="row-head"><h1>{{ tr('My reports', 'بلاغاتي') }}</h1><button @click="load">{{ tr('Refresh', 'تحديث') }}</button></div>
    <p v-if="!rows.length" class="card muted">{{ tr('You have not reported any link from this device yet.', 'لم تُبلغ عن أي رابط من هذا الجهاز بعد.') }}</p>
    <section v-for="row in rows" :key="row.saved.id" class="card">
      <p class="domain"><strong>{{ defang(hostOf(row.saved.url)) }}</strong></p>
      <p class="small muted">{{ new Date(row.saved.at).toLocaleString(lang === 'ar' ? 'ar-AE' : 'en-AE') }}</p>
      <p v-if="row.missing" class="muted">{{ tr('This report could not be loaded.', 'تعذّر تحميل هذا البلاغ.') }}
        <button class="small" @click="forget(row.saved.id)">{{ tr('Remove', 'إزالة') }}</button></p>
      <ol v-if="row.status" class="timeline">
        <li v-for="step in row.status.steps" :key="step.id" :class="{ done: step.done }">
          <span>{{ lang === 'ar' ? step.ar : step.en }}</span>
          <span v-if="step.at" class="small muted">{{ new Date(step.at).toLocaleString(lang === 'ar' ? 'ar-AE' : 'en-AE') }}</span>
        </li>
      </ol>
    </section>
  </main>
</template>

<style scoped>
.row-head { display: flex; align-items: center; justify-content: space-between; }
.timeline { list-style: none; padding: 0; margin: 0.5rem 0 0; }
.timeline li { position: relative; padding-inline-start: 1.6rem; padding-bottom: 0.6rem; display: grid; color: var(--muted); }
.timeline li::before { content: ''; position: absolute; inset-inline-start: 0.2rem; top: 0.35rem; width: 0.7rem; height: 0.7rem; border-radius: 50%;
  border: 2px solid #c2c8d0; background: var(--surface); }
.timeline li.done { color: var(--text); }
.timeline li.done::before { background: var(--accent); border-color: var(--accent); }
</style>
