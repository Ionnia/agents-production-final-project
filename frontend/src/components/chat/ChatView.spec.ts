import { it, expect, beforeEach, beforeAll, afterAll, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { handlers } from '../../mocks/handlers'
import ChatView from './ChatView.vue'

const server = setupServer(...handlers)
beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
beforeEach(() => setActivePinia(createPinia()))

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'chat', component: ChatView },
      { path: '/c/:sessionId', name: 'session', component: ChatView, props: true },
    ],
  })
}

const Root = { template: '<RouterView />' }

it('new chat: reply is visible after the run with the URL updated, no reload needed', async () => {
  server.use(
    http.post('*/api/v1/chat', () => HttpResponse.json({ run_id: 'run1', session_id: 'S-new' }, { status: 202 })),
    http.post('*/api/v1/chat/:runId/stream-ticket', () =>
      HttpResponse.json({ ticket: 'tk-1234567890123456789012345', expires_in: 60 })),
    http.get('*/api/v1/chat/:runId/stream', ({ params }) =>
      new HttpResponse(
        `event: message\ndata: ${JSON.stringify({ run_id: params.runId, message: { id: 'a1', role: 'assistant', content: 'Ваш маршрут готов', created_at: '2026-06-15T00:00:00Z' } })}\n\n` +
        `event: run_status\ndata: ${JSON.stringify({ run_id: params.runId, status: 'completed' })}\n\n`,
        { headers: { 'Content-Type': 'text/event-stream' } })),
    http.get('*/api/v1/sessions', () => HttpResponse.json({ items: [], total: 0, limit: 20, offset: 0 })),
    http.get('*/api/v1/sessions/S-new', () => HttpResponse.json({
      id: 'S-new', summary: 'x', created_at: '2026-06-15T00:00:00Z', updated_at: '2026-06-15T00:00:00Z',
      messages: [
        { id: 'u1', role: 'user', content: 'Поездка в Рим', created_at: '2026-06-15T00:00:00Z' },
        { id: 'a1', role: 'assistant', content: 'Ваш маршрут готов', created_at: '2026-06-15T00:00:01Z' },
      ], plans: [],
    })),
  )
  const router = makeRouter()
  router.push('/'); await router.isReady()
  const wrapper = mount(Root, { global: { plugins: [router] } })
  await flushPromises()

  await wrapper.find('textarea').setValue('Поездка в Рим')
  await wrapper.find('button.send').trigger('click')
  await flushPromises()
  await flushPromises()

  expect(router.currentRoute.value.path).toBe('/c/S-new')
  const text = wrapper.text()
  expect(text).toContain('Ваш маршрут готов') // bug 2: reply must be visible without reload
  const occurrences = text.split('Ваш маршрут готов').length - 1
  expect(occurrences).toBe(1) // bug 1: not doubled
})

it('a message that arrives after run_status:completed is not dropped', async () => {
  server.use(
    http.post('*/api/v1/chat', () => HttpResponse.json({ run_id: 'run2', session_id: 'S-ord' }, { status: 202 })),
    http.post('*/api/v1/chat/:runId/stream-ticket', () =>
      HttpResponse.json({ ticket: 'tk-1234567890123456789012345', expires_in: 60 })),
    // Note the order: run_status completed is emitted BEFORE the final message.
    http.get('*/api/v1/chat/:runId/stream', ({ params }) =>
      new HttpResponse(
        `event: run_status\ndata: ${JSON.stringify({ run_id: params.runId, status: 'completed' })}\n\n` +
        `event: message\ndata: ${JSON.stringify({ run_id: params.runId, message: { id: 'a9', role: 'assistant', content: 'Ответ агента', created_at: '2026-06-15T00:00:00Z' } })}\n\n`,
        { headers: { 'Content-Type': 'text/event-stream' } })),
    http.get('*/api/v1/sessions', () => HttpResponse.json({ items: [], total: 0, limit: 20, offset: 0 })),
  )
  const router = makeRouter()
  router.push('/'); await router.isReady()
  const wrapper = mount(Root, { global: { plugins: [router] } })
  await flushPromises()
  await wrapper.find('textarea').setValue('Привет')
  await wrapper.find('button.send').trigger('click')
  await flushPromises(); await flushPromises()
  expect(wrapper.text()).toContain('Ответ агента')
})

it('shows the agent message instead of a generic plan error when both arrive live', async () => {
  server.use(
    http.post('*/api/v1/chat', () => HttpResponse.json({ run_id: 'run-plan-error', session_id: 'S-plan-error' }, { status: 202 })),
    http.post('*/api/v1/chat/:runId/stream-ticket', () =>
      HttpResponse.json({ ticket: 'tk-1234567890123456789012345', expires_in: 60 })),
    http.get('*/api/v1/chat/:runId/stream', ({ params }) =>
      new HttpResponse(
        `event: message\ndata: ${JSON.stringify({ run_id: params.runId, message: { id: 'a-plan-error', role: 'assistant', content: 'Уточните бюджет и даты поездки, чтобы я смог подобрать маршрут.', created_at: '2026-06-15T00:00:00Z' } })}\n\n` +
        `event: plan_status\ndata: ${JSON.stringify({ run_id: params.runId, plan_id: 'P-error', status: 'error', error: 'Не удалось обработать план' })}\n\n` +
        `event: run_status\ndata: ${JSON.stringify({ run_id: params.runId, status: 'completed' })}\n\n`,
        { headers: { 'Content-Type': 'text/event-stream' } })),
    http.get('*/api/v1/sessions', () => HttpResponse.json({ items: [], total: 0, limit: 20, offset: 0 })),
  )
  const router = makeRouter()
  router.push('/'); await router.isReady()
  const wrapper = mount(Root, { global: { plugins: [router] } })
  await flushPromises()
  await wrapper.find('textarea').setValue('Спланируй поездку')
  await wrapper.find('button.send').trigger('click')
  await flushPromises(); await flushPromises()

  const text = wrapper.text()
  expect(text).toContain('Уточните бюджет и даты поездки')
  expect(text).not.toContain('Не удалось построить план')
})

