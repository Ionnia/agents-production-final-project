import { it, expect, beforeEach, beforeAll, afterAll, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'
import { handlers } from '../mocks/handlers'
import { useChatStore } from './chat'

const server = setupServer(...handlers)
beforeAll(() => server.listen()); afterAll(() => server.close())
afterEach(() => server.resetHandlers())
beforeEach(() => setActivePinia(createPinia()))

it('sending a first message streams a reply and a clarifying question', async () => {
  const chat = useChatStore()
  await chat.send('Хотим в Рим в сентябре')
  await chat.waitForIdle()
  expect(chat.messages.some(m => m.role === 'user')).toBe(true)
  expect(chat.messages.some(m => m.role === 'assistant' && m.content.length > 0)).toBe(true)
  expect(chat.pendingQuestion).toBeTruthy()
})

it('renders the assistant reply when the backend sends a final message with no deltas', async () => {
  // The live GigaChat backend emits a single `message` event (no `message_delta`
  // chunks). Regression guard: the bubble must still appear without a page reload.
  server.use(
    http.get('*/api/v1/chat/:runId/stream', ({ params }) => {
      const body =
        `event: message\ndata: ${JSON.stringify({ run_id: params.runId, message: { id: 'a1', role: 'assistant', content: 'Готовый маршрут', created_at: '2026-06-15T00:00:00Z' } })}\n\n` +
        `event: run_status\ndata: ${JSON.stringify({ run_id: params.runId, status: 'completed' })}\n\n`
      return new HttpResponse(body, { headers: { 'Content-Type': 'text/event-stream' } })
    }),
  )
  const chat = useChatStore()
  await chat.send('Подбери поездку в Дубай')
  await chat.waitForIdle()
  const reply = chat.messages.find(m => m.role === 'assistant')
  expect(reply?.content).toBe('Готовый маршрут')
  expect(reply?.streaming).toBeFalsy()
})

it('an `error` SSE frame sets planStatus to error and does not appear as a reply', async () => {
  server.use(
    http.get('*/api/v1/chat/:runId/stream', ({ params }) => {
      const body =
        `event: error\ndata: ${JSON.stringify({ run_id: params.runId, error: { code: 'agent_failed', message: 'Агент упал' } })}\n\n`
      return new HttpResponse(body, { headers: { 'Content-Type': 'text/event-stream' } })
    }),
  )
  const chat = useChatStore()
  await chat.send('Сломай агента')
  await chat.waitForIdle()
  expect(chat.planStatus).toBe('error')
  expect(chat.messages.some(m => m.role === 'assistant')).toBe(false)
  expect(chat.running).toBe(false)
})

it('reset() cancels the in-flight run; a stale stream does not pollute the new chat', async () => {
  // The stream stays open (never closes) so the run is still in flight when we reset.
  let release: () => void = () => {}
  const gate = new Promise<void>(r => { release = r })
  server.use(
    http.get('*/api/v1/chat/:runId/stream', ({ params }) => {
      const stream = new ReadableStream({
        async start(controller) {
          await gate // hold the connection open until the test releases it
          controller.enqueue(new TextEncoder().encode(
            `event: message\ndata: ${JSON.stringify({ run_id: params.runId, message: { id: 'late', role: 'assistant', content: 'Поздний ответ', created_at: '2026-06-15T00:00:00Z' } })}\n\n`))
          controller.close()
        },
      })
      return new HttpResponse(stream, { headers: { 'Content-Type': 'text/event-stream' } })
    }),
  )
  const chat = useChatStore()
  await chat.send('Первый чат')
  expect(chat.running).toBe(true)
  // New chat mid-reply: state is cleared and the run must be cancelled.
  chat.reset()
  expect(chat.running).toBe(false)
  expect(chat.messages).toHaveLength(0)
  // Let the orphaned stream try to deliver its late message; it must be ignored.
  release()
  await chat.waitForIdle()
  expect(chat.messages.some(m => m.content === 'Поздний ответ')).toBe(false)
  expect(chat.messages).toHaveLength(0)
})

it('hydrate() cancels an in-flight stream and clears live-only plan state', async () => {
  let release: () => void = () => {}
  const gate = new Promise<void>(r => { release = r })
  server.use(
    http.get('*/api/v1/chat/:runId/stream', ({ params }) => {
      const stream = new ReadableStream({
        async start(controller) {
          await gate
          controller.enqueue(new TextEncoder().encode(
            `event: message\ndata: ${JSON.stringify({ run_id: params.runId, message: { id: 'late-s1', role: 'assistant', content: 'Ответ из старой сессии', created_at: '2026-06-15T00:00:00Z' } })}\n\n`))
          controller.close()
        },
      })
      return new HttpResponse(stream, { headers: { 'Content-Type': 'text/event-stream' } })
    }),
  )
  const chat = useChatStore()
  chat.planStatus = 'ready'
  chat.planId = 'P-old'
  await chat.send('Первый чат')
  expect(chat.running).toBe(true)

  chat.hydrate('S2', [{ id: 'u2', role: 'user', content: 'Вторая сессия', created_at: '2026-06-15T00:00:00Z' } as any])
  expect(chat.running).toBe(false)
  expect(chat.planStatus).toBeNull()
  expect(chat.planId).toBeNull()
  release()
  await chat.waitForIdle()
  expect(chat.messages.map(m => m.content)).toEqual(['Вторая сессия'])
})

it('a new run clears stale ready plan state before handling a failed replanning reply', async () => {
  let turn = 0
  server.use(
    http.get('*/api/v1/chat/:runId/stream', ({ params }) => {
      turn += 1
      const body = turn === 1
        ? `event: plan_status\ndata: ${JSON.stringify({ run_id: params.runId, plan_id: 'P-ready', status: 'ready' })}\n\n` +
          `event: run_status\ndata: ${JSON.stringify({ run_id: params.runId, status: 'completed' })}\n\n`
        : `event: message\ndata: ${JSON.stringify({ run_id: params.runId, message: { id: 'a-fail', role: 'assistant', content: 'Нужно уточнение', created_at: '2026-06-15T00:00:00Z' } })}\n\n` +
          `event: plan_status\ndata: ${JSON.stringify({ run_id: params.runId, plan_id: 'P-failed', status: 'error' })}\n\n` +
          `event: run_status\ndata: ${JSON.stringify({ run_id: params.runId, status: 'completed' })}\n\n`
      return new HttpResponse(body, { headers: { 'Content-Type': 'text/event-stream' } })
    }),
  )
  const chat = useChatStore()
  await chat.send('Собери план')
  await chat.waitForIdle()
  expect(chat.planStatus).toBe('ready')
  expect(chat.planId).toBe('P-ready')

  await chat.send('Переделай план')
  await chat.waitForIdle()
  expect(chat.messages.some(m => m.content === 'Нужно уточнение')).toBe(true)
  expect(chat.planStatus).toBeNull()
  expect(chat.planId).toBeNull()
})
