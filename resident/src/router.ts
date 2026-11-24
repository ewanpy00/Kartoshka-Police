import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: () => import('./pages/Home.vue') },
    { path: '/check', name: 'check', component: () => import('./pages/Check.vue') },
    { path: '/sms', name: 'sms', component: () => import('./pages/Sms.vue') },
    { path: '/reports', name: 'reports', component: () => import('./pages/Reports.vue') },
    { path: '/radar', name: 'radar', component: () => import('./pages/Radar.vue') },
    { path: '/:rest(.*)*', redirect: '/' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})
