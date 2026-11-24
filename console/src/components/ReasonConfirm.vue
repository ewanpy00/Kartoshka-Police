<script setup lang="ts">
import { ref, watch } from 'vue'
import { t } from '../i18n'

defineProps<{ title: string; actionLabel: string; busy: boolean }>()
const emit = defineEmits<{ confirm: [reason: string]; cancel: [] }>()

const reason = ref('')
const armed = ref(false)
const missing = ref(false)

watch(reason, () => {
  armed.value = false
  missing.value = false
})

function activate(): void {
  const trimmed = reason.value.trim()
  if (!trimmed) {
    missing.value = true
    return
  }
  if (!armed.value) {
    armed.value = true
    return
  }
  armed.value = false
  emit('confirm', trimmed)
}

function cancel(): void {
  armed.value = false
  emit('cancel')
}
</script>

<template>
  <form class="reason-confirm" @submit.prevent @keydown.esc.prevent="cancel">
    <p class="reason-title">{{ title }}</p>
    <label class="reason-field">
      <span>{{ t('reasonLabel') }}</span>
      <input v-model="reason" type="text" maxlength="500" required :disabled="busy" @keydown.enter.prevent="activate" />
    </label>
    <p v-if="missing" class="error" role="alert">{{ t('reasonRequired') }}</p>
    <div class="actions">
      <button type="button" :class="['btn', 'danger', { armed }]" :disabled="busy" @click="activate">
        <template v-if="armed">{{ t('confirmArmed') }}</template>
        <template v-else>{{ actionLabel }}</template>
      </button>
      <button type="button" class="btn ghost" :disabled="busy" @click="cancel">{{ t('cancel') }}</button>
    </div>
  </form>
</template>

<style scoped>
.reason-confirm {
  display: grid;
  gap: var(--space-2, 8px);
  margin-block: var(--space-2, 8px);
}
.reason-title {
  margin: 0;
  font-weight: 600;
  overflow-wrap: anywhere;
}
.reason-field {
  display: grid;
  gap: 4px;
}
</style>
