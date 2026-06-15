import { it, expect, beforeAll, afterAll, afterEach, beforeEach } from 'vitest'
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
      { path: '/plans/:planId', name: 'plan', component: { template: '<div />' }, props: true },
    ],
  })
}
const Root = { template: '<RouterView />' }

const READY_PLAN = {
  id: 'P1', session_id: 'S-rec', run_id: 'run-rec', status: 'ready',
  destination: 'Стамбул', start_date: '2026-07-05', end_date: '2026-07-15',
  decision_rationale: 'Подобрал перелёт и отель в Стамбуле в рамках бюджета.',
  estimated_total_rub: 148400,
  items: {
    flight: { flight_id: 'FL-102', origin_city: 'Москва', destination: 'Стамбул', price_rub: 74200, baggage_included: true, stops: 1, departure_time: '10:20', arrival_time: '15:40', fare_type: 'standard' },
    hotel: { hotel_id: 'HT-045', destination: 'Стамбул', stars: 4, price_per_night_rub: 11260, nights: 10, breakfast_included: true, free_cancellation: true, rating: 8.7 },
  },
  map_points: [], created_at: '2026-06-15T00:00:00Z', updated_at: '2026-06-15T00:00:00Z',
}

function recStream(runId: unknown) {
  return new HttpResponse(
    `event: plan_status\ndata: ${JSON.stringify({ run_id: runId, plan_id: 'P1', status: 'building' })}\n\n` +
    `event: plan_status\ndata: ${JSON.stringify({ run_id: runId, plan_id: 'P1', status: 'ready' })}\n\n` +
    `event: message\ndata: ${JSON.stringify({ run_id: runId, message: { id: 'm1', role: 'assistant', content: 'План готов', created_at: '2026-06-15T00:00:00Z', plan_ref: { plan_id: 'P1', status: 'ready' } } })}\n\n` +
    `event: run_status\ndata: ${JSON.stringify({ run_id: runId, status: 'completed' })}\n\n`,
    { headers: { 'Content-Type': 'text/event-stream' } },
  )
}

it('renders an inline plan card for approval when the plan is ready, then accepts it', async () => {
  let accepted = false
  server.use(
    http.post('*/api/v1/chat', () => HttpResponse.json({ run_id: 'run-rec', session_id: 'S-rec' }, { status: 202 })),
    http.post('*/api/v1/chat/:runId/stream-ticket', () => HttpResponse.json({ ticket: 'tk-1234567890123456789012345', expires_in: 60 })),
    http.get('*/api/v1/chat/:runId/stream', ({ params }) => recStream(params.runId)),
    http.get('*/api/v1/sessions', () => HttpResponse.json({ items: [], total: 0, limit: 20, offset: 0 })),
    http.get('*/api/v1/plans/P1', () => HttpResponse.json(accepted ? { ...READY_PLAN, status: 'accepted' } : READY_PLAN)),
    http.post('*/api/v1/plans/P1/accept', () => { accepted = true; return HttpResponse.json({ ...READY_PLAN, status: 'accepted' }) }),
  )
  const router = makeRouter()
  router.push('/'); await router.isReady()
  const wrapper = mount(Root, { global: { plugins: [router] } })
  await flushPromises()

  await wrapper.find('textarea').setValue('Хочу в Стамбул, 5–15 июля')
  await wrapper.find('button.send').trigger('click')
  await flushPromises(); await flushPromises()

  // The plan is presented inline with its components and a total, plus an approve button.
  const card = wrapper.find('.pc')
  expect(card.exists()).toBe(true)
  expect(card.text()).toContain('Стамбул')
  expect(card.text()).toContain('Москва → Стамбул')
  const accept = wrapper.find('button.accept')
  expect(accept.exists()).toBe(true)

  await accept.trigger('click')
  await flushPromises()
  // Accepting persists the plan: the card reflects the accepted state and the button is gone.
  expect(wrapper.find('.pc').text()).toContain('План принят')
  expect(wrapper.find('button.accept').exists()).toBe(false)
})

it('restores the inline approval card when a session with a ready plan is reopened', async () => {
  server.use(
    http.get('*/api/v1/sessions', () => HttpResponse.json({ items: [], total: 0, limit: 20, offset: 0 })),
    http.get('*/api/v1/sessions/S-rec', () => HttpResponse.json({
      id: 'S-rec', summary: 'Стамбул', created_at: '2026-06-15T00:00:00Z', updated_at: '2026-06-15T00:00:00Z',
      messages: [
        { id: 'u1', role: 'user', content: 'Стамбул, 5–15 июля', created_at: '2026-06-15T00:00:00Z' },
        { id: 'm1', role: 'assistant', content: 'План готов', created_at: '2026-06-15T00:00:01Z', plan_ref: { plan_id: 'P1', status: 'ready' } },
      ],
      plans: [],
    })),
    http.get('*/api/v1/plans/P1', () => HttpResponse.json(READY_PLAN)),
  )
  const router = makeRouter()
  router.push('/c/S-rec'); await router.isReady()
  const wrapper = mount(Root, { global: { plugins: [router] } })
  await flushPromises(); await flushPromises()

  const card = wrapper.find('.pc')
  expect(card.exists()).toBe(true)
  expect(card.text()).toContain('Стамбул')
  expect(wrapper.find('button.accept').exists()).toBe(true) // still approvable after reload
})
