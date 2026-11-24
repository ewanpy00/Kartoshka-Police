import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'
import { setLocale } from '../i18n'
import { _resetStatsForTest, useStats } from '../stats'
import StatStrip from './StatStrip.vue'

beforeEach(() => {
  setLocale('en')
  _resetStatsForTest()
})

describe('StatStrip', () => {
  it('renders nothing when all stats are null', () => {
    const wrapper = mount(StatStrip)
    expect(wrapper.find('.stat-strip').exists()).toBe(false)
    expect(wrapper.html()).not.toContain('stat')
  })

  it('shows the median lead time', () => {
    useStats().medianLead.value = { hours: 14, cases: 3 }
    const text = mount(StatStrip).text()
    expect(text).toContain('at least 14 h')
    expect(text).toContain('3 cases')
  })

  it('shows no lead text when it is null', () => {
    useStats().awaiting.value = 4
    expect(mount(StatStrip).text()).not.toContain('lead')
  })

  it('shows a real zero', () => {
    useStats().awaiting.value = 0
    const wrapper = mount(StatStrip)
    expect(wrapper.find('.num').text()).toBe('0')
  })
})
