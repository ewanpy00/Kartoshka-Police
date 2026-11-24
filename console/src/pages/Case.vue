<script setup lang="ts">
import CaseCard from '../components/CaseCard.vue'

defineProps<{ domain: string }>()
</script>

<template>
  <main class="page">
    <RouterLink :to="{ name: 'queue' }" class="small">← Queue</RouterLink>
    <CaseCard :domain="domain" />
  </main>
</template>
