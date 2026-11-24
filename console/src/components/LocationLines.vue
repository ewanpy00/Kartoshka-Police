<script setup lang="ts">
import { t } from '../i18n'
import type { Location } from '../types'

defineProps<{ location: Location }>()
</script>

<template>
  <ul class="lines">
    <li>
      {{ t('hostedIn') }}:
      {{ location.behind_proxy ? t('behindProxy') : (location.hosted_in ?? t('unknown')) }}
    </li>
    <li>{{ t('registeredThrough') }}: {{ location.registered_through ?? t('unknown') }}</li>
    <li>{{ t('networkOwner') }}: {{ location.network_owner ?? t('unknown') }}</li>
  </ul>
</template>
