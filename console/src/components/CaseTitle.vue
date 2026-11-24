<script setup lang="ts">
import { defang } from '../defang'
import { t } from '../i18n'

defineProps<{ domain: string; title: string | null; url: string }>()
</script>

<template>
  <header class="case-title">
    <h2>{{ title ?? t('unknown') }}</h2>
    <p class="mono">{{ defang(domain) }}</p>
    <p class="mono muted">{{ defang(url) }}</p>
  </header>
</template>
