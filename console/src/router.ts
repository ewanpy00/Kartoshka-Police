import { createRouter, createWebHistory } from 'vue-router'
import QueueView from './views/QueueView.vue'
import CampaignsView from './views/CampaignsView.vue'
import CampaignView from './views/CampaignView.vue'
import TakedownsView from './views/TakedownsView.vue'
import HelplinesView from './views/HelplinesView.vue'
import FeedView from './views/FeedView.vue'
import ChainView from './views/ChainView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/queue' },
    { path: '/queue/:domain?', component: QueueView },
    { path: '/campaigns', component: CampaignsView },
    { path: '/campaigns/:id', component: CampaignView, props: true },
    { path: '/takedowns', component: TakedownsView },
    { path: '/helplines', component: HelplinesView },
    { path: '/feed', component: FeedView },
    { path: '/chain', component: ChainView },
  ],
})
