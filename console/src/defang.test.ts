import { describe, expect, it } from 'vitest'
import { defang } from './defang'

describe('defang', () => {
  it('brackets the dots of a domain', () => {
    expect(defang('tamm-pay.xyz')).toBe('tamm-pay[.]xyz')
  })

  it('rewrites the scheme of a URL', () => {
    expect(defang('https://tamm-pay.xyz/login')).toBe('hxxps://tamm-pay[.]xyz/login')
    expect(defang('http://a.b')).toBe('hxxp://a[.]b')
  })
})
