// Regression spec for live clarification rendering. Drives ChatView with an SSE
// stream that matches the REAL backend clarification shape:
// run_status(running) -> clarifying_question -> run_status(completed), with NO
// `message` / `message_delta` frame.
//   CASE 1: a turn-1 clarification renders the question panel live (no reload).
//   CASE 2: after answering, the earlier question stays in the live thread as a
//           bubble (it must not vanish until a manual reload) — guards the
//           store's flushPendingQuestion() demote-to-bubble behavior.
import { it, expect, beforeEach, beforeAll, afterAll, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { handlers } from '../../mocks/handlers'
import ChatView from './ChatView.vue'
import ClarifyingQuestion from './ClarifyingQuestion.vue'
import MessageBubble from './MessageBubble.vue'

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

// A clarification stream that matches the REAL backend: run_status running,
// then ONLY a clarifying_question (no message/message_delta), then completed.
function clarifyStream(runId: string, q: unknown) {
  return (
    `event: run_status\ndata: ${JSON.stringify({ run_id: runId, status: 'running' })}\n\n` +
    `event: clarifying_question\ndata: ${JSON.stringify({ run_id: runId, question: q })}\n\n` +
    `event: run_status\ndata: ${JSON.stringify({ run_id: runId, status: 'completed' })}\n\n`
  )
}

const Q1 = {
  id: 'q1',
  text: 'Какой формат отдыха предпочитаете?',
  allow_freeform: true,
  options: [{ id: 'o1', label: 'Пляж' }, { id: 'o2', label: 'Город' }],
}
const Q2 = {
  id: 'q2',
  text: 'На сколько дней планируете поездку?',
  allow_freeform: true,
  options: [{ id: 'd3', label: '3 дня' }, { id: 'd7', label: '7 дней' }],
}

it('CASE 1 (turn-1): real-backend clarification renders LIVE without reload', async () => {
  server.use(
    http.post('*/api/v1/chat', () => HttpResponse.json({ run_id: 'run1', session_id: 'S-clar' }, { status: 202 })),
    http.post('*/api/v1/chat/:runId/stream-ticket', () =>
      HttpResponse.json({ ticket: 'tk-1234567890123456789012345', expires_in: 60 })),
    http.get('*/api/v1/chat/:runId/stream', ({ params }) =>
      new HttpResponse(clarifyStream(String(params.runId), Q1), { headers: { 'Content-Type': 'text/event-stream' } })),
    http.get('*/api/v1/sessions', () => HttpResponse.json({ items: [], total: 0, limit: 20, offset: 0 })),
  )
  const router = makeRouter()
  router.push('/'); await router.isReady()
  const wrapper = mount(Root, { global: { plugins: [router] } })
  await flushPromises()

  await wrapper.find('textarea').setValue('Хочу в Рим')
  await wrapper.find('button.send').trigger('click')
  await flushPromises(); await flushPromises()

  const panel = wrapper.findComponent(ClarifyingQuestion)
  const bubbles = wrapper.findAllComponents(MessageBubble)
  const text = wrapper.text()

  // RECORD findings to the test log.
  console.log('[CASE1] route=', router.currentRoute.value.path)
  console.log('[CASE1] ClarifyingQuestion panel present =', panel.exists())
  console.log('[CASE1] MessageBubble count =', bubbles.length, '->', bubbles.map(b => b.text()))
  console.log('[CASE1] thread (.thread) visible =', wrapper.find('.thread').exists())
  console.log('[CASE1] question text in DOM =', text.includes(Q1.text))
  console.log('[CASE1] option chips in DOM =', text.includes('Пляж'), text.includes('Город'))

  // Assertions: the user must see the question live.
  expect(router.currentRoute.value.path).toBe('/c/S-clar')
  expect(panel.exists()).toBe(true)
  expect(text).toContain(Q1.text)
  expect(text).toContain('Пляж')
})

it('CASE 2 (multi-turn): after answering, is the FIRST question still visible live?', async () => {
  // Turn 1 -> Q1. Turn 2 (answering Q1) -> Q2. Both turns are clarification-only.
  let turn = 0
  server.use(
    http.post('*/api/v1/chat', () => {
      turn += 1
      return HttpResponse.json({ run_id: `run-${turn}`, session_id: 'S-multi' }, { status: 202 })
    }),
    http.post('*/api/v1/chat/:runId/stream-ticket', () =>
      HttpResponse.json({ ticket: 'tk-1234567890123456789012345', expires_in: 60 })),
    http.get('*/api/v1/chat/:runId/stream', ({ params }) => {
      const q = String(params.runId) === 'run-1' ? Q1 : Q2
      return new HttpResponse(clarifyStream(String(params.runId), q), { headers: { 'Content-Type': 'text/event-stream' } })
    }),
    http.get('*/api/v1/sessions', () => HttpResponse.json({ items: [], total: 0, limit: 20, offset: 0 })),
  )
  const router = makeRouter()
  router.push('/'); await router.isReady()
  const wrapper = mount(Root, { global: { plugins: [router] } })
  await flushPromises()

  // Turn 1
  await wrapper.find('textarea').setValue('Хочу в Рим')
  await wrapper.find('button.send').trigger('click')
  await flushPromises(); await flushPromises()
  console.log('[CASE2 after turn1] Q1 visible =', wrapper.text().includes(Q1.text))

  // Turn 2: answer Q1 by clicking the first option chip.
  const chip = wrapper.findComponent(ClarifyingQuestion).find('button.chip')
  await chip.trigger('click')
  await flushPromises(); await flushPromises()

  const text = wrapper.text()
  const panel = wrapper.findComponent(ClarifyingQuestion)
  const bubbles = wrapper.findAllComponents(MessageBubble)

  console.log('[CASE2 after turn2] route =', router.currentRoute.value.path)
  console.log('[CASE2 after turn2] current panel question =', panel.exists() ? panel.text() : '(none)')
  console.log('[CASE2 after turn2] Q1 still visible =', text.includes(Q1.text))
  console.log('[CASE2 after turn2] Q2 visible =', text.includes(Q2.text))
  console.log('[CASE2 after turn2] MessageBubble count =', bubbles.length, '->', bubbles.map(b => b.text()))
  console.log('[CASE2 after turn2] user msgs present: Хочу в Рим =', text.includes('Хочу в Рим'), ' Пляж(answer label) =', text.includes('Пляж'))

  // The current (trailing) question shows as the live panel.
  expect(panel.exists()).toBe(true)
  expect(text).toContain(Q2.text)
  // The answered question must remain in the live thread as a bubble — matching
  // what a reload would show via hydrate() — instead of vanishing.
  expect(text).toContain(Q1.text)
  expect(bubbles.some(b => b.text().includes(Q1.text))).toBe(true)
})
