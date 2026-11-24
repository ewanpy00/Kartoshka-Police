<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { adaptRefused } from '../adapt'
import { ApiError, apiJson, download, errorText, postJson } from '../api'
import { defang } from '../defang'
import { formatTime, t } from '../i18n'
import { officerName } from '../session'
import type { CaseSummary, Pack } from '../types'

const confirmed = ref<string[]>([])
const picked = reactive(new Set<string>())
const packs = ref<Pack[]>([])
const built = ref<{ packs: Pack[]; without_recipient: string[]; refused?: { domain: string; reason: string }[] } | null>(null)
const refused = ref<{ domain: string; reason: string }[]>([])
const error = ref('')
const copiedId = ref('')

async function loadPacks() {
  packs.value = (await apiJson<{ packs: Pack[] }>('/v1/admin/takedowns')).packs
}

async function load() {
  try {
    const queue = await apiJson<{ cases: CaseSummary[] }>('/v1/admin/queue?state=all')
    confirmed.value = queue.cases.filter((c) => c.state === 'confirmed').map((c) => c.domain)
    await loadPacks()
  } catch (e) {
    error.value = t('failed', { error: errorText(e) })
  }
}

function toggle(domain: string, on: boolean) {
  if (on) picked.add(domain)
  else picked.delete(domain)
}

async function build() {
  built.value = null
  refused.value = []
  error.value = ''
  try {
    built.value = await postJson('/v1/admin/takedowns', { domains: [...picked], generated_by: officerName() })
    refused.value = built.value?.refused ?? []
    picked.clear()
    await loadPacks()
  } catch (e) {
    if (e instanceof ApiError && e.status === 409) {
      refused.value = adaptRefused(e.body)
    } else {
      error.value = t('failed', { error: errorText(e) })
    }
  }
}

async function markSent(id: string) {
  try {
    await postJson(`/v1/admin/takedowns/${id}/sent`, { sent_by: officerName() })
    await loadPacks()
  } catch (e) {
    error.value = t('failed', { error: errorText(e) })
  }
}

async function copy(pack: Pack) {
  try {
    await navigator.clipboard.writeText(pack.recipient)
    copiedId.value = pack.id
  } catch (e) {
    error.value = t('failed', { error: errorText(e) })
  }
}

async function save(pack: Pack) {
  try {
    await download(`/v1/admin/takedowns/${pack.id}/pack.zip`, `${pack.id}.zip`)
  } catch (e) {
    error.value = t('failed', { error: errorText(e) })
  }
}

onMounted(load)
</script>

<template>
  <div class="page-head">
    <h1>{{ t('navTakedowns') }}</h1>
  </div>
  <p class="notice">{{ t('takedownNotice') }}</p>
  <p v-if="error" class="error" role="alert">{{ error }}</p>

  <div class="card">
    <div class="card-section">
      <h2 class="section-title">{{ t('pickConfirmed') }}</h2>
    </div>
    <p v-if="!confirmed.length" class="empty">{{ t('noConfirmed') }}</p>
    <table v-else class="table">
      <thead>
        <tr>
          <th class="sel"></th>
          <th>{{ t('domain') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="domain in confirmed" :key="domain">
          <td class="sel">
            <input
              type="checkbox"
              :id="`pick-${domain}`"
              :checked="picked.has(domain)"
              @change="toggle(domain, ($event.target as HTMLInputElement).checked)"
            />
          </td>
          <td :data-label="t('domain')">
            <label :for="`pick-${domain}`" class="mono">{{ defang(domain) }}</label>
          </td>
        </tr>
      </tbody>
    </table>
    <div class="card-section">
      <button class="btn primary" :disabled="!picked.size" @click="build">{{ t('buildPacks') }}</button>
    </div>

    <div v-if="refused.length" class="card-section error" role="alert">
      <strong>{{ t('refused') }}</strong>
      <ul>
        <li v-for="item in refused" :key="item.domain">
          <span class="mono">{{ defang(item.domain) }}</span>: {{ item.reason }}
        </li>
      </ul>
    </div>
    <div v-if="built?.without_recipient.length" class="card-section notice">
      {{ t('withoutRecipient') }}: <span class="mono">{{ built.without_recipient.map(defang).join(', ') }}</span>
    </div>
  </div>

  <div class="card packs">
    <div class="card-section">
      <h2 class="section-title">{{ t('navTakedowns') }}</h2>
    </div>
    <p v-if="!packs.length" class="empty">{{ t('noPacks') }}</p>
    <div v-for="pack in packs" :key="pack.id" class="card-section pack-item">
      <p>
        <strong>{{ pack.recipient_kind }}</strong>
        <span class="muted"> · {{ t('generatedAt') }}: {{ formatTime(pack.generated_at) }}</span>
      </p>
      <p>
        {{ t('recipient') }}: <span class="mono">{{ pack.recipient }}</span>
        <button class="btn ghost" @click="copy(pack)">{{ copiedId === pack.id ? t('copied') : t('copy') }}</button>
      </p>
      <p class="mono">{{ pack.domains.map(defang).join(', ') }}</p>
      <div class="hash">{{ t('packHash') }}: {{ pack.sha256 }}</div>
      <p v-if="pack.sent_at">
        <span class="status-chip confirmed">{{ t('sentBy', { who: pack.sent_by ?? '', when: formatTime(pack.sent_at) }) }}</span>
      </p>
      <p v-else>
        <span class="status-chip rejected">{{ t('notSent') }}</span>
      </p>
      <div class="row-actions">
        <button class="btn" @click="save(pack)">{{ t('downloadPack') }}</button>
        <button v-if="!pack.sent_at" class="btn" @click="markSent(pack.id)">{{ t('markSent') }}</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.card {
  margin-block-end: 16px;
}
.sel {
  inline-size: 40px;
}
.pack-item p {
  margin-block: 0 8px;
}
.row-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-block-start: 8px;
}
</style>
