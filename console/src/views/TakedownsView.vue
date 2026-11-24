<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ApiError, apiJson, download, postJson } from '../api'
import { defang } from '../defang'
import { formatTime, t } from '../i18n'
import { officerName } from '../session'
import type { CaseSummary, Pack } from '../types'

const confirmed = ref<string[]>([])
const picked = reactive(new Set<string>())
const packs = ref<Pack[]>([])
const built = ref<{ packs: Pack[]; without_recipient: string[] } | null>(null)
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
    error.value = t('failed', { error: String(e) })
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
    picked.clear()
    await loadPacks()
  } catch (e) {
    if (e instanceof ApiError && e.status === 409) {
      refused.value = (e.body as { refused: { domain: string; reason: string }[] }).refused
    } else {
      error.value = t('failed', { error: String(e) })
    }
  }
}

async function markSent(id: string) {
  try {
    await postJson(`/v1/admin/takedowns/${id}/sent`, { sent_by: officerName() })
    await loadPacks()
  } catch (e) {
    error.value = t('failed', { error: String(e) })
  }
}

async function copy(pack: Pack) {
  await navigator.clipboard.writeText(pack.recipient)
  copiedId.value = pack.id
}

onMounted(load)
</script>

<template>
  <section class="panel">
    <h1>{{ t('takedowns') }}</h1>
    <p class="notice">{{ t('takedownNotice') }}</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <h2>{{ t('pickConfirmed') }}</h2>
    <p v-if="!confirmed.length" class="muted">{{ t('noConfirmed') }}</p>
    <ul v-else class="plain">
      <li v-for="domain in confirmed" :key="domain">
        <label class="check">
          <input type="checkbox" :checked="picked.has(domain)" @change="toggle(domain, ($event.target as HTMLInputElement).checked)" />
          <span class="mono">{{ defang(domain) }}</span>
        </label>
      </li>
    </ul>
    <div class="actions">
      <button :disabled="!picked.size" @click="build">{{ t('buildPacks') }}</button>
    </div>

    <div v-if="refused.length" class="error" role="alert">
      <strong>{{ t('refused') }}</strong>
      <ul>
        <li v-for="item in refused" :key="item.domain">
          <span class="mono">{{ defang(item.domain) }}</span>: {{ item.reason }}
        </li>
      </ul>
    </div>
    <div v-if="built?.without_recipient.length" class="notice">
      {{ t('withoutRecipient') }}: <span class="mono">{{ built.without_recipient.map(defang).join(', ') }}</span>
    </div>
  </section>

  <section class="panel">
    <h2>{{ t('takedowns') }}</h2>
    <p v-if="!packs.length" class="muted">{{ t('noPacks') }}</p>
    <article v-for="pack in packs" :key="pack.id" class="pack">
      <p>
        <strong>{{ pack.recipient_kind }}</strong>
        · {{ t('generatedAt') }}: {{ formatTime(pack.generated_at) }}
      </p>
      <p>
        {{ t('recipient') }}: <span class="mono">{{ pack.recipient }}</span>
        <button class="secondary small" @click="copy(pack)">{{ copiedId === pack.id ? t('copied') : t('copy') }}</button>
      </p>
      <p class="mono">{{ pack.domains.map(defang).join(', ') }}</p>
      <p class="mono muted">{{ t('packHash') }}: {{ pack.sha256 }}</p>
      <p v-if="pack.sent_at">{{ t('sentBy', { who: pack.sent_by ?? '', when: formatTime(pack.sent_at) }) }}</p>
      <p v-else class="muted">{{ t('notSent') }}</p>
      <div class="actions">
        <button class="secondary" @click="download(`/v1/admin/takedowns/${pack.id}/pack.zip`, `${pack.id}.zip`)">
          {{ t('downloadPack') }}
        </button>
        <button v-if="!pack.sent_at" @click="markSent(pack.id)">{{ t('markSent') }}</button>
      </div>
    </article>
  </section>
</template>
