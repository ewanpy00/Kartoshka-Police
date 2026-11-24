<script setup lang="ts">
// Mock sign-in (ARCHITECTURE.md section 5): a plain, clearly labelled demo button. It does not imitate the
// UAE PASS page and calls no UAE PASS endpoint.
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { lang, t, toggleLang } from '../i18n'
import { signIn } from '../session'

const router = useRouter()
const route = useRoute()
const name = ref('Demo Officer')

function go() {
  signIn(name.value.trim() || 'Demo Officer')
  const next = typeof route.query.next === 'string' && route.query.next.startsWith('/') ? route.query.next : '/queue'
  router.replace(next)
}
</script>

<template>
  <main class="login">
    <div class="card">
      <div class="row"><h1>{{ t('login.title') }}</h1><span class="spacer" />
        <button class="ghost" @click="toggleLang">{{ lang === 'ar' ? 'English' : 'العربية' }}</button></div>
      <p>{{ t('login.lead') }}</p>
      <label class="small muted">{{ t('login.name') }}</label>
      <input v-model="name" maxlength="80" @keyup.enter="go" />
      <button class="primary big" @click="go">{{ t('login.button') }}</button>
      <p class="small muted">{{ t('login.note') }}</p>
    </div>
  </main>
</template>

<style scoped>
.login { max-width: 26rem; margin: 10vh auto; padding: 0 1rem; }
.login input { width: 100%; margin: 0.25rem 0 1rem; }
.big { width: 100%; justify-content: center; padding: 0.7rem; }
</style>
