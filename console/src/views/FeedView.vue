<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { adaptEvent } from '../adapt'
import { apiJson, apiToken, errorText } from '../api'
import { defang } from '../defang'
import { formatTime, t } from '../i18n'
import type { FeedRow } from '../types'

const MAX_ROWS = 200
const RECONNECT_MS = 3000
const UNAUTHORISED = 4401

const rows = ref<FeedRow[]>([])
const connected = ref(false)
const unauthorised = ref(false)
const error = ref('')
let socket: WebSocket | null = null
let retry: ReturnType<typeof setTimeout> | undefined
let closed = false

function push(row: FeedRow) {
  if (rows.value.some((existing) => existing.key === row.key)) return
  rows.value = [row, ...rows.value].slice(0, MAX_ROWS)
}

function connect() {
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws'
  socket = new WebSocket(`${scheme}://${location.host}/api/v1/events`)
  socket.onopen = () => {
    socket?.send(JSON.stringify({ type: 'auth', token: apiToken() }))
  }
  socket.onmessage = (message) => {
    let event: { type: string; at?: string; data?: unknown }
    try {
      event = JSON.parse(message.data)
    } catch {
      return
    }
    if (event.type === 'hello') {
      connected.value = true
      return
    }
    const row = adaptEvent(event)
    if (row) push(row)
  }
  socket.onclose = (event) => {
    connected.value = false
    if (event.code === UNAUTHORISED) unauthorised.value = true
    else if (!closed) retry = setTimeout(connect, RECONNECT_MS)
  }
}

onMounted(async () => {
  connect()
  try {
    const feed = await apiJson<{ rows: FeedRow[] }>('/v1/admin/hunter/feed')
    const known = new Set(rows.value.map((row) => row.key))
    const history = feed.rows.filter((row) => !known.has(row.key))
    rows.value = [...rows.value, ...history]
  } catch (e) {
    error.value = t('failed', { error: errorText(e) })
  }
})

onBeforeUnmount(() => {
  closed = true
  clearTimeout(retry)
  socket?.close()
})
</script>

<template>
  <div>
    <div class="page-head">
      <h1>{{ t('navFeed') }}</h1>
      <div class="actions">
        <span :class="['status-chip', connected ? 'confirmed' : 'rejected']">{{ connected ? t('connected') : unauthorised ? t('notAuthorised') : t('disconnected') }}</span>
      </div>
    </div>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div class="card">
      <p v-if="!rows.length" class="empty">{{ t('feedEmpty') }}</p>
      <table v-else class="table">
        <thead>
          <tr>
            <th>{{ t('time') }}</th>
            <th>{{ t('event') }}</th>
            <th>{{ t('domain') }}</th>
            <th>{{ t('brand') }}</th>
            <th>{{ t('verdict') }}</th>
            <th>{{ t('score') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.key">
            <td :data-label="t('time')">{{ formatTime(row.at) }}</td>
            <td :data-label="t('event')">{{ t(`event.${row.type}`) }}</td>
            <td :data-label="t('domain')" class="mono">{{ row.domain ? defang(row.domain) : t('unknown') }}</td>
            <td :data-label="t('brand')">{{ row.brand ?? '' }}</td>
            <td :data-label="t('verdict')">{{ row.verdict ?? '' }}</td>
            <td :data-label="t('score')">
              <span v-if="row.score !== null" :class="['q-score', row.score >= 70 ? 'high' : row.score >= 30 ? 'mid' : 'low']">{{ row.score }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
