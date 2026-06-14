import { it, expect, beforeEach, beforeAll, afterAll } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { setupServer } from 'msw/node'
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
