import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { effectScope, nextTick, ref } from 'vue'
import { useTypewriter } from './useTypewriter'

describe('useTypewriter', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('reveals the source in 18-char chunks every 120ms', async () => {
    const src = ref('')
    const scope = effectScope()
    const tw = scope.run(() => useTypewriter(() => src.value))!

    // A whole reply arriving at once (the live single-`message` case) still types out.
    src.value = 'a'.repeat(40)
    await nextTick()
    expect(tw.typing.value).toBe(true)
    expect(tw.displayed.value).toBe('') // nothing until the first interval fires

    await vi.advanceTimersByTimeAsync(120)
    expect(tw.displayed.value.length).toBe(18)
    await vi.advanceTimersByTimeAsync(120)
    expect(tw.displayed.value.length).toBe(36)
    await vi.advanceTimersByTimeAsync(120)
    expect(tw.displayed.value).toBe('a'.repeat(40))
    expect(tw.typing.value).toBe(false)

    scope.stop()
  })

  it('renders verbatim and never animates when instant', async () => {
    const src = ref('hello')
    const scope = effectScope()
    const tw = scope.run(() => useTypewriter(() => src.value, { instant: true }))!

    expect(tw.displayed.value).toBe('hello')
    expect(tw.typing.value).toBe(false)
    src.value = 'world'
    await nextTick()
    expect(tw.displayed.value).toBe('world')
    expect(tw.typing.value).toBe(false)

    scope.stop()
  })
})
