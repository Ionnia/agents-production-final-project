import { it, expect, beforeEach, beforeAll, afterAll, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { setupServer } from 'msw/node'
import { handlers } from '../mocks/handlers'
import { usePlansStore } from './plans'

const server = setupServer(...handlers)
beforeAll(() => server.listen()); afterAll(() => server.close())
beforeEach(() => setActivePinia(createPinia()))
afterEach(() => server.resetHandlers())

it('loads a plan with map + calendar and accepts it', async () => {
  const p = usePlansStore()
  await p.load('PL-0001')
  expect(p.current?.status).toBe('ready')
  expect(p.map?.editable).toBe(true)
  expect(p.calendar?.events.length).toBeGreaterThan(0)
  await p.accept('PL-0001')
  expect(p.current?.status).toBe('accepted')
})

it('modify returns a run id and stages edits', async () => {
  const { http, HttpResponse } = await import('msw')
  // Override both GET plan and POST modify so this test is db-state independent
  server.use(
    http.get('*/api/v1/plans/:id', ({ params }) =>
      HttpResponse.json({
        id: params.id, session_id: 'S-0001', group_id: 'G-0001', run_id: 'run-seed', status: 'ready',
        summary: 'Test', destination: 'Рим', start_date: '2026-09-05', end_date: '2026-09-12',
        estimated_total_rub: 100000, items: {}, map_points: [], created_at: '', updated_at: '',
      }),
    ),
    http.get('*/api/v1/plans/:id/map', ({ params }) =>
      HttpResponse.json({ plan_id: params.id, status: 'ready', editable: true, points: [], bounds: { north: 0, south: 0, east: 0, west: 0 } }),
    ),
    http.get('*/api/v1/plans/:id/calendar', ({ params }) =>
      HttpResponse.json({ plan_id: params.id, timezone: 'UTC', events: [] }),
    ),
    http.post('*/api/v1/plans/:id/modify', () =>
      HttpResponse.json({ run_id: 'run-modify-test' }, { status: 202 }),
    ),
  )
  const p = usePlansStore()
  await p.load('PL-0001')
  const runId = await p.modify('PL-0001', { add: [{ name: 'Венеция', kind: 'stop' }] })
  expect(runId).toBeTruthy()
})
