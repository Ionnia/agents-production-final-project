import { onScopeDispose, ref, watch, type Ref } from 'vue'
import { usePreferredReducedMotion } from '@vueuse/core'

// Replays text one chunk at a time to recreate the "typing" feel. The cadence
// mirrors the mock SSE stream so a real reply reads exactly like the streamed
// mock replies do in dev: `src/mocks/sse-script.ts` splits the reply into
// 18-char chunks and `src/mocks/handlers.ts` paces frames at 120ms. The live
// backend often delivers the whole reply as a single final `message`, so without
// this it would pop in all at once instead of typing out.
const CHUNK = 18
const INTERVAL_MS = 120

export interface UseTypewriterOptions {
  /** Skip the animation and mirror the source verbatim (history, reduced motion). */
  instant?: boolean
}

/**
 * Reveals `source()` progressively into the returned `displayed` ref. New text
 * (appended or replaced) is animated toward at a steady chunk-per-interval pace
 * regardless of how fast it actually arrives, so a single-shot reply and a
 * delta-streamed one both type out identically. `typing` is true while the
 * revealed text is still catching up to the source.
 */
export function useTypewriter(
  source: () => string,
  options: UseTypewriterOptions = {},
): { displayed: Ref<string>; typing: Ref<boolean> } {
  const reducedMotion = usePreferredReducedMotion()
  const instant = options.instant || reducedMotion.value === 'reduce'
  const displayed = ref(instant ? source() : '')
  const typing = ref(false)

  // Reduced motion / history: render verbatim and stay in sync, no animation.
  if (instant) {
    watch(source, (v) => { displayed.value = v })
    return { displayed, typing }
  }

  let timer: ReturnType<typeof setInterval> | null = null
  function stop() {
    if (timer) { clearInterval(timer); timer = null }
    typing.value = false
  }
  function reveal() {
    const target = source()
    if (displayed.value.length >= target.length) { stop(); return }
    displayed.value = target.slice(0, displayed.value.length + CHUNK)
    if (displayed.value.length >= target.length) stop()
  }
  function start() {
    if (!timer) { typing.value = true; timer = setInterval(reveal, INTERVAL_MS) }
  }

  watch(source, (v) => {
    // Content was reset/replaced with something shorter — snap rather than rewind.
    if (v.length < displayed.value.length) { displayed.value = v; stop(); return }
    if (displayed.value.length < v.length) start()
  }, { immediate: true })

  onScopeDispose(stop)
  return { displayed, typing }
}
