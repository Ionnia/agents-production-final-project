import { it, expect, beforeEach, beforeAll, afterAll } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'
import { handlers } from '../mocks/handlers'
import { useChatStore } from './chat'

const server = setupServer(...handlers)
beforeAll(() => server.listen()); afterAll(() => server.close())
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
