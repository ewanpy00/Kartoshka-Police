import type { Key } from './i18n'

export interface NavItem {
  to: string
  label: Key
  icon: string
  count?: 'awaiting'
}

export interface NavGroup {
  label: Key
  items: NavItem[]
}

export const navGroups: NavGroup[] = [
  {
    label: 'navGroupReview',
    items: [
      { to: '/queue', label: 'navQueue', icon: 'M2 3.5h12M2 8h12M2 12.5h8', count: 'awaiting' },
      {
        to: '/campaigns',
        label: 'navCampaigns',
        icon: 'M5.5 5l5 0M5 5.5l2 5M11 6.5l-2 4M2.2 4a1.8 1.8 0 103.6 0 1.8 1.8 0 10-3.6 0M10.2 5a1.8 1.8 0 103.6 0 1.8 1.8 0 10-3.6 0M6.2 12a1.8 1.8 0 103.6 0 1.8 1.8 0 10-3.6 0',
      },
      { to: '/takedowns', label: 'navTakedowns', icon: 'M2 5l6-3 6 3v1H2zM3.5 7v5M8 7v5M12.5 7v5M2 13.5h12' },
      {
        to: '/helplines',
        label: 'navHelplines',
        icon: 'M3.5 2.5h3l1 3-1.8 1.2a8 8 0 003.6 3.6L10.5 8.5l3 1v3a1 1 0 01-1 1A10 10 0 012.5 3.5a1 1 0 011-1z',
      },
    ],
  },
  {
    label: 'navGroupDetection',
    items: [{ to: '/feed', label: 'navFeed', icon: 'M1.5 8h3l2-5 3 10 2-5h3' }],
  },
  {
    label: 'navGroupInsights',
    items: [
      { to: '/impact', label: 'navImpact', icon: 'M2 13.5h12M4 13.5V9M8 13.5V4M12 13.5V7' },
      { to: '/quality', label: 'navQuality', icon: 'M2.5 8a5.5 5.5 0 1011 0 5.5 5.5 0 10-11 0M5.5 8l2 2 3.5-4' },
    ],
  },
  {
    label: 'navGroupSystem',
    items: [
      {
        to: '/chain',
        label: 'navChain',
        icon: 'M6.5 9.5l3-3M5 7.5L3.5 9a2.1 2.1 0 003 3L8 10.5M8 5.5L9.5 4a2.1 2.1 0 013 3L11 8.5',
      },
      { to: '/audit', label: 'navAudit', icon: 'M4 1.500h6l3 3v10H4zM9.5 1.500v3.500h3.500M6 8h5M6 11h5' },
    ],
  },
]
