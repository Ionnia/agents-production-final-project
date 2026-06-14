import type { ApiError } from './types'

export class ApiClientError extends Error {
  constructor(public status: number, public code: string, message: string, public details?: unknown) { super(message) }
}

export interface ClientOptions {
  baseUrl?: string
  fetch?: typeof fetch
  getToken?: () => string | null
}

export function createClient(opts: ClientOptions = {}) {
  const baseUrl = opts.baseUrl ?? '/api/v1'
  const f = opts.fetch ?? globalThis.fetch.bind(globalThis)
  const getToken = opts.getToken ?? (() => null)

  async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const headers: Record<string, string> = {}
    const token = getToken()
    if (token) headers.authorization = `Bearer ${token}`
    if (body !== undefined) headers['content-type'] = 'application/json'
    const res = await f(new Request(baseUrl + path, { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined }))
    if (res.status === 204) return undefined as T
    const isJson = res.headers.get('content-type')?.includes('application/json')
    const payload = isJson ? await res.json() : undefined
    if (!res.ok) {
      const e = (payload as ApiError | undefined)?.error
      throw new ApiClientError(res.status, e?.code ?? 'internal', e?.message ?? res.statusText, e?.details)
    }
    return payload as T
  }

  return {
    get: <T>(p: string) => request<T>('GET', p),
    post: <T>(p: string, b?: unknown) => request<T>('POST', p, b),
    raw: f,
    baseUrl,
  }
}
