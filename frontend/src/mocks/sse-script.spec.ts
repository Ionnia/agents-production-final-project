import { it, expect } from 'vitest'
import { buildRunFrames } from './sse-script'

it('first message run asks then builds a plan, terminal completed', () => {
  const frames = buildRunFrames({ runId: 'r1', planId: 'PL-9', kind: 'first', text: 'Рим' })
  const names = frames.map(f => f.event)
  expect(names[0]).toBe('run_status')
  expect(names).toContain('clarifying_question')
  expect(names).toContain('plan_status')
  expect(names).toContain('map')
  expect(names.at(-1)).toBe('run_status')
  expect((frames.at(-1)!.data as any).status).toBe('completed')
})
