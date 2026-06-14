import { it, expect, beforeAll, afterAll } from 'vitest'
import { setupServer } from 'msw/node'
import { handlers } from './handlers'

const server = setupServer(...handlers)
beforeAll(() => server.listen())
afterAll(() => server.close())
const base = 'http://localhost/api/v1'

it('login returns tokens and me works with the bearer', async () => {
  const login = await fetch(base + '/auth/login', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: 'demo@travel.app', password: 'password' }) })
  expect(login.status).toBe(200)
  const { access_token } = await login.json()
  const me = await fetch(base + '/auth/me', { headers: { authorization: `Bearer ${access_token}` } })
  expect(me.status).toBe(200)
  expect((await me.json()).email).toBe('demo@travel.app')
})

it('chat returns a run_id and the stream emits frames ending completed', async () => {
  const acc = await (await fetch(base + '/chat', { method: 'POST', headers: { 'content-type': 'application/json', authorization: 'Bearer x' }, body: JSON.stringify({ message: 'Рим' }) })).json()
  expect(acc.run_id).toBeTruthy()
  const ticket = (await (await fetch(`${base}/chat/${acc.run_id}/stream-ticket`, { method: 'POST', headers: { authorization: 'Bearer x' } })).json()).ticket
  const res = await fetch(`${base}/chat/${acc.run_id}/stream?ticket=${ticket}`, { headers: { accept: 'text/event-stream' } })
  const text = await res.text()
  expect(text).toContain('event: run_status')
  expect(text).toContain('"status":"completed"')
})

it('plan map exposes editable gate and calendar has events', async () => {
  const map = await (await fetch(base + '/plans/PL-0001/map', { headers: { authorization: 'Bearer x' } })).json()
  expect(map.editable).toBe(true)
  const cal = await (await fetch(base + '/plans/PL-0001/calendar', { headers: { authorization: 'Bearer x' } })).json()
  expect(cal.events.length).toBeGreaterThan(0)
})
