import { it, expect, beforeAll, afterAll, afterEach, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import PlanList from './PlanList.vue'

const server = setupServer()
beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
beforeEach(() => setActivePinia(createPinia()))

const router = createRouter({
  history: createMemoryHistory(),
  routes: [{ path: '/plans/:planId', component: { template: '<div />' } }],
})

// The user-scoped /plans endpoint returns a group-less accepted plan; the sidebar
// must list it (the per-group endpoint never could). Regression test for the
// "accepted plan missing from the sidebar" bug.
it('lists group-less plans from the user-scoped endpoint and reloads when opened', async () => {
  let calls = 0
  server.use(
    http.get('*/api/v1/plans', () => {
      calls++
      return HttpResponse.json({
        items: [{ plan_id: 'PL-X', status: 'accepted', destination: 'Стамбул', created_at: '2026-06-15T00:00:00Z' }],
      })
    }),
  )

  const wrapper = mount(PlanList, {
    props: { filter: '', open: false },
    global: { plugins: [router] },
  })
  await flushPromises()
  // Closed panel: no fetch, nothing listed.
  expect(calls).toBe(0)
  expect(wrapper.text()).not.toContain('Стамбул')

  await wrapper.setProps({ open: true })
  await flushPromises()
  expect(calls).toBe(1)
  const link = wrapper.find('a.item')
  expect(link.exists()).toBe(true)
  expect(link.text()).toContain('Стамбул')
  expect(link.attributes('href')).toContain('/plans/PL-X')
})
