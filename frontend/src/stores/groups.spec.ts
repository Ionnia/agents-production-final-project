import { it, expect, beforeEach, beforeAll, afterAll } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { setupServer } from 'msw/node'
import { handlers } from '../mocks/handlers'
import { useGroupsStore } from './groups'

const server = setupServer(...handlers)
beforeAll(() => server.listen()); afterAll(() => server.close())
beforeEach(() => setActivePinia(createPinia()))

it('lists and creates groups', async () => {
  const g = useGroupsStore()
  await g.loadList()
  const before = g.list.length
  await g.create({ name: 'Тест', members: [{ full_name: 'A' }] })
  await g.loadList()
  expect(g.list.length).toBe(before + 1)
})
