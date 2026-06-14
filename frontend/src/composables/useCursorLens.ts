import { onMounted, onBeforeUnmount, ref } from 'vue'

export const LENS_GRADIENT =
  'radial-gradient(closest-side, rgba(0,0,0,1) 0%, rgba(0,0,0,.97) 35%, rgba(0,0,0,.85) 55%, ' +
  'rgba(0,0,0,.62) 70%, rgba(0,0,0,.38) 82%, rgba(0,0,0,.20) 90%, rgba(0,0,0,.07) 96%, rgba(0,0,0,0) 100%)'

export const LEAK_RADIUS = 80

export function lensVars(x: number, y: number, r = LEAK_RADIUS): Record<string, string> {
  return { '--mpx': `${x - r}px`, '--mpy': `${y - r}px`, '--d': `${2 * r}px` }
}

/** Tracks the pointer and writes the mask vars onto `el` via rAF (one write/frame). */
export function useCursorLens(el: () => HTMLElement | null | undefined, r = LEAK_RADIUS) {
  let x = -9999, y = -9999, dirty = false, raf = 0
  const active = ref(false)
  function onMove(e: PointerEvent) { x = e.clientX; y = e.clientY; dirty = true; active.value = true }
  function frame() {
    if (dirty) {
      const node = el()
      if (node) { const v = lensVars(x, y, r); for (const k in v) node.style.setProperty(k, v[k]) }
      dirty = false
    }
    raf = requestAnimationFrame(frame)
  }
  onMounted(() => { window.addEventListener('pointermove', onMove, { passive: true }); raf = requestAnimationFrame(frame) })
  onBeforeUnmount(() => { window.removeEventListener('pointermove', onMove); cancelAnimationFrame(raf) })
  return { active }
}
