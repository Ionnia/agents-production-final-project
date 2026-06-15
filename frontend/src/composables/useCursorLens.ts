import { onMounted, onBeforeUnmount, ref } from 'vue'

// Alpha/offset stops of the reveal gradient. Scaling every alpha by a factor
// lets older trail points fade out while keeping the same falloff shape.
const STOPS: readonly [number, number][] = [
  [1, 0], [0.97, 35], [0.85, 55], [0.62, 70], [0.38, 82], [0.20, 90], [0.07, 96], [0, 100],
]

/** Reveal gradient with every alpha multiplied by `a` (0 = invisible, 1 = full). */
export function lensGradient(a = 1): string {
  const stops = STOPS.map(([v, p]) => `rgba(0,0,0,${(v * a).toFixed(3)}) ${p}%`).join(', ')
  return `radial-gradient(closest-side, ${stops})`
}

export const LENS_GRADIENT = lensGradient(1)
export const LEAK_RADIUS = 96      // reveal radius when the cursor is slow/still
export const MAX_RADIUS = 200      // reveal radius at/above MAX_SPEED
export const MAX_SPEED = 24        // px/ms cursor speed that maps to MAX_RADIUS
export const TRAIL_MS = 2048       // fade for trail points

export function lensVars(x: number, y: number, r = LEAK_RADIUS): Record<string, string> {
  return { '--mpx': `${x - r}px`, '--mpy': `${y - r}px`, '--d': `${2 * r}px` }
}

interface Pt { x: number; y: number; t: number; r: number; life: number }

/**
 * Tracks the pointer and reveals the color layer beneath it. The current point
 * stays fully revealed; recent positions form a trail whose mask alpha decays
 * with age, so a revealed streak fades out behind the cursor. Each point fades
 * over `TRAIL_MS`, and the reveal radius scales with cursor speed. The behaviour
 * is a single hover effect — no mouse-button interaction. One style write per
 * frame; the whole effect collapses to a single head point when reduced motion is on.
 */
export function useCursorLens(el: () => HTMLElement | null | undefined, r = LEAK_RADIUS) {
  const active = ref(false)
  const reduce = typeof window !== 'undefined' && typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const STEP = 48         // px between sampled trail points — fast moves are interpolated to this spacing
  const MAX_FILL = 96    // cap interpolated points per move (runaway / huge-jump guard)
  const MAX_POINTS = 512 // hard cap on live trail layers — bounds mask-string size & compositor cost
  const GAP_MS = 150     // idle gap after which we restart the trail instead of bridging
  const TELEPORT = 600   // px jump treated as a teleport (window re-entry) — don't bridge
  let cx = -9999, cy = -9999, have = false, raf = 0
  let lastX = 0, lastY = 0, lastT = 0, primed = false
  let sx = 0, sy = 0, st = 0, sHas = false // last sampled trail point (for interpolation)
  let targetR = r, headR = r // speed-driven reveal radius (eased)
  let prevTrail = false, pcx = NaN, pcy = NaN, phr = NaN // last-written state, for the idle short-circuit
  const pts: Pt[] = []

  function addPt(x: number, y: number, t: number) {
    pts.push({ x, y, t, r: headR, life: TRAIL_MS })
    if (pts.length > MAX_POINTS) pts.splice(0, pts.length - MAX_POINTS) // drop oldest excess
  }

  // Fill evenly-spaced points from the last sample to the cursor so fast moves
  // (far-apart pointer events) leave a continuous streak rather than dots.
  function fillTrail(now: number) {
    const dx = cx - sx, dy = cy - sy
    const dist = Math.hypot(dx, dy)
    if (dist < STEP) return
    if (!sHas || dist > TELEPORT || now - st > GAP_MS || dist / STEP > MAX_FILL) {
      addPt(cx, cy, now); sx = cx; sy = cy; st = now; sHas = true; return // start fresh, no bridge
    }
    const ux = dx / dist, uy = dy / dist, dt = now - st
    for (let d = STEP; d <= dist; d += STEP) addPt(sx + ux * d, sy + uy * d, st + dt * (d / dist))
    const placed = Math.floor(dist / STEP) * STEP // keep sub-STEP remainder for even spacing next move
    sx += ux * placed; sy += uy * placed; st += dt * (placed / dist)
  }

  function onMove(e: PointerEvent) {
    cx = e.clientX; cy = e.clientY; have = true
    if (!active.value) active.value = true
    const now = performance.now()
    if (primed) {
      const dt = now - lastT
      if (dt > 0) {
        const speed = Math.hypot(cx - lastX, cy - lastY) / dt // px/ms
        targetR = r + (MAX_RADIUS - r) * Math.min(1, speed / MAX_SPEED)
      }
    } else primed = true
    lastX = cx; lastY = cy; lastT = now
    if (!reduce) fillTrail(now)
  }

  function frame() {
    raf = requestAnimationFrame(frame)
    const node = el()
    if (!node || !have) return
    const now = performance.now()
    targetR += (r - targetR) * 0.05 // decay back toward the min radius when idle
    headR += (targetR - headR) * 0.25 // ease the head radius toward the target

    // Compact expired points in place (no array spread) while building the layers.
    const imgs: string[] = [], poss: string[] = [], sizes: string[] = []
    let w = 0
    for (let i = 0; i < pts.length; i++) {
      const p = pts[i]
      let a = 1 - (now - p.t) / p.life // each point fades over its own lifetime
      if (a <= 0) continue // expired — drop it
      pts[w++] = p
      a = a * a // quadratic ease for a softer tail
      const rr = p.r * (0.55 + 0.45 * a)
      imgs.push(lensGradient(a)); poss.push(`${p.x - rr}px ${p.y - rr}px`); sizes.push(`${2 * rr}px ${2 * rr}px`)
    }
    pts.length = w

    // Idle short-circuit: when the trail is empty and the head hasn't moved/resized
    // since the last write, skip the string build + style writes entirely.
    const trail = w > 0
    const headMoved = cx !== pcx || cy !== pcy || Math.abs(headR - phr) > 0.05
    if (!trail && !prevTrail && !headMoved) return
    prevTrail = trail; pcx = cx; pcy = cy; phr = headR

    // persistent fully-revealed head under the cursor (drawn even when idle)
    imgs.push(LENS_GRADIENT); poss.push(`${cx - headR}px ${cy - headR}px`); sizes.push(`${2 * headR}px ${2 * headR}px`)

    const img = imgs.join(', '), pos = poss.join(', '), size = sizes.join(', ')
    const s = node.style
    s.setProperty('-webkit-mask-image', img); s.setProperty('mask-image', img)
    s.setProperty('-webkit-mask-position', pos); s.setProperty('mask-position', pos)
    s.setProperty('-webkit-mask-size', size); s.setProperty('mask-size', size)
    s.setProperty('-webkit-mask-repeat', 'no-repeat'); s.setProperty('mask-repeat', 'no-repeat')
  }

  onMounted(() => {
    window.addEventListener('pointermove', onMove, { passive: true })
    raf = requestAnimationFrame(frame)
  })
  onBeforeUnmount(() => {
    window.removeEventListener('pointermove', onMove)
    cancelAnimationFrame(raf)
  })
  return { active }
}
