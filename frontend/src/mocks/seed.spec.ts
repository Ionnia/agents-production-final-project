import { it, expect } from 'vitest'
import { createDb } from './seed'

it('seeds groups, sessions and a ready plan with map points', () => {
  const db = createDb()
  expect(db.groups.length).toBeGreaterThan(0)
  expect(db.sessions.length).toBeGreaterThan(0)
  const plan = db.plans[0]
  expect(plan.status).toBe('ready')
  expect(plan.map_points.length).toBeGreaterThanOrEqual(2)
  expect(plan.map_points[0].kind).toBe('origin')
})
