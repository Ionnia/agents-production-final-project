import { it, expect, beforeEach, beforeAll, afterAll } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { setupServer } from 'msw/node'
import { handlers } from '../mocks/handlers'
import { useAuthStore } from './auth'

const server = setupServer(...handlers)
beforeAll(() => server.listen()); afterAll(() => server.close())
beforeEach(() => { setActivePinia(createPinia()); localStorage.clear() })

it('logs in, exposes the token, and restores from storage', async () => {
  const auth = useAuthStore()
  await auth.login('demo@travel.app', 'password')
  expect(auth.isAuthenticated).toBe(true)
  expect(auth.accessToken).toBeTruthy()
  setActivePinia(createPinia())
  const fresh = useAuthStore()
  await fresh.restore()
  expect(fresh.isAuthenticated).toBe(true)
})
