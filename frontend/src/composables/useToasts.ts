import { ref } from 'vue'

export interface Toast { id: number; kind: 'error' | 'info' | 'success'; text: string; ttl?: number }
const toasts = ref<Toast[]>([])
let seq = 0

export function useToasts() {
  function push(t: Omit<Toast, 'id'>): number {
    const id = ++seq
    toasts.value.push({ id, ...t })
    if (t.ttl !== 0) setTimeout(() => remove(id), t.ttl ?? 4000)
    return id
  }
  function remove(id: number) { toasts.value = toasts.value.filter(t => t.id !== id) }
  function clear() { toasts.value = [] }
  return { toasts, push, remove, clear }
}
