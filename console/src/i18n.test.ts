import { beforeEach, describe, expect, it } from 'vitest'
import { formatAge, setLocale, t } from './i18n'

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

describe('formatAge', () => {
  beforeEach(() => setLocale('en'))
  const ago = (min: number) => new Date(Date.now() - min * 60_000).toISOString()

  it('uses minutes under an hour', () => {
    expect(formatAge(ago(5))).toBe('5 min')
  })

  it('uses hours, with minutes when not round, under a day', () => {
    expect(formatAge(ago(120))).toBe('2 h')
    expect(formatAge(ago(135))).toBe('2 h 15 min')
  })

  it('uses days from 24 hours', () => {
    expect(formatAge(ago(3 * 24 * 60))).toBe('3 d')
  })
})
