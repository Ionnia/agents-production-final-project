import { it, expect, vi, beforeEach } from 'vitest'
import { createClient } from './client'

beforeEach(() => { /* localStorage not used by client */ })

it('attaches bearer token and parses JSON', async () => {
  const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(async () => new Response(JSON.stringify({ ok: 1 }), { status: 200, headers: { 'content-type': 'application/json' } }))
  const c = createClient({ baseUrl: 'http://localhost/api/v1', fetch: fetchMock, getToken: () => 'tok' })
  const out = await c.get<{ ok: number }>('/auth/me')
  expect(out.ok).toBe(1)
  const req = fetchMock.mock.calls[0]![0] as Request
  expect(req.headers.get('authorization')).toBe('Bearer tok')
})

it('declares the Russian locale so the backend localizes agent/plan messages in Russian', async () => {
  const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(async () => new Response(JSON.stringify({ ok: 1 }), { status: 200, headers: { 'content-type': 'application/json' } }))
  const c = createClient({ baseUrl: 'http://localhost/api/v1', fetch: fetchMock, getToken: () => null })
  await c.post('/chat', { message: 'Хочу в Рим' })
  const req = fetchMock.mock.calls[0]![0] as Request
  expect(req.headers.get('accept-language')).toBe('ru-RU')
})

it('throws ApiClientError carrying the error envelope', async () => {
  const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(async () => new Response(JSON.stringify({ error: { code: 'not_found', message: 'nope' } }), { status: 404, headers: { 'content-type': 'application/json' } }))
  const c = createClient({ baseUrl: 'http://localhost/api/v1', fetch: fetchMock, getToken: () => null })
  await expect(c.get('/x')).rejects.toMatchObject({ code: 'not_found', status: 404 })
})
