import { it, expect } from 'vitest'
import { useToasts } from './useToasts'

it('adds and auto-removes a toast', async () => {
  const { toasts, push, clear } = useToasts()
  clear()
  const id = push({ kind: 'error', text: 'boom', ttl: 10 })
  expect(toasts.value.find(t => t.id === id)).toBeTruthy()
  await new Promise(r => setTimeout(r, 30))
  expect(toasts.value.find(t => t.id === id)).toBeFalsy()
})
