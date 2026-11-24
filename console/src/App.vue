<script setup lang="ts">
import { locale, setLocale, t } from './i18n'
import { officer, signIn, signOut } from './session'
</script>

<template>
  <div class="banner" role="status">{{ t('demoBanner') }}</div>
  <header class="topbar">
    <strong class="brand">{{ t('appName') }}</strong>
    <nav v-if="officer">
      <RouterLink to="/queue">{{ t('navQueue') }}</RouterLink>
      <RouterLink to="/campaigns">{{ t('navCampaigns') }}</RouterLink>
      <RouterLink to="/takedowns">{{ t('navTakedowns') }}</RouterLink>
      <RouterLink to="/helplines">{{ t('navHelplines') }}</RouterLink>
      <RouterLink to="/feed">{{ t('navFeed') }}</RouterLink>
      <RouterLink to="/chain">{{ t('navChain') }}</RouterLink>
    </nav>
    <div class="topbar-end">
      <button class="secondary" @click="setLocale(locale === 'en' ? 'ar' : 'en')">{{ t('language') }}</button>
      <button v-if="officer" class="secondary" @click="signOut">{{ t('signOut') }}</button>
    </div>
  </header>
  <main>
    <RouterView v-if="officer" />
    <section v-else class="panel signin">
      <h1>{{ t('signInTitle') }}</h1>
      <button @click="signIn">{{ t('signInButton') }}</button>
    </section>
  </main>
</template>
