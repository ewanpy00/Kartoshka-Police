import { beforeEach, describe, expect, it } from 'vitest'
import { setLocale, t } from './i18n'

describe('language switch', () => {
  beforeEach(() => setLocale('en'))

  it('sets rtl and lang for Arabic and remembers the choice', () => {
    setLocale('ar')
    expect(document.documentElement.dir).toBe('rtl')
    expect(document.documentElement.lang).toBe('ar')
    expect(localStorage.getItem('locale')).toBe('ar')
  })

  it('returns to ltr for English', () => {
    setLocale('ar')
    setLocale('en')
    expect(document.documentElement.dir).toBe('ltr')
  })

  it('fills placeholders', () => {
    expect(t('leadTime', { n: 5 })).toBe('ahead of Google Safe Browsing by at least 5 hours')
  })
})
