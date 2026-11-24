<script setup lang="ts">
// Attacker-controlled names are shown as defanged text, never as links (docs/admin-dashboard.md decision 6).
defineProps<{ display: string | null | undefined }>()
</script>

<template>
  <span class="domain" :title="display ?? ''">{{ display ?? '—' }}</span>
</template>
