import { it, expect, beforeEach, beforeAll, afterAll } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'
import { handlers } from '../mocks/handlers'
import { useAuthStore } from './auth'
import { useSessionsStore } from './sessions'
import { useGroupsStore } from './groups'
import { useChatStore } from './chat'
import { usePlansStore } from './plans'

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

it('purges the previous user\'s cached data on logout', async () => {
  const auth = useAuthStore()
  await auth.login('demo@travel.app', 'password')
  // Simulate a populated session for user A across the per-user data stores.
  useSessionsStore().list.push({ id: 'S1', summary: 'A', created_at: '', updated_at: '' } as any)
  useGroupsStore().list.push({ id: 'G1', name: 'g', member_count: 0, created_at: '' } as any)
  useChatStore().messages.push({ id: 'm1', role: 'user', content: 'hi' })
  usePlansStore().current = { id: 'P1' } as any

  await auth.logout()

  expect(useSessionsStore().list).toEqual([])
  expect(useGroupsStore().list).toEqual([])
  expect(useChatStore().messages).toEqual([])
  expect(useChatStore().sessionId).toBeNull()
  expect(usePlansStore().current).toBeNull()
})

it('purges the previous user\'s cached data when a different user logs in', async () => {
  // No explicit logout — switching users (a fresh login) must not leak A's data.
  useSessionsStore().list.push({ id: 'S1', summary: 'A', created_at: '', updated_at: '' } as any)
  useChatStore().messages.push({ id: 'm1', role: 'user', content: 'hi' })

  const auth = useAuthStore()
  await auth.login('demo@travel.app', 'password')

  expect(useSessionsStore().list).toEqual([])
  expect(useChatStore().messages).toEqual([])
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
