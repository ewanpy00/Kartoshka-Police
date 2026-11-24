import { describe, expect, it } from 'vitest'
import { band, isHigh } from './bands'

describe('band', () => {
  it.each([
    [0, 'low'],
    [29, 'low'],
    [30, 'mid'],
    [70, 'mid'],
    [71, 'high'],
    [100, 'high'],
  ])('score %i is %s', (score, expected) => {
    expect(band(score)).toBe(expected)
  })

  it('isHigh is true only above 70', () => {
    expect([69, 70, 71].map(isHigh)).toEqual([false, false, true])
  })
})