it('hydrating a session with a pending clarifying question does not double it', async () => {
  server.use(
    http.get('*/api/v1/sessions', () => HttpResponse.json({ items: [], total: 0, limit: 20, offset: 0 })),
    http.get('*/api/v1/sessions/S-q', () => HttpResponse.json({
      id: 'S-q', summary: 'x', created_at: '2026-06-15T00:00:00Z', updated_at: '2026-06-15T00:00:00Z',
      messages: [
        { id: 'u1', role: 'user', content: 'Хочу в Рим', created_at: '2026-06-15T00:00:00Z' },
        {
          id: 'a1', role: 'assistant', content: 'Какой формат отдыха предпочитаете?',
          created_at: '2026-06-15T00:00:01Z',
          question: { id: 'q1', text: 'Какой формат отдыха предпочитаете?', allow_freeform: true, options: [{ id: 'o1', label: 'Пляж' }, { id: 'o2', label: 'Город' }] },
        },
      ], plans: [],
    })),
  )
  const router = makeRouter()
  router.push('/c/S-q'); await router.isReady()
  const wrapper = mount(Root, { global: { plugins: [router] } })
  await flushPromises()
  await flushPromises()

  const text = wrapper.text()
  const occurrences = text.split('Какой формат отдыха предпочитаете?').length - 1
  expect(occurrences).toBe(1) // fixed: shown once (question panel), not also as a bubble
})

it('submits composer text as a freeform answer when a clarifying question is pending', async () => {
  const requests: any[] = []
  let turn = 0
  server.use(
    http.post('*/api/v1/chat', async ({ request }) => {
      const body = await request.json()
      requests.push(body)
      turn += 1
      return HttpResponse.json({ run_id: `run-answer-${turn}`, session_id: 'S-answer' }, { status: 202 })
    }),
    http.post('*/api/v1/chat/:runId/stream-ticket', () =>
      HttpResponse.json({ ticket: 'tk-1234567890123456789012345', expires_in: 60 })),
    http.get('*/api/v1/chat/:runId/stream', ({ params }) => {
      const body = String(params.runId) === 'run-answer-1'
        ? `event: clarifying_question\ndata: ${JSON.stringify({ run_id: params.runId, question: { id: 'q-budget', text: 'Какой бюджет?', options: [], allow_freeform: true } })}\n\n` +
          `event: run_status\ndata: ${JSON.stringify({ run_id: params.runId, status: 'completed' })}\n\n`
        : `event: message\ndata: ${JSON.stringify({ run_id: params.runId, message: { id: 'a-answer', role: 'assistant', content: 'Принял бюджет', created_at: '2026-06-15T00:00:00Z' } })}\n\n` +
          `event: run_status\ndata: ${JSON.stringify({ run_id: params.runId, status: 'completed' })}\n\n`
      return new HttpResponse(body, { headers: { 'Content-Type': 'text/event-stream' } })
    }),
    http.get('*/api/v1/sessions', () => HttpResponse.json({ items: [], total: 0, limit: 20, offset: 0 })),
  )
  const router = makeRouter()
  router.push('/'); await router.isReady()
  const wrapper = mount(Root, { global: { plugins: [router] } })
  await flushPromises()
  await wrapper.find('textarea').setValue('Хочу в Грецию')
  await wrapper.find('button.send').trigger('click')
  await flushPromises(); await flushPromises()
  expect(wrapper.text()).toContain('Какой бюджет?')

  await wrapper.find('textarea').setValue('200000 рублей')
  await wrapper.find('button.send').trigger('click')
  await flushPromises(); await flushPromises()
  expect(requests[1]).toMatchObject({
    session_id: 'S-answer',
    in_reply_to_question_id: 'q-budget',
    selected_option_ids: [],
    freeform: '200000 рублей',
  })
  expect(requests[1]).not.toHaveProperty('message')
})

it('input is disabled while the agent is responding', async () => {
  server.use(
    http.post('*/api/v1/chat', () => HttpResponse.json({ run_id: 'run3', session_id: 'S-busy' }, { status: 202 })),
    http.post('*/api/v1/chat/:runId/stream-ticket', () =>
      HttpResponse.json({ ticket: 'tk-1234567890123456789012345', expires_in: 60 })),
    http.get('*/api/v1/chat/:runId/stream', () =>
      new HttpResponse('', { headers: { 'Content-Type': 'text/event-stream' } })),
    http.get('*/api/v1/sessions', () => HttpResponse.json({ items: [], total: 0, limit: 20, offset: 0 })),
  )
  const router = makeRouter()
  router.push('/'); await router.isReady()
  const wrapper = mount(Root, { global: { plugins: [router] } })
  await flushPromises()
  await wrapper.find('textarea').setValue('Поездка')
  // Assert on the tick right after submit, while the run is accepted but not finished.
  await wrapper.find('button.send').trigger('click')
  expect((wrapper.find('textarea').element as HTMLTextAreaElement).disabled).toBe(true)
  await flushPromises()
})
