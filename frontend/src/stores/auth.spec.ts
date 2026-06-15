import { it, expect, beforeEach, beforeAll, afterAll } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'
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

it('clears in-memory tokens when restore refresh succeeds but /me is unauthorized', async () => {
  localStorage.setItem('travel.auth', JSON.stringify({ refreshToken: 'stale-refresh' }))
  server.use(
    http.post('*/api/v1/auth/refresh', () => HttpResponse.json({ access_token: 'new-access', refresh_token: 'new-refresh' })),
    http.get('*/api/v1/auth/me', () => HttpResponse.json({ code: 'unauthorized', message: 'Unauthorized' }, { status: 401 })),
  )
  const auth = useAuthStore()
  await auth.restore()
  expect(auth.isAuthenticated).toBe(false)
  expect(auth.accessToken).toBeNull()
  expect(auth.refreshToken).toBeNull()
  expect(auth.user).toBeNull()
  expect(localStorage.getItem('travel.auth')).toBeNull()
})
