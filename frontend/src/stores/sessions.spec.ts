import { it, expect, beforeEach, beforeAll, afterAll } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { setupServer } from 'msw/node'
import { handlers } from '../mocks/handlers'
import { useSessionsStore } from './sessions'

const server = setupServer(...handlers)
beforeAll(() => server.listen()); afterAll(() => server.close())
beforeEach(() => setActivePinia(createPinia()))

it('loads the session list and a session detail', async () => {
  const s = useSessionsStore()
  await s.loadList()
  expect(s.list.length).toBeGreaterThan(0)
  await s.loadDetail('S-0001')
  expect(s.current?.messages.length).toBeGreaterThan(0)
})
