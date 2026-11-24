import { createRouter, createWebHistory } from 'vue-router'
import QueueView from './views/QueueView.vue'
import CampaignsView from './views/CampaignsView.vue'
import CampaignView from './views/CampaignView.vue'
import TakedownsView from './views/TakedownsView.vue'
import HelplinesView from './views/HelplinesView.vue'
import FeedView from './views/FeedView.vue'
import ChainView from './views/ChainView.vue'
import AuditView from './views/AuditView.vue'
import ImpactView from './views/ImpactView.vue'
import QualityView from './views/QualityView.vue'
import HealthView from './views/HealthView.vue'

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/queue' },
    { path: '/queue/:domain?', component: QueueView },
    { path: '/campaigns', component: CampaignsView },
    { path: '/campaigns/:id', component: CampaignView, props: true },
    { path: '/takedowns', component: TakedownsView },
    { path: '/helplines', component: HelplinesView },
    { path: '/feed', component: FeedView },
    { path: '/chain', component: ChainView },
    { path: '/audit', component: AuditView },
    { path: '/impact', component: ImpactView },
    { path: '/quality', component: QualityView },
    { path: '/health', component: HealthView },
  ],
})
