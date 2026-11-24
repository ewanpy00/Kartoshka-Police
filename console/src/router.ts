import { createRouter, createWebHistory } from 'vue-router'
import { session } from './session'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('./pages/Login.vue'), meta: { open: true } },
    { path: '/', redirect: '/queue' },
    { path: '/queue', name: 'queue', component: () => import('./pages/Queue.vue') },
    { path: '/live', name: 'live', component: () => import('./pages/Live.vue'), meta: { bare: true } },
    { path: '/case/:domain', name: 'case', component: () => import('./pages/Case.vue'), props: true },
    { path: '/hunter', name: 'hunter', component: () => import('./pages/Hunter.vue') },
    { path: '/campaigns', name: 'campaigns', component: () => import('./pages/Campaigns.vue') },
    { path: '/campaigns/:id', name: 'campaign', component: () => import('./pages/Campaign.vue'), props: true },
    { path: '/takedowns', name: 'takedowns', component: () => import('./pages/Takedowns.vue') },
    { path: '/impact', name: 'impact', component: () => import('./pages/Impact.vue') },
    { path: '/quality', name: 'quality', component: () => import('./pages/Quality.vue') },
    { path: '/health', name: 'health', component: () => import('./pages/Health.vue') },
    { path: '/:rest(.*)*', redirect: '/queue' },
  ],
})

router.beforeEach((to) => {
  if (!to.meta.open && !session.value) return { name: 'login', query: { next: to.fullPath } }
  return true
})
