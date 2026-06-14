import { it, expect } from 'vitest'
import { lensVars } from './useCursorLens'

it('computes mask vars centered on the cursor', () => {
  const v = lensVars(200, 100, 80)
  expect(v['--mpx']).toBe('120px')   // 200 - 80
  expect(v['--mpy']).toBe('20px')    // 100 - 80
  expect(v['--d']).toBe('160px')     // 2 * 80
})
