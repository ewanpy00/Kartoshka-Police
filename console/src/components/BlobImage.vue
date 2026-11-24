<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { fetchBlob } from '../api'
import { t } from '../i18n'

const props = defineProps<{ path: string }>()
const url = ref<string | null>(null)
const failed = ref(false)
let unmounted = false

function release() {
  if (url.value) URL.revokeObjectURL(url.value)
  url.value = null
}

watch(
  () => props.path,
  async (path) => {
    release()
    failed.value = false
    try {
      const next = URL.createObjectURL(await fetchBlob(path))
      if (path === props.path && !unmounted) url.value = next
      else URL.revokeObjectURL(next)
    } catch {
      failed.value = true
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  unmounted = true
  release()
})
</script>

<template>
  <img v-if="url" class="screenshot" :src="url" :alt="t('screenshot')" />
  <p v-else-if="failed" class="muted">{{ t('noScreenshot') }}</p>
  <p v-else class="muted">{{ t('loading') }}</p>
</template>
