# Frontend Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full travel-planning chat frontend — glassmorphism UI, dithered backgrounds, chat with SSE + clarifying questions, side panel, plan view (MapLibre map + itinerary calendar + editing), and auth — all running end-to-end against an MSW mock of `api/openapi.yaml`.

**Architecture:** Vue 3 + `<script setup>` + TS, Vite, Tailwind v4, Pinia, Vue Router. A typed API client (types generated from the OpenAPI doc) talks to MSW handlers that implement the whole contract incl. a streamed SSE response. A full-screen `DitheredBackground` (prerendered 4K layers, CSS-mask cursor lens) sits behind a persistent app shell (menu + side panel) whose main pane is routed (auth / chat / plan).

**Tech Stack:** Vue 3.5, Vite 8, Tailwind 4, Pinia, Vue Router 4, MapLibre GL, MSW 2, openapi-typescript, Vitest + Vue Test Utils + jsdom. `@napi-rs/canvas` (prerender, already added).

**Conventions for every task:** files use `<script setup lang="ts">`; money is integer `*_rub`; the single glass token (`.glass`, Task 0.3) is reused on every translucent surface; tests run with `pnpm test`; commit after each task with the shown message.

**Already built (do not redo):** `frontend/scripts/prerender-backgrounds.mjs`, `frontend/public/backgrounds/<scene>-{mono,color}.webp` (8 scenes), `@napi-rs/canvas` dev dep + `prerender:bg` script, `.gitignore` entry for `.superpowers/`, the spec, and `docs/prototypes/final-look.html` (the visual reference — open it to see the target look/behaviour).

---

## File structure

```
frontend/
  vitest.config.ts                      test config (jsdom)
  src/
    main.ts                             mount: pinia, router, MSW bootstrap
    style.css                           reset + tailwind import + design vars (trimmed)
    styles/glass.css                   .glass token + shared surface helpers
    router/index.ts                    routes + auth guard
    App.vue                            shell: background + menu + side panel + <RouterView>
    api/
      schema.d.ts                      GENERATED from api/openapi.yaml (do not edit)
      types.ts                         friendly aliases over schema.d.ts + SSE union
      client.ts                        fetch wrapper (bearer, error envelope, pagination)
      sse.ts                           fetch-based event-stream reader
      endpoints.ts                     one function per OpenAPI operation
    mocks/
      geo.ts                           city → {lat,lng} lookup
      seed.ts                          in-memory DB seeded from data/ (typed objects)
      sse-script.ts                    scripted run → ordered SSE frames
      handlers.ts                      MSW handlers for every endpoint
      browser.ts                       setupWorker(...handlers)
    stores/
      auth.ts  sessions.ts  groups.ts  plans.ts  chat.ts
    composables/
      useCursorLens.ts                 cursor → CSS mask vars
      useToasts.ts                     error/info toasts
    components/
      background/DitheredBackground.vue
      layout/AppShell.vue MenuButton.vue SidePanel.vue
      layout/SessionList.vue GroupList.vue PlanList.vue
      ui/GlassPanel.vue Skeleton.vue EmptyState.vue ToastHost.vue
      auth/AuthView.vue
      chat/ChatView.vue ChatComposer.vue MessageList.vue MessageBubble.vue
           ClarifyingQuestion.vue PlanStatus.vue
      plan/PlanView.vue MapView.vue ItineraryView.vue OfferCard.vue PlanEditBar.vue
  test/ (co-located *.spec.ts next to sources)
```

**Removed in Task 9.2:** `src/components/PageBackground/**`, `src/assets/images/**`, `src/assets/images_backup/**`, `src/assets/hero.png`, `src/SPEC.md`.

---

## Parallelization map (for subagent dispatch)

- **Phase 0 is a hard barrier** — every later task imports its types/tokens/router/stores-scaffold. Do it first, single-threaded.
- After Phase 0, these tracks are independent and can run in parallel: **A** Background (Phase 1), **B** API client + SSE (Phase 2) → Mock (Phase 3) → Stores (Phase 4) [B is sequential within itself], **C** UI primitives (Task 0.5).
- Phases 5–8 (feature views) depend on Phase 4 stores; within them each view is independent.
- Phase 9 is the closing barrier.

---

## Phase 0 — Setup & shared contracts (single-threaded barrier)

### Task 0.1: Install dependencies and test tooling

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/vitest.config.ts`

- [ ] **Step 1: Install runtime + dev deps**

Run:
```bash
cd frontend
pnpm add pinia vue-router maplibre-gl
pnpm add -D msw openapi-typescript vitest @vue/test-utils jsdom @vitest/coverage-v8
```

- [ ] **Step 2: Add scripts to `package.json`**

Add to the `"scripts"` block (keep existing `dev`/`build`/`preview`/`prerender:bg`):
```json
"test": "vitest run",
"test:watch": "vitest",
"gen:api": "openapi-typescript ../api/openapi.yaml -o src/api/schema.d.ts",
"mock:init": "msw init public --save"
```

- [ ] **Step 3: Create `frontend/vitest.config.ts`**

```ts
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: [],
    include: ['src/**/*.spec.ts'],
  },
})
```

- [ ] **Step 4: Verify the test runner boots**

Create a throwaway `src/sanity.spec.ts`:
```ts
import { it, expect } from 'vitest'
it('runs', () => { expect(1 + 1).toBe(2) })
```
Run: `pnpm test`
Expected: 1 passed. Then delete `src/sanity.spec.ts`.

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/pnpm-lock.yaml frontend/vitest.config.ts
git commit -m "chore(frontend): add pinia, router, maplibre, msw, vitest tooling"
```

---

### Task 0.2: Generate API types and friendly aliases

**Files:**
- Create (generated): `frontend/src/api/schema.d.ts`
- Create: `frontend/src/api/types.ts`

- [ ] **Step 1: Generate types from the OpenAPI doc**

Run: `cd frontend && pnpm gen:api`
Expected: `src/api/schema.d.ts` created, no errors.

- [ ] **Step 2: Create `src/api/types.ts` (friendly aliases + SSE union)**

```ts
import type { components } from './schema'

type S = components['schemas']

export type User = S['User']
export type TokenBundle = S['TokenBundle']
export type RegisterRequest = S['RegisterRequest']
export type LoginRequest = S['LoginRequest']
export type LoginResponse = S['LoginResponse']
export type RegisterResponse = S['RegisterResponse']
export type AccessTokenResponse = S['AccessTokenResponse']

export type ChatRequest = S['ChatRequest']
export type ChatAccepted = S['ChatAccepted']
export type StreamTicket = S['StreamTicket']
export type CancelResponse = S['CancelResponse']

export type Message = S['Message']
export type ClarifyingQuestion = S['ClarifyingQuestion']
export type QuestionOption = S['QuestionOption']
export type MapPoint = S['MapPoint']

export type SessionSummary = S['SessionSummary']
export type SessionList = S['SessionList']
export type SessionDetail = S['SessionDetail']
export type GroupSummary = S['GroupSummary']
export type GroupList = S['GroupList']
export type Group = S['Group']
export type Member = S['Member']
export type Preference = S['Preference']
export type CreateGroupRequest = S['CreateGroupRequest']
export type GroupPreferences = S['GroupPreferences']

export type PlanStatus = S['PlanStatus']
export type PlanBuildStatus = S['PlanBuildStatus']
export type PlanSummary = S['PlanSummary']
export type PlanList = S['PlanList']
export type Plan = S['Plan']
export type PlanItems = S['PlanItems']
export type FlightSel = S['FlightSel']
export type HotelSel = S['HotelSel']
export type TourSel = S['TourSel']
export type PlanMap = S['PlanMap']
export type PlanCalendar = S['PlanCalendar']
export type CalendarEvent = S['CalendarEvent']
export type ModifyRequest = S['ModifyRequest']
export type ModifyAccepted = S['ModifyAccepted']
export type AddPoint = S['AddPoint']
export type ApiError = S['Error']

// SSE: discriminate on the event NAME (not a body field).
export type SseEvent =
  | { event: 'run_status'; data: S['RunStatusEvent'] }
  | { event: 'message_delta'; data: S['MessageDeltaEvent'] }
  | { event: 'message'; data: S['MessageEvent'] }
  | { event: 'clarifying_question'; data: S['ClarifyingQuestionEvent'] }
  | { event: 'plan_status'; data: S['PlanStatusEvent'] }
  | { event: 'map'; data: S['MapEvent'] }
  | { event: 'error'; data: S['ErrorEvent'] }
export type SseEventName = SseEvent['event']
```

- [ ] **Step 3: Typecheck**

Run: `cd frontend && pnpm vue-tsc --noEmit`
Expected: no errors (the file only re-exports generated types).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/schema.d.ts frontend/src/api/types.ts
git commit -m "feat(frontend): generate API types and friendly aliases"
```

---

### Task 0.3: Glass design tokens & base styles

**Files:**
- Create: `frontend/src/styles/glass.css`
- Modify: `frontend/src/style.css`

- [ ] **Step 1: Create `src/styles/glass.css`** (the single shared glass token — from the approved prototype)

```css
:root {
  --accent: #d97757;
  --accent-press: #cf5f3f;
  --bg-base: #0c0a08;
  --ink: #241c14;                 /* text on frosted glass */
  --ink-soft: rgba(40, 30, 20, 0.55);

  /* locked glass spec: white 30% · blur 7px · saturate 100% · no border */
  --glass-bg: rgba(255, 255, 255, 0.30);
  --glass-blur: 7px;
  --glass-saturate: 1;
  --glass-shadow: 0 18px 50px rgba(0, 0, 0, 0.35);
}

.glass {
  background: var(--glass-bg);
  -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
  backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
  box-shadow: var(--glass-shadow);
  color: var(--ink);
}

/* darker glass variant for controls that sit on light frost (e.g. toasts) */
.glass-dark {
  background: rgba(14, 11, 9, 0.82);
  -webkit-backdrop-filter: blur(14px);
  backdrop-filter: blur(14px);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: #ece4d6;
}

@media (prefers-reduced-motion: reduce) {
  * { animation-duration: 0.001ms !important; transition-duration: 0.001ms !important; }
}
```

- [ ] **Step 2: Replace `src/style.css`** with a trimmed base (remove the old scrapbook keyframes/hero rules)

```css
@import 'tailwindcss';
@import './styles/glass.css';

html, body, #app { height: 100%; }
body {
  margin: 0;
  background: var(--bg-base);
  color: #ece4d6;
  font: 15px/1.5 ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
  -webkit-font-smoothing: antialiased;
  overflow: hidden;            /* the app manages its own scroll regions */
}
*, *::before, *::after { box-sizing: border-box; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
```

- [ ] **Step 3: Verify dev server still boots** (App.vue is replaced in 0.4; for now just ensure no CSS import error)

Run: `cd frontend && pnpm vue-tsc --noEmit` → no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/styles/glass.css frontend/src/style.css
git commit -m "feat(frontend): glass design tokens and trimmed base styles"
```

---

### Task 0.4: Router, Pinia, and App shell skeleton

**Files:**
- Create: `frontend/src/router/index.ts`
- Modify: `frontend/src/main.ts`
- Modify: `frontend/src/App.vue`
- Create: `frontend/src/components/layout/AppShell.vue`

- [ ] **Step 1: Create `src/router/index.ts`** (guard reads the auth store lazily to avoid import cycles)

```ts
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('../components/auth/AuthView.vue'), meta: { public: true } },
    { path: '/', name: 'chat', component: () => import('../components/chat/ChatView.vue') },
    { path: '/c/:sessionId', name: 'session', component: () => import('../components/chat/ChatView.vue'), props: true },
    { path: '/plans/:planId', name: 'plan', component: () => import('../components/plan/PlanView.vue'), props: true },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  const { useAuthStore } = await import('../stores/auth')
  const auth = useAuthStore()
  if (!auth.ready) await auth.restore()
  if (!to.meta.public && !auth.isAuthenticated) return { name: 'login', query: { redirect: to.fullPath } }
  if (to.name === 'login' && auth.isAuthenticated) return { path: '/' }
  return true
})

export default router
```

- [ ] **Step 2: Replace `src/main.ts`** (bootstrap MSW before mount in dev/demo)

```ts
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import App from './App.vue'
import router from './router'

async function bootstrap() {
  if (import.meta.env.DEV || import.meta.env.VITE_USE_MOCKS === 'true') {
    const { worker } = await import('./mocks/browser')
    await worker.start({ onUnhandledRequest: 'bypass' })
  }
  createApp(App).use(createPinia()).use(router).mount('#app')
}
bootstrap()
```

- [ ] **Step 3: Create `src/components/layout/AppShell.vue`** (persistent chrome around the routed pane)

```vue
<script setup lang="ts">
import DitheredBackground from '../background/DitheredBackground.vue'
import MenuButton from './MenuButton.vue'
import SidePanel from './SidePanel.vue'
import ToastHost from '../ui/ToastHost.vue'
import { ref } from 'vue'
const panelOpen = ref(false)
</script>

<template>
  <DitheredBackground />
  <MenuButton @toggle="panelOpen = !panelOpen" />
  <SidePanel :open="panelOpen" @close="panelOpen = false" />
  <main class="pane"><slot /></main>
  <ToastHost />
</template>

<style scoped>
.pane { position: fixed; inset: 0; z-index: 1; }
</style>
```

- [ ] **Step 4: Replace `src/App.vue`**

```vue
<script setup lang="ts">
import AppShell from './components/layout/AppShell.vue'
</script>

<template>
  <AppShell>
    <RouterView />
  </AppShell>
</template>
```

- [ ] **Step 5: Create placeholder feature components so the router resolves**

Create each of these as a one-line stub (replaced in later phases) so `pnpm dev`/tests don't fail on missing imports:
`src/components/auth/AuthView.vue`, `src/components/chat/ChatView.vue`, `src/components/plan/PlanView.vue`, `src/components/layout/MenuButton.vue`, `src/components/layout/SidePanel.vue`, `src/components/background/DitheredBackground.vue`, `src/components/ui/ToastHost.vue`.

Each stub:
```vue
<template><div /></template>
```
For `MenuButton.vue` add the emit so AppShell typechecks:
```vue
<script setup lang="ts">defineEmits<{ toggle: [] }>()</script>
<template><button type="button" @click="$emit('toggle')" /></template>
```
For `SidePanel.vue`:
```vue
<script setup lang="ts">defineProps<{ open: boolean }>(); defineEmits<{ close: [] }>()</script>
<template><aside v-show="open" /></template>
```

- [ ] **Step 6: Typecheck**

Run: `cd frontend && pnpm vue-tsc --noEmit`
Expected: no errors. (Auth store referenced by the guard is created in Task 4.1; until then comment out the guard body's store use OR implement 4.1 before running dev. Typecheck passes because the import is dynamic.)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/main.ts frontend/src/App.vue frontend/src/router frontend/src/components
git commit -m "feat(frontend): router, pinia bootstrap, app shell skeleton + stubs"
```

---

### Task 0.5: UI primitives (GlassPanel, Skeleton, EmptyState, toasts)

**Files:**
- Create: `frontend/src/composables/useToasts.ts` + `useToasts.spec.ts`
- Create: `frontend/src/components/ui/GlassPanel.vue`, `Skeleton.vue`, `EmptyState.vue`, `ToastHost.vue` (replaces stub)

- [ ] **Step 1: Write failing test for the toast store**

`src/composables/useToasts.spec.ts`:
```ts
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
```

- [ ] **Step 2: Run it — expect FAIL** (`useToasts` not found). `pnpm test useToasts`

- [ ] **Step 3: Implement `src/composables/useToasts.ts`**

```ts
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
```

- [ ] **Step 4: Run test — expect PASS.** `pnpm test useToasts`

- [ ] **Step 5: Implement the UI primitives**

`src/components/ui/GlassPanel.vue`:
```vue
<script setup lang="ts">
withDefaults(defineProps<{ radius?: string }>(), { radius: '18px' })
</script>
<template>
  <div class="glass" :style="{ borderRadius: radius }"><slot /></div>
</template>
```

`src/components/ui/Skeleton.vue`:
```vue
<script setup lang="ts">
withDefaults(defineProps<{ w?: string; h?: string }>(), { w: '100%', h: '14px' })
</script>
<template><div class="sk" :style="{ width: w, height: h }" /></template>
<style scoped>
.sk { border-radius: 8px; background: linear-gradient(90deg, rgba(255,255,255,.10), rgba(255,255,255,.22), rgba(255,255,255,.10)); background-size: 200% 100%; animation: sh 1.2s infinite; }
@keyframes sh { from { background-position: 200% 0 } to { background-position: -200% 0 } }
</style>
```

`src/components/ui/EmptyState.vue`:
```vue
<script setup lang="ts">defineProps<{ title: string; hint?: string }>()</script>
<template>
  <div class="empty">
    <p class="t">{{ title }}</p>
    <p v-if="hint" class="h">{{ hint }}</p>
  </div>
</template>
<style scoped>
.empty { text-align: center; padding: 28px 16px; color: #cfc7ba; }
.t { font-weight: 600; color: #fff; margin: 0 0 4px; }
.h { margin: 0; font-size: 13px; opacity: .7; }
</style>
```

`src/components/ui/ToastHost.vue` (replace stub):
```vue
<script setup lang="ts">
import { useToasts } from '../../composables/useToasts'
const { toasts, remove } = useToasts()
</script>
<template>
  <div class="host">
    <div v-for="t in toasts" :key="t.id" class="toast glass-dark" :data-kind="t.kind" @click="remove(t.id)">
      {{ t.text }}
    </div>
  </div>
</template>
<style scoped>
.host { position: fixed; bottom: 18px; left: 50%; transform: translateX(-50%); z-index: 100; display: flex; flex-direction: column; gap: 8px; }
.toast { padding: 10px 16px; border-radius: 10px; font-size: 14px; cursor: pointer; max-width: 90vw; }
.toast[data-kind='error'] { border-color: rgba(217,119,87,.6); color: #f3c0ab; }
</style>
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/composables/useToasts.* frontend/src/components/ui
git commit -m "feat(frontend): UI primitives (glass panel, skeleton, empty state, toasts)"
```

---

## Phase 1 — Background (Track A)

### Task 1.1: useCursorLens composable

**Files:**
- Create: `frontend/src/composables/useCursorLens.ts` + `useCursorLens.spec.ts`

- [ ] **Step 1: Write failing test**

`src/composables/useCursorLens.spec.ts`:
```ts
import { it, expect } from 'vitest'
import { lensVars } from './useCursorLens'

it('computes mask vars centered on the cursor', () => {
  const v = lensVars(200, 100, 80)
  expect(v['--mpx']).toBe('120px')   // 200 - 80
  expect(v['--mpy']).toBe('20px')    // 100 - 80
  expect(v['--d']).toBe('160px')     // 2 * 80
})
```

- [ ] **Step 2: Run — expect FAIL.** `pnpm test useCursorLens`

- [ ] **Step 3: Implement `src/composables/useCursorLens.ts`**

```ts
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
```

- [ ] **Step 4: Run — expect PASS.** `pnpm test useCursorLens`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/useCursorLens.*
git commit -m "feat(frontend): cursor lens composable"
```

---

### Task 1.2: DitheredBackground component (and remove old system)

**Files:**
- Replace: `frontend/src/components/background/DitheredBackground.vue` (was a stub)

- [ ] **Step 1: Implement `DitheredBackground.vue`** (random scene on load, two prerendered layers, masked color layer)

```vue
<script setup lang="ts">
import { onMounted, ref, useTemplateRef } from 'vue'
import { useCursorLens, LENS_GRADIENT } from '../../composables/useCursorLens'

const SCENES = ['france', 'greece', 'italy', 'japan', 'china', 'india', 'russia', 'usa'] as const
const scene = SCENES[Math.floor(Math.random() * SCENES.length)]
const base = `/backgrounds/${scene}-mono.webp`
const color = `/backgrounds/${scene}-color.webp`

const colorEl = useTemplateRef<HTMLImageElement>('colorEl')
useCursorLens(() => colorEl.value)
const loaded = ref(false)
</script>

<template>
  <div class="bg" aria-hidden="true">
    <img class="layer" :src="base" alt="" @load="loaded = true" />
    <img ref="colorEl" class="layer color" :src="color" alt="" :style="{ '--lens': LENS_GRADIENT }" />
  </div>
</template>

<style scoped>
.bg { position: fixed; inset: 0; z-index: 0; background: var(--bg-base); }
.layer { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
.color {
  -webkit-mask-image: var(--lens); mask-image: var(--lens);
  -webkit-mask-repeat: no-repeat; mask-repeat: no-repeat;
  -webkit-mask-size: var(--d, 0) var(--d, 0); mask-size: var(--d, 0) var(--d, 0);
  -webkit-mask-position: var(--mpx, -9999px) var(--mpy, -9999px); mask-position: var(--mpx, -9999px) var(--mpy, -9999px);
}
</style>
```

- [ ] **Step 2: Manually verify in the browser**

Run: `cd frontend && pnpm dev`, open the app. Expected: a random dithered scene fills the screen; moving the mouse leaks color near the cursor; refresh changes the scene. (If the page is blank because the auth guard redirects to a stub `/login`, that's fine — the background still renders behind it.)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/background/DitheredBackground.vue
git commit -m "feat(frontend): dithered background with cursor color-lens"
```

> Old `PageBackground/**` and image assets are deleted in Task 9.2 (after nothing imports them).

---

## Phase 2 — API client + SSE (Track B, sequential)

### Task 2.1: HTTP client

**Files:**
- Create: `frontend/src/api/client.ts` + `client.spec.ts`

- [ ] **Step 1: Write failing tests**

`src/api/client.spec.ts`:
```ts
import { it, expect, vi, beforeEach } from 'vitest'
import { ApiClientError, createClient } from './client'

beforeEach(() => { localStorage.clear() })

it('attaches bearer token and parses JSON', async () => {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify({ ok: 1 }), { status: 200, headers: { 'content-type': 'application/json' } }))
  const c = createClient({ baseUrl: '/api/v1', fetch: fetchMock, getToken: () => 'tok' })
  const out = await c.get<{ ok: number }>('/auth/me')
  expect(out.ok).toBe(1)
  const req = fetchMock.mock.calls[0][0] as Request
  expect(req.headers.get('authorization')).toBe('Bearer tok')
})

it('throws ApiClientError carrying the error envelope', async () => {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify({ error: { code: 'not_found', message: 'nope' } }), { status: 404, headers: { 'content-type': 'application/json' } }))
  const c = createClient({ baseUrl: '/api/v1', fetch: fetchMock, getToken: () => null })
  await expect(c.get('/x')).rejects.toMatchObject({ code: 'not_found', status: 404 })
})
```

- [ ] **Step 2: Run — expect FAIL.** `pnpm test client`

- [ ] **Step 3: Implement `src/api/client.ts`**

```ts
import type { ApiError } from './types'

export class ApiClientError extends Error {
  constructor(public status: number, public code: string, message: string, public details?: unknown) { super(message) }
}

export interface ClientOptions {
  baseUrl?: string
  fetch?: typeof fetch
  getToken?: () => string | null
}

export function createClient(opts: ClientOptions = {}) {
  const baseUrl = opts.baseUrl ?? '/api/v1'
  const f = opts.fetch ?? globalThis.fetch.bind(globalThis)
  const getToken = opts.getToken ?? (() => null)

  async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const headers: Record<string, string> = {}
    const token = getToken()
    if (token) headers.authorization = `Bearer ${token}`
    if (body !== undefined) headers['content-type'] = 'application/json'
    const res = await f(new Request(baseUrl + path, { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined }))
    if (res.status === 204) return undefined as T
    const isJson = res.headers.get('content-type')?.includes('application/json')
    const payload = isJson ? await res.json() : undefined
    if (!res.ok) {
      const e = (payload as ApiError | undefined)?.error
      throw new ApiClientError(res.status, e?.code ?? 'internal', e?.message ?? res.statusText, e?.details)
    }
    return payload as T
  }

  return {
    get: <T>(p: string) => request<T>('GET', p),
    post: <T>(p: string, b?: unknown) => request<T>('POST', p, b),
    raw: f,
    baseUrl,
  }
}
```

- [ ] **Step 4: Run — expect PASS.** `pnpm test client`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/client.*
git commit -m "feat(frontend): typed HTTP client with error-envelope handling"
```

---

### Task 2.2: SSE-over-fetch reader

**Files:**
- Create: `frontend/src/api/sse.ts` + `sse.spec.ts`

- [ ] **Step 1: Write failing test** (feed a fake event-stream body, assert parsed typed frames)

`src/api/sse.spec.ts`:
```ts
import { it, expect } from 'vitest'
import { parseEventStream } from './sse'

function streamOf(text: string): ReadableStream<Uint8Array> {
  const enc = new TextEncoder()
  return new ReadableStream({ start(c) { c.enqueue(enc.encode(text)); c.close() } })
}

it('parses named SSE frames into typed events', async () => {
  const body = [
    'id: 1', 'event: run_status', 'data: {"run_id":"r1","status":"started"}', '',
    'event: message_delta', 'data: {"run_id":"r1","message_id":"m1","delta":"Hi"}', '',
    '',
  ].join('\n')
  const out: any[] = []
  for await (const ev of parseEventStream(streamOf(body))) out.push(ev)
  expect(out[0]).toEqual({ event: 'run_status', data: { run_id: 'r1', status: 'started' } })
  expect(out[1].data.delta).toBe('Hi')
})
```

- [ ] **Step 2: Run — expect FAIL.** `pnpm test sse`

- [ ] **Step 3: Implement `src/api/sse.ts`**

```ts
import type { SseEvent } from './types'

/** Parse a text/event-stream ReadableStream into typed {event,data} frames. */
export async function* parseEventStream(body: ReadableStream<Uint8Array>): AsyncGenerator<SseEvent> {
  const reader = body.getReader()
  const dec = new TextDecoder()
  let buf = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })
    let idx: number
    while ((idx = buf.indexOf('\n\n')) !== -1) {
      const frame = buf.slice(0, idx)
      buf = buf.slice(idx + 2)
      const ev = parseFrame(frame)
      if (ev) yield ev
    }
  }
}

function parseFrame(frame: string): SseEvent | null {
  let event = 'message'
  const dataLines: string[] = []
  for (const line of frame.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
    // id:/retry: ignored here
  }
  if (!dataLines.length) return null
  try { return { event, data: JSON.parse(dataLines.join('\n')) } as SseEvent }
  catch { return null }
}

export interface StreamRunArgs { baseUrl: string; runId: string; ticket: string; signal?: AbortSignal; fetch?: typeof fetch }

/** Open the run stream and yield typed events until the connection closes. */
export async function* streamRun(args: StreamRunArgs): AsyncGenerator<SseEvent> {
  const f = args.fetch ?? globalThis.fetch.bind(globalThis)
  const res = await f(`${args.baseUrl}/chat/${args.runId}/stream?ticket=${encodeURIComponent(args.ticket)}`, {
    headers: { accept: 'text/event-stream' }, signal: args.signal,
  })
  if (!res.ok || !res.body) throw new Error(`stream failed: ${res.status}`)
  yield* parseEventStream(res.body)
}
```

- [ ] **Step 4: Run — expect PASS.** `pnpm test sse`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/sse.*
git commit -m "feat(frontend): fetch-based SSE reader for run events"
```

---

### Task 2.3: Endpoints module

**Files:**
- Create: `frontend/src/api/endpoints.ts`

- [ ] **Step 1: Implement `src/api/endpoints.ts`** (one typed function per operation; uses the shared client)

```ts
import { createClient } from './client'
import type {
  LoginRequest, LoginResponse, RegisterRequest, RegisterResponse, AccessTokenResponse, User,
  ChatRequest, ChatAccepted, StreamTicket, CancelResponse,
  SessionList, SessionDetail, GroupList, Group, CreateGroupRequest, GroupPreferences,
  PlanList, Plan, PlanMap, PlanCalendar, ModifyRequest, ModifyAccepted,
} from './types'

let tokenGetter: () => string | null = () => null
export function setTokenGetter(fn: () => string | null) { tokenGetter = fn }

export const client = createClient({ getToken: () => tokenGetter() })

export const api = {
  // Auth
  register: (b: RegisterRequest) => client.post<RegisterResponse>('/auth/register', b),
  login: (b: LoginRequest) => client.post<LoginResponse>('/auth/login', b),
  refresh: (refresh_token: string) => client.post<AccessTokenResponse>('/auth/refresh', { refresh_token }),
  logout: (refresh_token: string) => client.post<void>('/auth/logout', { refresh_token }),
  me: () => client.get<User>('/auth/me'),
  // Chat / run
  chat: (b: ChatRequest) => client.post<ChatAccepted>('/chat', b),
  streamTicket: (runId: string) => client.post<StreamTicket>(`/chat/${runId}/stream-ticket`),
  cancel: (runId: string) => client.post<CancelResponse>(`/chat/${runId}/cancel`),
  // Sessions
  sessions: (limit = 20, offset = 0) => client.get<SessionList>(`/sessions?limit=${limit}&offset=${offset}`),
  session: (id: string) => client.get<SessionDetail>(`/sessions/${id}`),
  // Groups
  groups: (limit = 20, offset = 0) => client.get<GroupList>(`/groups?limit=${limit}&offset=${offset}`),
  group: (id: string) => client.get<Group>(`/groups/${id}`),
  createGroup: (b: CreateGroupRequest) => client.post<Group>('/groups', b),
  groupPreferences: (id: string) => client.get<GroupPreferences>(`/groups/${id}/preferences`),
  groupPlans: (id: string) => client.get<PlanList>(`/groups/${id}/plans`),
  // Plans
  plan: (id: string) => client.get<Plan>(`/plans/${id}`),
  planMap: (id: string) => client.get<PlanMap>(`/plans/${id}/map`),
  planCalendar: (id: string) => client.get<PlanCalendar>(`/plans/${id}/calendar`),
  acceptPlan: (id: string) => client.post<Plan>(`/plans/${id}/accept`),
  rejectPlan: (id: string, reason?: string) => client.post<Plan>(`/plans/${id}/reject`, { reason }),
  modifyPlan: (id: string, b: ModifyRequest) => client.post<ModifyAccepted>(`/plans/${id}/modify`, b),
}
```

- [ ] **Step 2: Typecheck.** `cd frontend && pnpm vue-tsc --noEmit` → no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/endpoints.ts
git commit -m "feat(frontend): typed API endpoints module"
```

---

## Phase 3 — Mock backend (Track B, sequential; needs Phase 2)

### Task 3.1: Geo lookup + seed database

**Files:**
- Create: `frontend/src/mocks/geo.ts`
- Create: `frontend/src/mocks/seed.ts` + `seed.spec.ts`

- [ ] **Step 1: Create `src/mocks/geo.ts`** (city → coordinates; covers the seed cities)

```ts
export const GEO: Record<string, { lat: number; lng: number }> = {
  'Москва': { lat: 55.7558, lng: 37.6173 },
  'Санкт-Петербург': { lat: 59.9311, lng: 30.3609 },
  'Сочи': { lat: 43.5855, lng: 39.7231 },
  'Париж': { lat: 48.8566, lng: 2.3522 },
  'Рим': { lat: 41.9028, lng: 12.4964 },
  'Флоренция': { lat: 43.7696, lng: 11.2558 },
  'Афины': { lat: 37.9838, lng: 23.7275 },
  'Санторини': { lat: 36.3932, lng: 25.4615 },
  'Токио': { lat: 35.6762, lng: 139.6503 },
  'Пекин': { lat: 39.9042, lng: 116.4074 },
  'Дели': { lat: 28.6139, lng: 77.2090 },
  'Нью-Йорк': { lat: 40.7128, lng: -74.0060 },
}
export const DEFAULT_GEO = { lat: 48.0, lng: 16.0 }
export function geo(city?: string) { return (city && GEO[city]) || DEFAULT_GEO }
```

- [ ] **Step 2: Write failing test for the seed factory**

`src/mocks/seed.spec.ts`:
```ts
import { it, expect } from 'vitest'
import { createDb } from './seed'

it('seeds groups, sessions and a ready plan with map points', () => {
  const db = createDb()
  expect(db.groups.length).toBeGreaterThan(0)
  expect(db.sessions.length).toBeGreaterThan(0)
  const plan = db.plans[0]
  expect(plan.status).toBe('ready')
  expect(plan.map_points.length).toBeGreaterThanOrEqual(2)
  expect(plan.map_points[0].kind).toBe('origin')
})
```

- [ ] **Step 3: Run — expect FAIL.** `pnpm test seed`

- [ ] **Step 4: Implement `src/mocks/seed.ts`** (typed in-memory DB; ids stable for deep-links)

```ts
import type { User, Group, SessionSummary, SessionDetail, Message, Plan, MapPoint } from '../api/types'
import { geo } from './geo'

export interface Db {
  user: User
  password: string
  groups: Group[]
  sessions: SessionDetail[]
  plans: Plan[]
  refreshTokens: Set<string>
}

const now = '2026-06-14T09:00:00Z'
function point(name: string, kind: MapPoint['kind'], order: number): MapPoint {
  const g = geo(name); return { id: `mp-${order}-${name}`, name, kind, lat: g.lat, lng: g.lng, order }
}

export function createDb(): Db {
  const user: User = { id: 'u-1', name: 'Алекс', email: 'demo@travel.app', created_at: now }

  const groups: Group[] = [
    { id: 'G-0001', name: 'Семья Ивановых', budget_rub: 200000, origin_city: 'Москва', destination: 'Рим',
      start_date: '2026-09-05', end_date: '2026-09-12', created_at: now, updated_at: now,
      members: [
        { id: 'm-1', full_name: 'Иван Иванов', age: 41, role_in_group: 'parent', home_airport: 'SVO',
          preferences: [{ id: 'p-1', type: 'hotel_rating', value: '4+' }] },
        { id: 'm-2', full_name: 'Анна Иванова', age: 39, role_in_group: 'parent', preferences: [] },
        { id: 'm-3', full_name: 'Миша', age: 9, role_in_group: 'child', preferences: [] },
        { id: 'm-4', full_name: 'Катя', age: 6, role_in_group: 'child', preferences: [] },
      ] },
    { id: 'G-0002', name: 'Друзья — Бали', budget_rub: 350000, origin_city: 'Москва', destination: 'Санторини',
      created_at: now, updated_at: now,
      members: [
        { id: 'm-5', full_name: 'Олег', age: 28, role_in_group: 'lead', preferences: [] },
        { id: 'm-6', full_name: 'Дима', age: 30, preferences: [] },
      ] },
  ]

  const plan: Plan = {
    id: 'PL-0001', session_id: 'S-0001', group_id: 'G-0001', run_id: 'run-seed', status: 'ready',
    summary: 'Рим → Флоренция, 7 ночей, перелёт + отель 4★',
    destination: 'Рим', start_date: '2026-09-05', end_date: '2026-09-12',
    decision_rationale: 'Прямой рейс в пределах бюджета, отель 4★ с завтраком и бесплатной отменой, тур во Флоренцию на 1 день.',
    estimated_total_rub: 184500,
    items: {
      flight: { flight_id: 'F-101', origin_city: 'Москва', destination: 'Рим', price_rub: 41200, baggage_included: true, stops: 0, departure_time: '10:20', arrival_time: '13:50', fare_type: 'standard' },
      hotel: { hotel_id: 'H-77', destination: 'Рим', stars: 4, price_per_night_rub: 12400, nights: 7, breakfast_included: true, free_cancellation: true, rating: 8.7 },
      tour: { tour_id: 'T-12', destination: 'Флоренция', total_price_rub: 15800, includes_flight: false, includes_transfer: true },
    },
    map_points: [point('Москва', 'origin', 0), point('Рим', 'destination', 1), point('Флоренция', 'stop', 2)],
    created_at: now, updated_at: now,
  }

  const messages: Message[] = [
    { id: 'msg-1', role: 'user', content: 'Хотим в Рим в сентябре, бюджет 200к на семью из Москвы.', created_at: now },
    { id: 'msg-2', role: 'assistant', content: 'Готово! Собрал маршрут Рим → Флоренция на 7 ночей.', created_at: now, run_id: 'run-seed', plan_ref: { plan_id: 'PL-0001', status: 'ready' } },
  ]
  const sessions: SessionDetail[] = [
    { id: 'S-0001', summary: 'Рим в сентябре, бюджет 200к', created_at: now, updated_at: now, group_id: 'G-0001',
      messages, plans: [{ plan_id: 'PL-0001', status: 'ready', destination: 'Рим', estimated_total_rub: 184500, created_at: now }] },
    { id: 'S-0002', summary: 'Острова Греции', created_at: now, updated_at: now, group_id: 'G-0002', messages: [], plans: [] },
  ]

  return { user, password: 'password', groups, sessions, plans: [plan], refreshTokens: new Set() }
}

export function sessionSummary(s: SessionDetail): SessionSummary {
  return { id: s.id, summary: s.summary, created_at: s.created_at, updated_at: s.updated_at,
    group_id: s.group_id, last_message_preview: s.messages.at(-1)?.content,
    latest_plan_id: s.plans.at(-1)?.plan_id, plan_status: s.plans.at(-1)?.status }
}
```

- [ ] **Step 5: Run — expect PASS.** `pnpm test seed`

- [ ] **Step 6: Commit**

```bash
git add frontend/src/mocks/geo.ts frontend/src/mocks/seed.*
git commit -m "feat(frontend): mock seed database and geo lookup"
```

---

### Task 3.2: Scripted SSE run

**Files:**
- Create: `frontend/src/mocks/sse-script.ts` + `sse-script.spec.ts`

- [ ] **Step 1: Write failing test**

`src/mocks/sse-script.spec.ts`:
```ts
import { it, expect } from 'vitest'
import { buildRunFrames } from './sse-script'

it('first message run asks then builds a plan, terminal completed', () => {
  const frames = buildRunFrames({ runId: 'r1', planId: 'PL-9', kind: 'first', text: 'Рим' })
  const names = frames.map(f => f.event)
  expect(names[0]).toBe('run_status')
  expect(names).toContain('clarifying_question')
  expect(names).toContain('plan_status')
  expect(names).toContain('map')
  expect(names.at(-1)).toBe('run_status')
  expect((frames.at(-1)!.data as any).status).toBe('completed')
})
```

- [ ] **Step 2: Run — expect FAIL.** `pnpm test sse-script`

- [ ] **Step 3: Implement `src/mocks/sse-script.ts`** (returns ordered frames; the handler serialises + paces them)

```ts
import type { SseEvent, MapPoint } from '../api/types'
import { geo } from './geo'

export interface RunSpec { runId: string; planId: string; kind: 'first' | 'answer' | 'rebuild'; text?: string; points?: MapPoint[] }

const mp = (name: string, kind: MapPoint['kind'], order: number): MapPoint => {
  const g = geo(name); return { id: `mp-${order}-${name}`, name, kind, lat: g.lat, lng: g.lng, order }
}

export function buildRunFrames(spec: RunSpec): SseEvent[] {
  const { runId, planId } = spec
  const frames: SseEvent[] = [{ event: 'run_status', data: { run_id: runId, status: 'started' } }]
  const reply = 'Отличный выбор! Подбираю оптимальные варианты по вашему бюджету…'
  for (const chunk of reply.match(/.{1,18}/g) ?? [reply])
    frames.push({ event: 'message_delta', data: { run_id: runId, message_id: 'am-' + runId, delta: chunk } })

  if (spec.kind === 'first') {
    frames.push({ event: 'clarifying_question', data: { run_id: runId, question: {
      id: 'q-' + runId, text: 'Какой формат отдыха предпочитаете?', allow_freeform: true,
      options: [{ id: 'opt-beach', label: 'Пляжный отдых' }, { id: 'opt-city', label: 'Город + море' }, { id: 'opt-islands', label: 'Острова' }] } } })
    frames.push({ event: 'run_status', data: { run_id: runId, status: 'completed' } })
    return frames
  }

  // answer / rebuild → build the plan
  frames.push({ event: 'plan_status', data: { run_id: runId, plan_id: planId, status: 'building' } })
  const points = spec.points ?? [mp('Москва', 'origin', 0), mp('Рим', 'destination', 1), mp('Флоренция', 'stop', 2)]
  frames.push({ event: 'map', data: { run_id: runId, plan_id: planId, points } })
  frames.push({ event: 'plan_status', data: { run_id: runId, plan_id: planId, status: 'ready' } })
  frames.push({ event: 'message', data: { run_id: runId, message: {
    id: 'am-' + runId, role: 'assistant', content: 'Готово! Маршрут собран — откройте план, чтобы посмотреть карту и смету.',
    created_at: new Date().toISOString(), run_id: runId, plan_ref: { plan_id: planId, status: 'ready' } } } })
  frames.push({ event: 'run_status', data: { run_id: runId, status: 'completed' } })
  return frames
}
```

- [ ] **Step 4: Run — expect PASS.** `pnpm test sse-script`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/mocks/sse-script.*
git commit -m "feat(frontend): scripted SSE run frames for the mock"
```

---

### Task 3.3: MSW handlers

**Files:**
- Create: `frontend/src/mocks/handlers.ts` + `handlers.spec.ts`
- Create: `frontend/src/mocks/browser.ts`

- [ ] **Step 1: Write failing test** (drive handlers with `@mswjs/interceptors` via the node server)

`src/mocks/handlers.spec.ts`:
```ts
import { it, expect, beforeAll, afterAll } from 'vitest'
import { setupServer } from 'msw/node'
import { handlers } from './handlers'

const server = setupServer(...handlers)
beforeAll(() => server.listen())
afterAll(() => server.close())
const base = 'http://localhost/api/v1'

it('login returns tokens and me works with the bearer', async () => {
  const login = await fetch(base + '/auth/login', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: 'demo@travel.app', password: 'password' }) })
  expect(login.status).toBe(200)
  const { access_token } = await login.json()
  const me = await fetch(base + '/auth/me', { headers: { authorization: `Bearer ${access_token}` } })
  expect(me.status).toBe(200)
  expect((await me.json()).email).toBe('demo@travel.app')
})

it('chat returns a run_id and the stream emits frames ending completed', async () => {
  const acc = await (await fetch(base + '/chat', { method: 'POST', headers: { 'content-type': 'application/json', authorization: 'Bearer x' }, body: JSON.stringify({ message: 'Рим' }) })).json()
  expect(acc.run_id).toBeTruthy()
  const ticket = (await (await fetch(`${base}/chat/${acc.run_id}/stream-ticket`, { method: 'POST', headers: { authorization: 'Bearer x' } })).json()).ticket
  const res = await fetch(`${base}/chat/${acc.run_id}/stream?ticket=${ticket}`, { headers: { accept: 'text/event-stream' } })
  const text = await res.text()
  expect(text).toContain('event: run_status')
  expect(text).toContain('"status":"completed"')
})

it('plan map exposes editable gate and calendar has events', async () => {
  const map = await (await fetch(base + '/plans/PL-0001/map', { headers: { authorization: 'Bearer x' } })).json()
  expect(map.editable).toBe(true)
  const cal = await (await fetch(base + '/plans/PL-0001/calendar', { headers: { authorization: 'Bearer x' } })).json()
  expect(cal.events.length).toBeGreaterThan(0)
})
```

- [ ] **Step 2: Run — expect FAIL.** `pnpm test handlers`

- [ ] **Step 3: Implement `src/mocks/handlers.ts`**

```ts
import { http, HttpResponse } from 'msw'
import type { ChatRequest, ModifyRequest, CalendarEvent, MapPoint } from '../api/types'
import { createDb, sessionSummary, type Db } from './seed'
import { buildRunFrames } from './sse-script'
import { geo } from './geo'

const base = '*/api/v1'
const db: Db = createDb()
const runs = new Map<string, { frames: ReturnType<typeof buildRunFrames>; sessionId: string; planId: string }>()
const tickets = new Map<string, string>() // ticket -> runId
let seq = 1
const id = (p: string) => `${p}-${Date.now().toString(36)}-${seq++}`
const err = (status: number, code: string, message: string) => HttpResponse.json({ error: { code, message } }, { status })

function calendarFor(planId: string): CalendarEvent[] {
  const plan = db.plans.find(p => p.id === planId)
  if (!plan) return []
  const start = plan.start_date ?? '2026-09-05'
  const f = plan.items.flight, h = plan.items.hotel, t = plan.items.tour
  const ev: CalendarEvent[] = []
  if (f) ev.push({ id: 'ce-f', type: 'flight', title: `Перелёт ${f.origin_city} → ${f.destination}`, start: `${start}T${f.departure_time}:00Z`, end: `${start}T${f.arrival_time}:00Z`, location: f.destination, ref_id: f.flight_id })
  if (h) ev.push({ id: 'ce-h', type: 'hotel', title: `Отель ${h.stars}★ (${h.nights} ночей)`, start: `${start}T15:00:00Z`, end: `${plan.end_date ?? start}T11:00:00Z`, location: h.destination, ref_id: h.hotel_id })
  if (t) ev.push({ id: 'ce-t', type: 'tour', title: `Тур: ${t.destination}`, start: `${start}T09:00:00Z`, end: `${start}T18:00:00Z`, location: t.destination, ref_id: t.tour_id })
  return ev
}

export const handlers = [
  // Auth
  http.post(`${base}/auth/login`, async ({ request }) => {
    const b = await request.json() as { email: string; password: string }
    if (b.email !== db.user.email || b.password !== db.password) return err(401, 'unauthorized', 'Неверный email или пароль')
    const refresh = id('rt'); db.refreshTokens.add(refresh)
    return HttpResponse.json({ access_token: id('at'), refresh_token: refresh, token_type: 'Bearer', expires_in: 900, user: db.user })
  }),
  http.post(`${base}/auth/register`, async ({ request }) => {
    const b = await request.json() as { name: string; email: string; password: string }
    db.user = { ...db.user, name: b.name, email: b.email }; db.password = b.password
    const refresh = id('rt'); db.refreshTokens.add(refresh)
    return HttpResponse.json({ user: db.user, tokens: { access_token: id('at'), refresh_token: refresh, token_type: 'Bearer', expires_in: 900 } }, { status: 201 })
  }),
  http.post(`${base}/auth/refresh`, async ({ request }) => {
    const b = await request.json() as { refresh_token: string }
    if (!db.refreshTokens.has(b.refresh_token)) return err(401, 'unauthorized', 'Недействительный refresh')
    db.refreshTokens.delete(b.refresh_token); const rot = id('rt'); db.refreshTokens.add(rot)
    return HttpResponse.json({ access_token: id('at'), refresh_token: rot, token_type: 'Bearer', expires_in: 900 })
  }),
  http.post(`${base}/auth/logout`, async ({ request }) => {
    const b = await request.json() as { refresh_token: string }; db.refreshTokens.delete(b.refresh_token)
    return new HttpResponse(null, { status: 204 })
  }),
  http.get(`${base}/auth/me`, () => HttpResponse.json(db.user)),

  // Sessions
  http.get(`${base}/sessions`, () => HttpResponse.json({ items: db.sessions.map(sessionSummary), total: db.sessions.length, limit: 20, offset: 0 })),
  http.get(`${base}/sessions/:id`, ({ params }) => {
    const s = db.sessions.find(x => x.id === params.id); return s ? HttpResponse.json(s) : err(404, 'not_found', 'Чат не найден')
  }),

  // Groups
  http.get(`${base}/groups`, () => HttpResponse.json({ items: db.groups.map(g => ({ id: g.id, name: g.name, comment: g.comment, budget_rub: g.budget_rub, destination: g.destination, member_count: g.members.length, created_at: g.created_at })), total: db.groups.length, limit: 20, offset: 0 })),
  http.get(`${base}/groups/:id`, ({ params }) => { const g = db.groups.find(x => x.id === params.id); return g ? HttpResponse.json(g) : err(404, 'not_found', 'Группа не найдена') }),
  http.get(`${base}/groups/:id/preferences`, ({ params }) => {
    const g = db.groups.find(x => x.id === params.id); if (!g) return err(404, 'not_found', 'Группа не найдена')
    return HttpResponse.json({ items: g.members.map(m => ({ member_id: m.id, full_name: m.full_name, preferences: m.preferences ?? [] })) })
  }),
  http.get(`${base}/groups/:id/plans`, ({ params }) => HttpResponse.json({ items: db.plans.filter(p => p.group_id === params.id).map(p => ({ plan_id: p.id, status: p.status, destination: p.destination, estimated_total_rub: p.estimated_total_rub, created_at: p.created_at })) })),
  http.post(`${base}/groups`, async ({ request }) => {
    const b = await request.json() as any
    const g = { id: id('G'), ...b, created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
      members: (b.members ?? []).map((m: any, i: number) => ({ id: `m-${seq}-${i}`, ...m, preferences: (m.preferences ?? []).map((p: any, j: number) => ({ id: `p-${seq}-${i}-${j}`, ...p })) })) }
    db.groups.push(g); return HttpResponse.json(g, { status: 201 })
  }),

  // Plans
  http.get(`${base}/plans/:id`, ({ params }) => { const p = db.plans.find(x => x.id === params.id); return p ? HttpResponse.json(p) : err(404, 'not_found', 'План не найден') }),
  http.get(`${base}/plans/:id/map`, ({ params }) => {
    const p = db.plans.find(x => x.id === params.id); if (!p) return err(404, 'not_found', 'План не найден')
    const lats = p.map_points.map(pt => pt.lat), lngs = p.map_points.map(pt => pt.lng)
    return HttpResponse.json({ plan_id: p.id, status: p.status, editable: p.status === 'ready', points: p.map_points,
      bounds: { north: Math.max(...lats), south: Math.min(...lats), east: Math.max(...lngs), west: Math.min(...lngs) } })
  }),
  http.get(`${base}/plans/:id/calendar`, ({ params }) => HttpResponse.json({ plan_id: params.id, timezone: 'Europe/Moscow', events: calendarFor(params.id as string) })),
  http.post(`${base}/plans/:id/accept`, ({ params }) => { const p = db.plans.find(x => x.id === params.id); if (!p) return err(404, 'not_found', 'План не найден'); if (p.status !== 'ready') return err(409, 'plan_not_ready', 'План ещё строится'); p.status = 'accepted'; return HttpResponse.json(p) }),
  http.post(`${base}/plans/:id/reject`, ({ params }) => { const p = db.plans.find(x => x.id === params.id); if (!p) return err(404, 'not_found', 'План не найден'); p.status = 'rejected'; return HttpResponse.json(p) }),
  http.post(`${base}/plans/:id/modify`, async ({ params, request }) => {
    const p = db.plans.find(x => x.id === params.id); if (!p) return err(404, 'not_found', 'План не найден')
    if (p.status !== 'ready') return err(409, 'plan_not_ready', 'Изменять можно только готовый план')
    const body = await request.json() as ModifyRequest
    let pts = p.map_points.filter(pt => !(body.remove ?? []).includes(pt.id))
    for (const a of body.add ?? []) { const g = geo(a.name); pts.push({ id: id('mp'), name: a.name, kind: a.kind ?? 'stop', lat: a.lat ?? g.lat, lng: a.lng ?? g.lng, order: pts.length }) }
    pts = pts.map((pt, i) => ({ ...pt, order: i })); p.map_points = pts; p.status = 'building'
    const runId = id('run'); runs.set(runId, { frames: buildRunFrames({ runId, planId: p.id, kind: 'rebuild', points: pts }), sessionId: p.session_id, planId: p.id })
    // when this run finishes the plan becomes ready again
    setTimeout(() => { p.status = 'ready' }, 50)
    return HttpResponse.json({ run_id: runId }, { status: 202 })
  }),

  // Chat / run
  http.post(`${base}/chat`, async ({ request }) => {
    const b = await request.json() as ChatRequest
    let session = b.session_id ? db.sessions.find(s => s.id === b.session_id) : undefined
    if (!session) { session = { id: id('S'), summary: (b.message ?? 'Новый чат').slice(0, 48), created_at: new Date().toISOString(), updated_at: new Date().toISOString(), group_id: b.group_id, messages: [], plans: [] }; db.sessions.unshift(session) }
    if (b.message) session.messages.push({ id: id('msg'), role: 'user', content: b.message, created_at: new Date().toISOString() })
    const runId = id('run')
    const kind = b.in_reply_to_question_id ? 'answer' : 'first'
    const planId = kind === 'answer' ? (db.plans[0]?.id ?? 'PL-0001') : 'PL-pending'
    runs.set(runId, { frames: buildRunFrames({ runId, planId, kind, text: b.message }), sessionId: session.id, planId })
    return HttpResponse.json({ run_id: runId, session_id: session.id }, { status: 202 })
  }),
  http.post(`${base}/chat/:runId/stream-ticket`, ({ params }) => { const t = id('tk'); tickets.set(t, params.runId as string); return HttpResponse.json({ ticket: t, expires_in: 60 }) }),
  http.post(`${base}/chat/:runId/cancel`, ({ params }) => HttpResponse.json({ run_id: params.runId, status: 'cancelling' })),
  http.get(`${base}/chat/:runId/stream`, ({ params, request }) => {
    const url = new URL(request.url); const ticket = url.searchParams.get('ticket') ?? ''
    if (tickets.get(ticket) !== params.runId) return err(401, 'unauthorized', 'Недействительный билет')
    tickets.delete(ticket)
    const run = runs.get(params.runId as string)
    const frames = run?.frames ?? []
    const enc = new TextEncoder()
    let i = 0
    const stream = new ReadableStream({
      pull(controller) {
        if (i >= frames.length) { controller.close(); return }
        const f = frames[i++]
        controller.enqueue(enc.encode(`id: ${i}\nevent: ${f.event}\ndata: ${JSON.stringify(f.data)}\n\n`))
        return new Promise(r => setTimeout(r, 120)) // pace the stream
      },
    })
    return new HttpResponse(stream, { headers: { 'content-type': 'text/event-stream', 'cache-control': 'no-cache' } })
  }),
]
```

- [ ] **Step 4: Run — expect PASS.** `pnpm test handlers`

- [ ] **Step 5: Create `src/mocks/browser.ts`**

```ts
import { setupWorker } from 'msw/browser'
import { handlers } from './handlers'
export const worker = setupWorker(...handlers)
```

- [ ] **Step 6: Generate the MSW service worker file**

Run: `cd frontend && pnpm mock:init`
Expected: `frontend/public/mockServiceWorker.js` created.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/mocks/handlers.* frontend/src/mocks/browser.ts frontend/public/mockServiceWorker.js
git commit -m "feat(frontend): MSW handlers implementing the full API contract"
```

---

## Phase 4 — Stores (Track B; needs Phases 2–3)

### Task 4.1: Auth store

**Files:**
- Create: `frontend/src/stores/auth.ts` + `auth.spec.ts`

- [ ] **Step 1: Write failing test** (use the msw node server)

`src/stores/auth.spec.ts`:
```ts
import { it, expect, beforeEach, beforeAll, afterAll } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { setupServer } from 'msw/node'
import { handlers } from '../mocks/handlers'
import { useAuthStore } from './auth'

const server = setupServer(...handlers)
beforeAll(() => server.listen()); afterAll(() => server.close())
beforeEach(() => { setActivePinia(createPinia()); localStorage.clear() })

it('logs in, exposes the token, and restores from storage', async () => {
  const auth = useAuthStore()
  await auth.login('demo@travel.app', 'password')
  expect(auth.isAuthenticated).toBe(true)
  expect(auth.accessToken).toBeTruthy()
  const auth2 = useAuthStore()
  setActivePinia(createPinia())
  const fresh = useAuthStore()
  await fresh.restore()
  expect(fresh.isAuthenticated).toBe(true)
})
```

- [ ] **Step 2: Run — expect FAIL.** `pnpm test stores/auth`

- [ ] **Step 3: Implement `src/stores/auth.ts`**

```ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api, setTokenGetter } from '../api/endpoints'
import type { User } from '../api/types'

const LS = 'travel.auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const accessToken = ref<string | null>(null)
  const refreshToken = ref<string | null>(null)
  const ready = ref(false)
  const isAuthenticated = computed(() => !!accessToken.value)
  setTokenGetter(() => accessToken.value)

  function persist() { localStorage.setItem(LS, JSON.stringify({ refreshToken: refreshToken.value })) }

  async function login(email: string, password: string) {
    const r = await api.login({ email, password })
    accessToken.value = r.access_token; refreshToken.value = r.refresh_token; user.value = r.user; persist()
  }
  async function register(name: string, email: string, password: string) {
    const r = await api.register({ name, email, password })
    accessToken.value = r.tokens.access_token; refreshToken.value = r.tokens.refresh_token; user.value = r.user; persist()
  }
  async function restore() {
    ready.value = true
    const raw = localStorage.getItem(LS); if (!raw) return
    const { refreshToken: rt } = JSON.parse(raw) as { refreshToken: string | null }
    if (!rt) return
    try { const r = await api.refresh(rt); accessToken.value = r.access_token; refreshToken.value = r.refresh_token; persist(); user.value = await api.me() }
    catch { localStorage.removeItem(LS) }
  }
  async function logout() {
    if (refreshToken.value) { try { await api.logout(refreshToken.value) } catch {} }
    user.value = null; accessToken.value = null; refreshToken.value = null; localStorage.removeItem(LS)
  }
  return { user, accessToken, refreshToken, ready, isAuthenticated, login, register, restore, logout }
})
```

- [ ] **Step 4: Run — expect PASS.** `pnpm test stores/auth`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stores/auth.*
git commit -m "feat(frontend): auth store (login/register/refresh/restore)"
```

---

### Task 4.2: Sessions store

**Files:**
- Create: `frontend/src/stores/sessions.ts` + `sessions.spec.ts`

- [ ] **Step 1: Write failing test** (msw node server, as in 4.1)

`src/stores/sessions.spec.ts`:
```ts
import { it, expect, beforeEach, beforeAll, afterAll } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { setupServer } from 'msw/node'
import { handlers } from '../mocks/handlers'
import { useSessionsStore } from './sessions'

const server = setupServer(...handlers)
beforeAll(() => server.listen()); afterAll(() => server.close())
beforeEach(() => setActivePinia(createPinia()))

it('loads the session list and a session detail', async () => {
  const s = useSessionsStore()
  await s.loadList()
  expect(s.list.length).toBeGreaterThan(0)
  await s.loadDetail('S-0001')
  expect(s.current?.messages.length).toBeGreaterThan(0)
})
```

- [ ] **Step 2: Run — expect FAIL.** `pnpm test stores/sessions`

- [ ] **Step 3: Implement `src/stores/sessions.ts`**

```ts
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/endpoints'
import type { SessionSummary, SessionDetail } from '../api/types'

export const useSessionsStore = defineStore('sessions', () => {
  const list = ref<SessionSummary[]>([])
  const current = ref<SessionDetail | null>(null)
  const loading = ref(false)

  async function loadList() { loading.value = true; try { list.value = (await api.sessions()).items } finally { loading.value = false } }
  async function loadDetail(id: string) { loading.value = true; try { current.value = await api.session(id) } finally { loading.value = false } }
  function clearCurrent() { current.value = null }
  return { list, current, loading, loadList, loadDetail, clearCurrent }
})
```

- [ ] **Step 4: Run — expect PASS.** `pnpm test stores/sessions`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stores/sessions.*
git commit -m "feat(frontend): sessions store"
```

---

### Task 4.3: Groups store

**Files:**
- Create: `frontend/src/stores/groups.ts` + `groups.spec.ts`

- [ ] **Step 1: Write failing test**

`src/stores/groups.spec.ts`:
```ts
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
```

- [ ] **Step 2: Run — expect FAIL.** `pnpm test stores/groups`

- [ ] **Step 3: Implement `src/stores/groups.ts`**

```ts
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/endpoints'
import type { GroupSummary, Group, CreateGroupRequest } from '../api/types'

export const useGroupsStore = defineStore('groups', () => {
  const list = ref<GroupSummary[]>([])
  const current = ref<Group | null>(null)
  async function loadList() { list.value = (await api.groups()).items }
  async function load(id: string) { current.value = await api.group(id) }
  async function create(body: CreateGroupRequest) { const g = await api.createGroup(body); current.value = g; return g }
  return { list, current, loadList, load, create }
})
```

- [ ] **Step 4: Run — expect PASS.** `pnpm test stores/groups`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stores/groups.*
git commit -m "feat(frontend): groups store"
```

---

### Task 4.4: Plans store

**Files:**
- Create: `frontend/src/stores/plans.ts` + `plans.spec.ts`

- [ ] **Step 1: Write failing test**

`src/stores/plans.spec.ts`:
```ts
import { it, expect, beforeEach, beforeAll, afterAll } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { setupServer } from 'msw/node'
import { handlers } from '../mocks/handlers'
import { usePlansStore } from './plans'

const server = setupServer(...handlers)
beforeAll(() => server.listen()); afterAll(() => server.close())
beforeEach(() => setActivePinia(createPinia()))

it('loads a plan with map + calendar and accepts it', async () => {
  const p = usePlansStore()
  await p.load('PL-0001')
  expect(p.current?.status).toBe('ready')
  expect(p.map?.editable).toBe(true)
  expect(p.calendar?.events.length).toBeGreaterThan(0)
  await p.accept('PL-0001')
  expect(p.current?.status).toBe('accepted')
})

it('modify returns a run id and stages edits', async () => {
  const p = usePlansStore()
  await p.load('PL-0001')
  const runId = await p.modify('PL-0001', { add: [{ name: 'Венеция', kind: 'stop' }] })
  expect(runId).toBeTruthy()
})
```

- [ ] **Step 2: Run — expect FAIL.** `pnpm test stores/plans`

- [ ] **Step 3: Implement `src/stores/plans.ts`**

```ts
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/endpoints'
import type { Plan, PlanMap, PlanCalendar, ModifyRequest, MapPoint } from '../api/types'

export const usePlansStore = defineStore('plans', () => {
  const current = ref<Plan | null>(null)
  const map = ref<PlanMap | null>(null)
  const calendar = ref<PlanCalendar | null>(null)
  const loading = ref(false)
  // local edit buffer for route changes before submit
  const pendingRemove = ref<Set<string>>(new Set())
  const pendingAdd = ref<MapPoint[]>([])

  async function load(id: string) {
    loading.value = true
    try { const [p, m, c] = await Promise.all([api.plan(id), api.planMap(id), api.planCalendar(id)]); current.value = p; map.value = m; calendar.value = c; resetEdits() }
    finally { loading.value = false }
  }
  function resetEdits() { pendingRemove.value = new Set(); pendingAdd.value = [] }
  function toggleRemove(id: string) { const s = new Set(pendingRemove.value); s.has(id) ? s.delete(id) : s.add(id); pendingRemove.value = s }
  function stageAdd(name: string, kind: MapPoint['kind'] = 'stop') { pendingAdd.value = [...pendingAdd.value, { id: `tmp-${Date.now()}`, name, kind, lat: 0, lng: 0, order: 999 }] }
  const hasEdits = () => pendingRemove.value.size > 0 || pendingAdd.value.length > 0

  async function accept(id: string) { current.value = await api.acceptPlan(id) }
  async function reject(id: string, reason?: string) { current.value = await api.rejectPlan(id, reason) }
  async function modify(id: string, override?: ModifyRequest): Promise<string> {
    const body: ModifyRequest = override ?? { add: pendingAdd.value.map(p => ({ name: p.name, kind: p.kind })), remove: [...pendingRemove.value] }
    const { run_id } = await api.modifyPlan(id, body); resetEdits(); return run_id
  }
  return { current, map, calendar, loading, pendingRemove, pendingAdd, hasEdits, load, toggleRemove, stageAdd, resetEdits, accept, reject, modify }
})
```

- [ ] **Step 4: Run — expect PASS.** `pnpm test stores/plans`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stores/plans.*
git commit -m "feat(frontend): plans store with map/calendar + edit buffer"
```

---

### Task 4.5: Chat store (run lifecycle + SSE reducer)

**Files:**
- Create: `frontend/src/stores/chat.ts` + `chat.spec.ts`

- [ ] **Step 1: Write failing test** (msw node server; drives the whole run)

`src/stores/chat.spec.ts`:
```ts
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
```

- [ ] **Step 2: Run — expect FAIL.** `pnpm test stores/chat`

- [ ] **Step 3: Implement `src/stores/chat.ts`**

```ts
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, client } from '../api/endpoints'
import { streamRun } from '../api/sse'
import type { Message, ClarifyingQuestion, PlanBuildStatus, ChatRequest } from '../api/types'

interface UiMessage extends Pick<Message, 'id' | 'role' | 'content'> { streaming?: boolean }

export const useChatStore = defineStore('chat', () => {
  const sessionId = ref<string | null>(null)
  const messages = ref<UiMessage[]>([])
  const pendingQuestion = ref<ClarifyingQuestion | null>(null)
  const planStatus = ref<PlanBuildStatus | null>(null)
  const planId = ref<string | null>(null)
  const running = ref(false)
  let runDone: Promise<void> = Promise.resolve()

  function reset() { sessionId.value = null; messages.value = []; pendingQuestion.value = null; planStatus.value = null; planId.value = null }
  function hydrate(id: string, msgs: Message[]) { sessionId.value = id; messages.value = msgs.map(m => ({ id: m.id, role: m.role, content: m.content })); pendingQuestion.value = msgs.at(-1)?.question ?? null }

  async function startRun(req: ChatRequest) {
    running.value = true; pendingQuestion.value = null
    runDone = (async () => {
      const acc = await api.chat(req); sessionId.value = acc.session_id
      const { ticket } = await api.streamTicket(acc.run_id)
      let assistant: UiMessage | null = null
      for await (const ev of streamRun({ baseUrl: client.baseUrl, runId: acc.run_id, ticket })) {
        if (ev.event === 'message_delta') {
          if (!assistant) { assistant = { id: ev.data.message_id, role: 'assistant', content: '', streaming: true }; messages.value.push(assistant) }
          assistant.content += ev.data.delta
        } else if (ev.event === 'message') {
          if (assistant) { assistant.content = ev.data.message.content; assistant.streaming = false }
          if (ev.data.message.plan_ref) planId.value = ev.data.message.plan_ref.plan_id
        } else if (ev.event === 'clarifying_question') { pendingQuestion.value = ev.data.question }
        else if (ev.event === 'plan_status') { planStatus.value = ev.data.status; planId.value = ev.data.plan_id }
        else if (ev.event === 'run_status' && (ev.data.status === 'completed' || ev.data.status === 'error' || ev.data.status === 'cancelled')) break
      }
      if (assistant) assistant.streaming = false
      running.value = false
    })()
    return runDone
  }

  async function send(text: string) {
    messages.value.push({ id: `u-${Date.now()}`, role: 'user', content: text })
    return startRun({ message: text, session_id: sessionId.value ?? undefined })
  }
  async function answer(questionId: string, optionIds: string[], freeform?: string) {
    const label = pendingQuestion.value?.options.filter(o => optionIds.includes(o.id)).map(o => o.label).join(', ') || freeform || ''
    if (label) messages.value.push({ id: `u-${Date.now()}`, role: 'user', content: label })
    return startRun({ session_id: sessionId.value ?? undefined, in_reply_to_question_id: questionId, selected_option_ids: optionIds, freeform })
  }
  const waitForIdle = () => runDone
  return { sessionId, messages, pendingQuestion, planStatus, planId, running, reset, hydrate, send, answer, waitForIdle }
})
```

- [ ] **Step 4: Run — expect PASS.** `pnpm test stores/chat`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stores/chat.*
git commit -m "feat(frontend): chat store with run lifecycle + SSE reducer"
```

---

## Phase 5 — Auth view

### Task 5.1: AuthView (login / register)

**Files:**
- Replace: `frontend/src/components/auth/AuthView.vue`

- [ ] **Step 1: Implement `AuthView.vue`**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import { useToasts } from '../../composables/useToasts'
import { ApiClientError } from '../../api/client'

const auth = useAuthStore(); const router = useRouter(); const route = useRoute(); const { push } = useToasts()
const mode = ref<'login' | 'register'>('login')
const name = ref(''); const email = ref('demo@travel.app'); const password = ref('password'); const busy = ref(false)

async function submit() {
  busy.value = true
  try {
    if (mode.value === 'login') await auth.login(email.value, password.value)
    else await auth.register(name.value, email.value, password.value)
    router.replace((route.query.redirect as string) || '/')
  } catch (e) {
    push({ kind: 'error', text: e instanceof ApiClientError ? e.message : 'Не удалось войти' })
  } finally { busy.value = false }
}
</script>

<template>
  <div class="wrap">
    <form class="card glass" @submit.prevent="submit">
      <h1>{{ mode === 'login' ? 'С возвращением' : 'Создать аккаунт' }}</h1>
      <input v-if="mode === 'register'" v-model="name" class="f" placeholder="Имя" required />
      <input v-model="email" class="f" type="email" placeholder="Email" required />
      <input v-model="password" class="f" type="password" placeholder="Пароль" minlength="8" required />
      <button class="submit" :disabled="busy">{{ busy ? '…' : (mode === 'login' ? 'Войти' : 'Зарегистрироваться') }}</button>
      <p class="alt">
        {{ mode === 'login' ? 'Нет аккаунта?' : 'Уже есть аккаунт?' }}
        <a href="#" @click.prevent="mode = mode === 'login' ? 'register' : 'login'">{{ mode === 'login' ? 'Регистрация' : 'Вход' }}</a>
      </p>
    </form>
  </div>
</template>

<style scoped>
.wrap { position: fixed; inset: 0; display: grid; place-items: center; z-index: 1; }
.card { width: min(380px, 92%); padding: 28px; border-radius: 24px / 18px; display: flex; flex-direction: column; gap: 12px; }
h1 { margin: 0 0 6px; font-size: 24px; color: #1c150f; }
.f { padding: 12px 14px; border: none; border-radius: 12px; background: rgba(255,255,255,.45); color: var(--ink); font: inherit; }
.f::placeholder { color: var(--ink-soft); }
.submit { margin-top: 4px; padding: 12px; border: none; border-radius: 12px; background: var(--accent); color: #fff; font-weight: 600; cursor: pointer; }
.submit:disabled { opacity: .6; }
.alt { font-size: 13px; color: var(--ink-soft); text-align: center; margin: 4px 0 0; }
.alt a { color: var(--accent-press); font-weight: 600; }
</style>
```

- [ ] **Step 2: Verify** — `pnpm dev`, visit `/login`, log in with the prefilled demo creds → redirected to `/`. Wrong password → error toast.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/auth/AuthView.vue
git commit -m "feat(frontend): glass login/register view"
```

---

## Phase 6 — Chat experience

### Task 6.1: ChatComposer

**Files:**
- Create: `frontend/src/components/chat/ChatComposer.vue` (reuse caret/typewriter logic from existing `AgentChat/`)

- [ ] **Step 1: Implement `ChatComposer.vue`** (frosted glass, elliptical radius, autosize, Enter to send)

```vue
<script setup lang="ts">
import { ref, nextTick, watch, useTemplateRef } from 'vue'
const model = defineModel<string>({ default: '' })
const emit = defineEmits<{ submit: [text: string] }>()
const ta = useTemplateRef<HTMLTextAreaElement>('ta')
const MAX = 6

function autosize() {
  const el = ta.value; if (!el) return
  el.style.height = '0px'
  const cs = getComputedStyle(el); const line = parseFloat(cs.lineHeight); const pad = parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom)
  el.style.height = Math.min(el.scrollHeight, line * MAX + pad) + 'px'
}
watch(model, () => nextTick(autosize))
function onKey(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); fire() }
}
function fire() { const t = model.value.trim(); if (t) { emit('submit', t); model.value = '' } }
</script>

<template>
  <div class="composer glass">
    <div class="row">
      <textarea ref="ta" v-model="model" class="field" rows="1" placeholder="Спланируй путешествие…"
        autocomplete="off" spellcheck="false" @keydown="onKey" />
      <button class="send" :disabled="!model.trim()" aria-label="Отправить" @click="fire">↑</button>
    </div>
  </div>
</template>

<style scoped>
.composer { width: min(680px, 92%); border-radius: 90px / 18px; padding: 6px; }
.row { display: flex; align-items: flex-end; gap: 10px; padding: 9px 12px; }
.field { flex: 1; resize: none; border: none; background: transparent; color: var(--ink); font: inherit; font-size: 16px; outline: none; padding: 8px; max-height: 160px; }
.field::placeholder { color: var(--ink-soft); }
.send { width: 40px; height: 40px; flex: none; border-radius: 50%; border: none; cursor: pointer; color: #fff; font-size: 18px;
  background: linear-gradient(160deg, #e2825f, var(--accent-press)); }
.send:disabled { opacity: .5; cursor: default; }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/chat/ChatComposer.vue
git commit -m "feat(frontend): glass chat composer"
```

---

### Task 6.2: MessageBubble, ClarifyingQuestion, PlanStatus

**Files:**
- Create: `frontend/src/components/chat/MessageBubble.vue`, `ClarifyingQuestion.vue`, `PlanStatus.vue`

- [ ] **Step 1: `MessageBubble.vue`**

```vue
<script setup lang="ts">
defineProps<{ role: 'user' | 'assistant'; content: string; streaming?: boolean }>()
</script>
<template>
  <div class="msg" :class="role === 'user' ? 'user' : 'bot glass'">
    <span>{{ content }}</span><span v-if="streaming" class="caret" />
  </div>
</template>
<style scoped>
.msg { max-width: 80%; padding: 12px 15px; font-size: 14.5px; line-height: 1.5; white-space: pre-wrap; }
.user { align-self: flex-end; background: var(--accent); color: #fff; border-radius: 18px 18px 6px 18px; }
.bot { align-self: flex-start; border-radius: 18px 18px 18px 6px; }
.caret { display: inline-block; width: 7px; height: 1.05em; margin-left: 2px; vertical-align: -2px; background: currentColor; animation: blink 1s steps(2) infinite; }
@keyframes blink { 50% { opacity: 0; } }
</style>
```

- [ ] **Step 2: `ClarifyingQuestion.vue`** (chips + optional freeform)

```vue
<script setup lang="ts">
import { ref } from 'vue'
import type { ClarifyingQuestion } from '../../api/types'
const props = defineProps<{ question: ClarifyingQuestion }>()
const emit = defineEmits<{ answer: [optionIds: string[], freeform?: string] }>()
const freeform = ref('')
function pick(id: string) { emit('answer', [id]) }
function sendFree() { if (freeform.value.trim()) emit('answer', [], freeform.value.trim()) }
</script>
<template>
  <div class="q">
    <p class="qt glass">{{ question.text }}</p>
    <div class="chips">
      <button v-for="o in question.options" :key="o.id" class="chip glass" @click="pick(o.id)">{{ o.label }}</button>
    </div>
    <div v-if="question.allow_freeform" class="free">
      <input v-model="freeform" class="fi glass" placeholder="Свой вариант…" @keydown.enter="sendFree" />
      <button class="go" @click="sendFree">→</button>
    </div>
  </div>
</template>
<style scoped>
.q { align-self: flex-start; max-width: 90%; display: flex; flex-direction: column; gap: 8px; }
.qt { margin: 0; padding: 12px 15px; border-radius: 18px 18px 18px 6px; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { padding: 8px 14px; border: none; border-radius: 999px; cursor: pointer; color: var(--ink); font: inherit; font-size: 13.5px; }
.free { display: flex; gap: 8px; }
.fi { flex: 1; padding: 9px 13px; border: none; border-radius: 999px; color: var(--ink); font: inherit; }
.fi::placeholder { color: var(--ink-soft); }
.go { width: 38px; border: none; border-radius: 50%; background: var(--accent); color: #fff; cursor: pointer; }
</style>
```

- [ ] **Step 3: `PlanStatus.vue`** (building → ready indicator + link to plan)

```vue
<script setup lang="ts">
import { RouterLink } from 'vue-router'
defineProps<{ status: 'building' | 'ready' | 'error'; planId?: string | null }>()
</script>
<template>
  <div class="ps glass" :data-status="status">
    <template v-if="status === 'building'"><span class="dot" /> Собираю маршрут…</template>
    <template v-else-if="status === 'ready'">
      ✓ Маршрут готов
      <RouterLink v-if="planId" class="open" :to="`/plans/${planId}`">Открыть план →</RouterLink>
    </template>
    <template v-else>Не удалось построить план</template>
  </div>
</template>
<style scoped>
.ps { align-self: flex-start; padding: 9px 14px; border-radius: 12px; font-size: 13.5px; display: flex; gap: 8px; align-items: center; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); animation: pulse 1s infinite; }
@keyframes pulse { 50% { opacity: .3; } }
.open { color: var(--accent-press); font-weight: 600; }
</style>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/chat/MessageBubble.vue frontend/src/components/chat/ClarifyingQuestion.vue frontend/src/components/chat/PlanStatus.vue
git commit -m "feat(frontend): chat message, clarifying-question, plan-status components"
```

---

### Task 6.3: MessageList

**Files:**
- Create: `frontend/src/components/chat/MessageList.vue`

- [ ] **Step 1: Implement `MessageList.vue`** (renders messages + the active question + plan status; autoscroll)

```vue
<script setup lang="ts">
import { watch, nextTick, useTemplateRef } from 'vue'
import MessageBubble from './MessageBubble.vue'
import ClarifyingQuestion from './ClarifyingQuestion.vue'
import PlanStatus from './PlanStatus.vue'
import type { ClarifyingQuestion as CQ } from '../../api/types'

const props = defineProps<{
  messages: { id: string; role: 'user' | 'assistant'; content: string; streaming?: boolean }[]
  question: CQ | null
  planStatus: 'building' | 'ready' | 'error' | null
  planId: string | null
}>()
const emit = defineEmits<{ answer: [optionIds: string[], freeform?: string] }>()
const box = useTemplateRef<HTMLElement>('box')
watch(() => [props.messages.map(m => m.content).join(''), props.question, props.planStatus],
  () => nextTick(() => { if (box.value) box.value.scrollTop = box.value.scrollHeight }))
</script>

<template>
  <div ref="box" class="list">
    <MessageBubble v-for="m in messages" :key="m.id" :role="m.role" :content="m.content" :streaming="m.streaming" />
    <PlanStatus v-if="planStatus" :status="planStatus" :plan-id="planId" />
    <ClarifyingQuestion v-if="question" :question="question" @answer="(o, f) => emit('answer', o, f)" />
  </div>
</template>

<style scoped>
.list { display: flex; flex-direction: column; gap: 13px; overflow: auto; height: 100%; padding: 4px 2px; }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/chat/MessageList.vue
git commit -m "feat(frontend): message list with autoscroll"
```

---

### Task 6.4: ChatView (center→bottom animation, store wiring)

**Files:**
- Replace: `frontend/src/components/chat/ChatView.vue`

- [ ] **Step 1: Implement `ChatView.vue`**

```vue
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import ChatComposer from './ChatComposer.vue'
import MessageList from './MessageList.vue'
import { useChatStore } from '../../stores/chat'
import { useSessionsStore } from '../../stores/sessions'

const props = defineProps<{ sessionId?: string }>()
const chat = useChatStore(); const sessions = useSessionsStore(); const router = useRouter()
const draft = ref('')
const started = computed(() => chat.messages.length > 0)

onMounted(async () => {
  if (props.sessionId) { await sessions.loadDetail(props.sessionId); if (sessions.current) chat.hydrate(sessions.current.id, sessions.current.messages) }
  else chat.reset()
})
watch(() => props.sessionId, async (id) => {
  if (id) { await sessions.loadDetail(id); if (sessions.current) chat.hydrate(sessions.current.id, sessions.current.messages) }
  else chat.reset()
})

async function onSubmit(text: string) {
  await chat.send(text)
  if (chat.sessionId && !props.sessionId) router.replace(`/c/${chat.sessionId}`)
}
function onAnswer(optionIds: string[], freeform?: string) {
  if (chat.pendingQuestion) chat.answer(chat.pendingQuestion.id, optionIds, freeform)
}
</script>

<template>
  <div class="chat" :class="{ chatting: started }">
    <transition name="hero">
      <div v-if="!started" class="hero">
        <h1>Куда отправимся?</h1>
        <p>Опишите поездку — соберу маршрут, отели и туры под вашу группу.</p>
      </div>
    </transition>

    <div v-if="started" class="thread">
      <MessageList :messages="chat.messages" :question="chat.pendingQuestion" :plan-status="chat.planStatus" :plan-id="chat.planId" @answer="onAnswer" />
    </div>

    <div class="composer-slot" :class="{ bottom: started }">
      <ChatComposer v-model="draft" @submit="onSubmit" />
    </div>
  </div>
</template>

<style scoped>
.chat { position: fixed; inset: 0; }
.hero { position: absolute; left: 0; right: 0; top: 31%; text-align: center; }
.hero h1 { font-size: 38px; font-weight: 600; letter-spacing: -.8px; margin: 0; color: #fff; text-shadow: 0 2px 30px rgba(0,0,0,.6); }
.hero p { color: #e7ddcf; margin: 10px 0 0; text-shadow: 0 1px 14px rgba(0,0,0,.6); }
.thread { position: absolute; left: 50%; transform: translateX(-50%); top: 78px; bottom: 110px; width: min(720px, 92%); }
.composer-slot { position: absolute; left: 50%; transform: translateX(-50%); top: 48%; display: flex; justify-content: center; width: 100%;
  transition: top .6s cubic-bezier(.55,.06,.12,1); }
.composer-slot.bottom { top: calc(100% - 96px); }
.hero-enter-active, .hero-leave-active { transition: opacity .35s, transform .35s; }
.hero-enter-from, .hero-leave-to { opacity: 0; transform: translateY(-14px); }
</style>
```

- [ ] **Step 2: Verify the full flow** — `pnpm dev`, log in, land on `/`. Type a message → composer animates to the bottom, assistant reply streams in, a clarifying question appears as chips. Pick a chip → plan builds → "Открыть план" link appears.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/chat/ChatView.vue
git commit -m "feat(frontend): chat view with centered→bottom animation and run wiring"
```

---

## Phase 7 — Side panel

### Task 7.1: MenuButton + SidePanel + lists

**Files:**
- Replace: `frontend/src/components/layout/MenuButton.vue`, `SidePanel.vue`
- Create: `frontend/src/components/layout/SessionList.vue`, `GroupList.vue`, `PlanList.vue`

- [ ] **Step 1: `MenuButton.vue`** (top-left glass hamburger)

```vue
<script setup lang="ts">defineEmits<{ toggle: [] }>()</script>
<template>
  <button class="menu glass" type="button" aria-label="Меню" @click="$emit('toggle')">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 6h18M3 12h18M3 18h18"/></svg>
  </button>
</template>
<style scoped>
.menu { position: fixed; top: 20px; left: 20px; z-index: 30; width: 44px; height: 44px; border-radius: 14px; display: grid; place-items: center; cursor: pointer; border: none; }
.menu svg { width: 20px; height: 20px; }
</style>
```

- [ ] **Step 2: `SessionList.vue`** (history; navigates to a chat)

```vue
<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useSessionsStore } from '../../stores/sessions'
import Skeleton from '../ui/Skeleton.vue'
import EmptyState from '../ui/EmptyState.vue'
const sessions = useSessionsStore()
const props = defineProps<{ filter: string }>()
const emit = defineEmits<{ navigate: [] }>()
onMounted(() => { if (!sessions.list.length) sessions.loadList() })
function match(s: { summary: string }) { return s.summary.toLowerCase().includes(props.filter.toLowerCase()) }
</script>
<template>
  <div class="sect">
    <h4>История</h4>
    <template v-if="sessions.loading && !sessions.list.length"><Skeleton v-for="i in 3" :key="i" h="32px" /></template>
    <EmptyState v-else-if="!sessions.list.length" title="Пока нет чатов" />
    <RouterLink v-for="s in sessions.list.filter(match)" :key="s.id" class="item" :to="`/c/${s.id}`" @click="emit('navigate')">
      💬 <span class="lbl">{{ s.summary }}</span>
    </RouterLink>
  </div>
</template>
<style scoped>
.sect { display: flex; flex-direction: column; gap: 2px; }
h4 { margin: 10px 4px 3px; font-size: 11px; text-transform: uppercase; letter-spacing: .1em; color: #7a6f62; font-weight: 700; }
.item { display: flex; gap: 9px; padding: 8px 10px; border-radius: 9px; color: #3a3024; font-size: 14px; text-decoration: none; }
.item:hover { background: rgba(255,255,255,.4); }
.lbl { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
```

- [ ] **Step 3: `GroupList.vue`**

```vue
<script setup lang="ts">
import { onMounted } from 'vue'
import { useGroupsStore } from '../../stores/groups'
import EmptyState from '../ui/EmptyState.vue'
const groups = useGroupsStore()
defineProps<{ filter: string }>()
onMounted(() => { if (!groups.list.length) groups.loadList() })
</script>
<template>
  <div class="sect">
    <h4>Группы</h4>
    <EmptyState v-if="!groups.list.length" title="Нет групп" hint="Создайте группу путешественников" />
    <div v-for="g in groups.list.filter(g => g.name.toLowerCase().includes(filter.toLowerCase()))" :key="g.id" class="item">
      👥 <span class="lbl">{{ g.name }}</span> <small>{{ g.member_count }}</small>
    </div>
  </div>
</template>
<style scoped>
.sect { display: flex; flex-direction: column; gap: 2px; }
h4 { margin: 10px 4px 3px; font-size: 11px; text-transform: uppercase; letter-spacing: .1em; color: #7a6f62; font-weight: 700; }
.item { display: flex; gap: 9px; padding: 8px 10px; border-radius: 9px; color: #3a3024; font-size: 14px; }
.item:hover { background: rgba(255,255,255,.4); }
.lbl { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
small { color: #8a7f70; }
</style>
```

- [ ] **Step 4: `PlanList.vue`** (plans pulled from the seed group; links to plan view)

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api } from '../../api/endpoints'
import type { PlanSummary } from '../../api/types'
import { useGroupsStore } from '../../stores/groups'
import EmptyState from '../ui/EmptyState.vue'
const groups = useGroupsStore()
const plans = ref<PlanSummary[]>([])
const emit = defineEmits<{ navigate: [] }>()
onMounted(async () => {
  if (!groups.list.length) await groups.loadList()
  const all = await Promise.all(groups.list.map(g => api.groupPlans(g.id).then(r => r.items)))
  plans.value = all.flat()
})
</script>
<template>
  <div class="sect">
    <h4>Планы</h4>
    <EmptyState v-if="!plans.length" title="Нет планов" />
    <RouterLink v-for="p in plans" :key="p.plan_id" class="item" :to="`/plans/${p.plan_id}`" @click="emit('navigate')">
      🗺 <span class="lbl">{{ p.destination || 'Маршрут' }}</span> <small>{{ p.status }}</small>
    </RouterLink>
  </div>
</template>
<style scoped>
.sect { display: flex; flex-direction: column; gap: 2px; }
h4 { margin: 10px 4px 3px; font-size: 11px; text-transform: uppercase; letter-spacing: .1em; color: #7a6f62; font-weight: 700; }
.item { display: flex; gap: 9px; padding: 8px 10px; border-radius: 9px; color: #3a3024; font-size: 14px; text-decoration: none; }
.item:hover { background: rgba(255,255,255,.4); }
.lbl { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
small { color: #8a7f70; }
</style>
```

- [ ] **Step 5: `SidePanel.vue`** (frosted-white, slide-in, hosts the lists + new-chat + search + logout)

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import SessionList from './SessionList.vue'
import GroupList from './GroupList.vue'
import PlanList from './PlanList.vue'
import { useChatStore } from '../../stores/chat'
import { useAuthStore } from '../../stores/auth'

defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()
const router = useRouter(); const chat = useChatStore(); const auth = useAuthStore()
const filter = ref('')
function newChat() { chat.reset(); router.push('/'); emit('close') }
async function logout() { await auth.logout(); router.push('/login') }
</script>

<template>
  <transition name="slide">
    <aside v-show="open" class="panel glass" @keydown.esc="emit('close')">
      <div class="title">Маршруты</div>
      <button class="newchat" @click="newChat">＋ Новый чат</button>
      <input v-model="filter" class="search" placeholder="Поиск по чатам…" />
      <div class="scroll">
        <SessionList :filter="filter" @navigate="emit('close')" />
        <GroupList :filter="filter" />
        <PlanList @navigate="emit('close')" />
      </div>
      <button class="logout" @click="logout">Выйти</button>
    </aside>
  </transition>
</template>

<style scoped>
.panel { position: fixed; top: 0; left: 0; bottom: 0; width: 308px; z-index: 25; padding: 16px; display: flex; flex-direction: column; gap: 12px;
  border-radius: 0 22px 22px 0; color: var(--ink); }
.title { font-weight: 700; padding: 6px 4px 0 54px; color: #1c150f; }
.newchat { padding: 11px 13px; border: none; border-radius: 13px; cursor: pointer; font-weight: 600; background: var(--accent); color: #fff; }
.search { padding: 9px 12px; border: none; border-radius: 11px; background: rgba(255,255,255,.4); color: var(--ink); font-size: 13.5px; }
.search::placeholder { color: var(--ink-soft); }
.scroll { flex: 1; overflow: auto; display: flex; flex-direction: column; gap: 6px; }
.logout { padding: 9px; border: none; border-radius: 10px; background: rgba(0,0,0,.08); color: #3a3024; cursor: pointer; }
.slide-enter-active, .slide-leave-active { transition: transform .42s cubic-bezier(.5,.05,.1,1); }
.slide-enter-from, .slide-leave-to { transform: translateX(-104%); }
</style>
```

- [ ] **Step 6: Verify** — `pnpm dev`, click the top-left menu → panel slides in with История/Группы/Планы, search filters history, "Новый чат" resets, a plan link opens the plan route, "Выйти" logs out.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/layout
git commit -m "feat(frontend): side panel with history/groups/plans, search, new chat, logout"
```

---

## Phase 8 — Plan view (map + calendar + editing)

### Task 8.1: MapView (MapLibre)

**Files:**
- Create: `frontend/src/components/plan/MapView.vue`

- [ ] **Step 1: Implement `MapView.vue`** (dark no-key style, markers, route line, fit to points)

```vue
<script setup lang="ts">
import { onMounted, onBeforeUnmount, watch, useTemplateRef } from 'vue'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { MapPoint } from '../../api/types'

const props = defineProps<{ points: MapPoint[] }>()
const el = useTemplateRef<HTMLElement>('el')
let map: maplibregl.Map | null = null
let markers: maplibregl.Marker[] = []

// Free, no-API-key raster style (CARTO dark basemap).
const STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: { carto: { type: 'raster', tiles: ['https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png'], tileSize: 256, attribution: '© OpenStreetMap, © CARTO' } },
  layers: [{ id: 'carto', type: 'raster', source: 'carto' }],
}

function render() {
  if (!map) return
  markers.forEach(m => m.remove()); markers = []
  const pts = [...props.points].sort((a, b) => a.order - b.order)
  if (!pts.length) return
  for (const p of pts) {
    const e = document.createElement('div'); e.className = 'pin'; e.title = p.name
    markers.push(new maplibregl.Marker({ element: e }).setLngLat([p.lng, p.lat]).setPopup(new maplibregl.Popup({ offset: 16 }).setText(p.name)).addTo(map))
  }
  const line = { type: 'Feature' as const, geometry: { type: 'LineString' as const, coordinates: pts.map(p => [p.lng, p.lat]) }, properties: {} }
  const src = map.getSource('route') as maplibregl.GeoJSONSource | undefined
  if (src) src.setData(line as any)
  else { map.addSource('route', { type: 'geojson', data: line as any }); map.addLayer({ id: 'route', type: 'line', source: 'route', paint: { 'line-color': '#d97757', 'line-width': 3, 'line-dasharray': [2, 1.5] } }) }
  const b = new maplibregl.LngLatBounds(); pts.forEach(p => b.extend([p.lng, p.lat]))
  map.fitBounds(b, { padding: 70, maxZoom: 6, duration: 600 })
}

onMounted(() => {
  map = new maplibregl.Map({ container: el.value!, style: STYLE, center: [37.6, 55.75], zoom: 3, attributionControl: { compact: true } })
  map.on('load', render)
})
watch(() => props.points, render, { deep: true })
onBeforeUnmount(() => map?.remove())
</script>

<template><div ref="el" class="map" /></template>

<style scoped>
.map { width: 100%; height: 100%; border-radius: 16px; overflow: hidden; }
:global(.pin) { width: 16px; height: 16px; border-radius: 50% 50% 50% 0; background: var(--accent); transform: rotate(-45deg); box-shadow: 0 0 0 3px rgba(217,119,87,.35); }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/plan/MapView.vue
git commit -m "feat(frontend): MapLibre plan map with route line and markers"
```

---

### Task 8.2: ItineraryView (calendar)

**Files:**
- Create: `frontend/src/components/plan/ItineraryView.vue`

- [ ] **Step 1: Implement `ItineraryView.vue`** (events grouped by day; glass cards)

```vue
<script setup lang="ts">
import { computed } from 'vue'
import type { CalendarEvent } from '../../api/types'
const props = defineProps<{ events: CalendarEvent[]; timezone?: string }>()
const ICON: Record<string, string> = { flight: '✈️', hotel: '🏨', tour: '🗺', activity: '📍' }

const days = computed(() => {
  const map = new Map<string, CalendarEvent[]>()
  for (const e of [...props.events].sort((a, b) => a.start.localeCompare(b.start))) {
    const day = e.start.slice(0, 10); if (!map.has(day)) map.set(day, []); map.get(day)!.push(e)
  }
  return [...map.entries()]
})
const fmtDay = (d: string) => new Date(d).toLocaleDateString('ru-RU', { weekday: 'short', day: 'numeric', month: 'long' })
const fmtTime = (s?: string) => (s ? new Date(s).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }) : '')
</script>

<template>
  <div class="cal">
    <div v-for="[day, evs] in days" :key="day" class="day">
      <div class="dh">{{ fmtDay(day) }}</div>
      <div v-for="e in evs" :key="e.id" class="ev glass">
        <span class="ic">{{ ICON[e.type] }}</span>
        <div class="body"><div class="ti">{{ e.title }}</div><div class="meta">{{ fmtTime(e.start) }}<template v-if="e.end"> – {{ fmtTime(e.end) }}</template><template v-if="e.location"> · {{ e.location }}</template></div></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cal { display: flex; flex-direction: column; gap: 16px; }
.dh { font-size: 12px; text-transform: uppercase; letter-spacing: .08em; color: #cabfb0; margin: 0 0 6px; }
.ev { display: flex; gap: 12px; padding: 12px 14px; border-radius: 14px; margin-bottom: 8px; }
.ic { font-size: 18px; }
.ti { font-weight: 600; color: var(--ink); }
.meta { font-size: 12.5px; color: var(--ink-soft); }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/plan/ItineraryView.vue
git commit -m "feat(frontend): itinerary/calendar view grouped by day"
```

---

### Task 8.3: OfferCard + PlanEditBar

**Files:**
- Create: `frontend/src/components/plan/OfferCard.vue`, `PlanEditBar.vue`

- [ ] **Step 1: `OfferCard.vue`** (renders a flight / hotel / tour selection)

```vue
<script setup lang="ts">
import type { FlightSel, HotelSel, TourSel } from '../../api/types'
const props = defineProps<{ flight?: FlightSel; hotel?: HotelSel; tour?: TourSel }>()
const rub = (n?: number) => (n == null ? '' : n.toLocaleString('ru-RU') + ' ₽')
</script>
<template>
  <div class="card glass">
    <template v-if="flight">
      <div class="h">✈️ {{ flight.origin_city }} → {{ flight.destination }}</div>
      <div class="r">{{ flight.departure_time }}–{{ flight.arrival_time }} · {{ flight.stops === 0 ? 'без пересадок' : flight.stops + ' пересадк.' }} · {{ flight.baggage_included ? 'багаж включён' : 'без багажа' }}</div>
      <div class="p">{{ rub(flight.price_rub) }}</div>
    </template>
    <template v-else-if="hotel">
      <div class="h">🏨 Отель {{ hotel.stars }}★ · {{ hotel.rating }}/10</div>
      <div class="r">{{ hotel.nights }} ночей · {{ hotel.breakfast_included ? 'завтрак' : 'без завтрака' }} · {{ hotel.free_cancellation ? 'отмена бесплатно' : '' }}</div>
      <div class="p">{{ rub(hotel.price_per_night_rub) }}/ночь</div>
    </template>
    <template v-else-if="tour">
      <div class="h">🗺 Тур: {{ tour.destination }}</div>
      <div class="r">{{ tour.includes_flight ? 'перелёт включён' : 'без перелёта' }} · {{ tour.includes_transfer ? 'трансфер' : '' }}</div>
      <div class="p">{{ rub(tour.total_price_rub) }}</div>
    </template>
  </div>
</template>
<style scoped>
.card { padding: 14px 16px; border-radius: 14px; }
.h { font-weight: 600; color: var(--ink); }
.r { font-size: 13px; color: var(--ink-soft); margin: 4px 0; }
.p { font-weight: 700; color: var(--accent-press); }
</style>
```

- [ ] **Step 2: `PlanEditBar.vue`** (stage add/remove points, submit modify)

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { usePlansStore } from '../../stores/plans'
const props = defineProps<{ planId: string; editable: boolean }>()
const emit = defineEmits<{ rebuild: [runId: string] }>()
const plans = usePlansStore()
const newPoint = ref('')
function add() { if (newPoint.value.trim()) { plans.stageAdd(newPoint.value.trim()); newPoint.value = '' } }
async function submit() { const runId = await plans.modify(props.planId); emit('rebuild', runId) }
</script>
<template>
  <div class="bar glass" :class="{ disabled: !editable }">
    <div class="row">
      <input v-model="newPoint" class="in" :disabled="!editable" placeholder="Добавить точку (город)…" @keydown.enter="add" />
      <button class="add" :disabled="!editable" @click="add">＋</button>
    </div>
    <div v-if="plans.pendingAdd.length" class="staged">
      <span v-for="p in plans.pendingAdd" :key="p.id" class="tag">＋ {{ p.name }}</span>
    </div>
    <p v-if="!editable" class="note">Изменять можно только готовый план.</p>
    <button class="rebuild" :disabled="!editable || !plans.hasEdits()" @click="submit">Перестроить маршрут</button>
  </div>
</template>
<style scoped>
.bar { padding: 14px; border-radius: 14px; display: flex; flex-direction: column; gap: 8px; }
.row { display: flex; gap: 8px; }
.in { flex: 1; padding: 9px 12px; border: none; border-radius: 10px; background: rgba(255,255,255,.4); color: var(--ink); }
.add { width: 38px; border: none; border-radius: 10px; background: var(--accent); color: #fff; cursor: pointer; }
.staged { display: flex; flex-wrap: wrap; gap: 6px; }
.tag { font-size: 12px; padding: 4px 9px; border-radius: 999px; background: rgba(217,119,87,.18); color: var(--accent-press); }
.note { margin: 0; font-size: 12px; color: var(--ink-soft); }
.rebuild { padding: 10px; border: none; border-radius: 10px; background: var(--accent); color: #fff; font-weight: 600; cursor: pointer; }
.rebuild:disabled { opacity: .5; cursor: default; }
</style>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/plan/OfferCard.vue frontend/src/components/plan/PlanEditBar.vue
git commit -m "feat(frontend): offer cards and plan edit bar"
```

---

### Task 8.4: PlanView (assembles map + itinerary + offers + actions)

**Files:**
- Replace: `frontend/src/components/plan/PlanView.vue`

- [ ] **Step 1: Implement `PlanView.vue`**

```vue
<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import MapView from './MapView.vue'
import ItineraryView from './ItineraryView.vue'
import OfferCard from './OfferCard.vue'
import PlanEditBar from './PlanEditBar.vue'
import Skeleton from '../ui/Skeleton.vue'
import { usePlansStore } from '../../stores/plans'
import { useChatStore } from '../../stores/chat'
import { useToasts } from '../../composables/useToasts'
import { ApiClientError } from '../../api/client'

const props = defineProps<{ planId: string }>()
const plans = usePlansStore(); const chat = useChatStore(); const router = useRouter(); const { push } = useToasts()
const tab = ref<'map' | 'cal'>('map')
const rub = (n?: number) => (n == null ? '' : n.toLocaleString('ru-RU') + ' ₽')

onMounted(() => plans.load(props.planId))
watch(() => props.planId, id => plans.load(id))

async function accept() { try { await plans.accept(props.planId); push({ kind: 'success', text: 'План принят' }) } catch (e) { push({ kind: 'error', text: e instanceof ApiClientError ? e.message : 'Ошибка' }) } }
async function reject() { await plans.reject(props.planId); push({ kind: 'info', text: 'План отклонён' }) }
async function onRebuild() {
  // poll the rebuilt plan a moment after the mock flips it back to ready
  setTimeout(() => plans.load(props.planId), 400)
  push({ kind: 'info', text: 'Перестраиваю маршрут…' })
}
</script>

<template>
  <div class="plan">
    <header class="top">
      <button class="back glass" @click="router.back()">←</button>
      <div v-if="plans.current" class="ti">
        <h1>{{ plans.current.destination || 'Маршрут' }}</h1>
        <span class="status" :data-s="plans.current.status">{{ plans.current.status }}</span>
      </div>
    </header>

    <div v-if="plans.loading || !plans.current" class="grid">
      <Skeleton h="60vh" /><div><Skeleton h="22px" /><Skeleton h="120px" /></div>
    </div>

    <div v-else class="grid">
      <section class="left glass">
        <div class="tabs">
          <button :class="{ on: tab === 'map' }" @click="tab = 'map'">Карта</button>
          <button :class="{ on: tab === 'cal' }" @click="tab = 'cal'">Расписание</button>
        </div>
        <div class="canvas">
          <MapView v-show="tab === 'map'" :points="plans.map?.points ?? plans.current.map_points" />
          <ItineraryView v-if="tab === 'cal'" :events="plans.calendar?.events ?? []" :timezone="plans.calendar?.timezone" />
        </div>
      </section>

      <aside class="right">
        <div class="summary glass">
          <p class="rat">{{ plans.current.decision_rationale }}</p>
          <div class="total">Итого ≈ <b>{{ rub(plans.current.estimated_total_rub) }}</b></div>
        </div>
        <OfferCard v-if="plans.current.items.flight" :flight="plans.current.items.flight" />
        <OfferCard v-if="plans.current.items.hotel" :hotel="plans.current.items.hotel" />
        <OfferCard v-if="plans.current.items.tour" :tour="plans.current.items.tour" />
        <PlanEditBar :plan-id="planId" :editable="plans.map?.editable ?? false" @rebuild="onRebuild" />
        <div class="actions">
          <button class="accept" :disabled="plans.current.status !== 'ready'" @click="accept">Принять</button>
          <button class="reject" @click="reject">Отклонить</button>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.plan { position: fixed; inset: 0; overflow: auto; padding: 76px 22px 26px; }
.top { position: fixed; top: 18px; left: 76px; right: 22px; z-index: 5; display: flex; align-items: center; gap: 14px; }
.back { width: 40px; height: 40px; border: none; border-radius: 12px; cursor: pointer; }
.ti { display: flex; align-items: baseline; gap: 12px; }
h1 { margin: 0; font-size: 22px; color: #fff; text-shadow: 0 1px 12px rgba(0,0,0,.5); }
.status { font-size: 12px; padding: 3px 9px; border-radius: 999px; background: rgba(255,255,255,.25); color: #fff; }
.grid { display: grid; grid-template-columns: 1.6fr 1fr; gap: 16px; max-width: 1200px; margin: 0 auto; }
@media (max-width: 860px) { .grid { grid-template-columns: 1fr; } }
.left { border-radius: 18px; padding: 10px; display: flex; flex-direction: column; min-height: 60vh; }
.tabs { display: flex; gap: 6px; padding: 4px; }
.tabs button { flex: 1; padding: 8px; border: none; border-radius: 10px; background: transparent; color: var(--ink-soft); cursor: pointer; }
.tabs button.on { background: rgba(255,255,255,.45); color: var(--ink); font-weight: 600; }
.canvas { flex: 1; padding: 6px; min-height: 56vh; }
.right { display: flex; flex-direction: column; gap: 12px; }
.summary { padding: 16px; border-radius: 16px; }
.rat { margin: 0 0 10px; color: var(--ink); font-size: 14px; }
.total { color: var(--ink); } .total b { color: var(--accent-press); }
.actions { display: flex; gap: 10px; }
.accept { flex: 1; padding: 12px; border: none; border-radius: 12px; background: var(--accent); color: #fff; font-weight: 600; cursor: pointer; }
.accept:disabled { opacity: .5; cursor: default; }
.reject { padding: 12px 16px; border: none; border-radius: 12px; background: rgba(0,0,0,.12); color: var(--ink); cursor: pointer; }
</style>
```

- [ ] **Step 2: Verify** — open a plan (`/plans/PL-0001` or via the side panel). Map shows the route with markers; "Расписание" tab shows the day-by-day itinerary; offers + rationale + total render; "Добавить точку" + "Перестроить маршрут" works; Accept flips status. On a narrow window the grid stacks.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/plan/PlanView.vue
git commit -m "feat(frontend): plan view (map + itinerary + offers + edit + actions)"
```

---

## Phase 9 — Polish, removals, docs (closing barrier)

### Task 9.1: Reduced-motion & responsive pass

**Files:**
- Modify: `frontend/src/components/chat/ChatView.vue`, `frontend/src/components/layout/SidePanel.vue` (mobile width)

- [ ] **Step 1: Make the side panel full-width on small screens**

In `SidePanel.vue` `<style scoped>` append:
```css
@media (max-width: 480px) { .panel { width: 100vw; border-radius: 0; } }
```

- [ ] **Step 2: Ensure hero font scales on small screens** — in `ChatView.vue` append to styles:
```css
@media (max-width: 600px) { .hero h1 { font-size: 28px; } .thread { width: 94%; } }
```

- [ ] **Step 3: Verify reduced motion** — in the browser devtools enable "prefers-reduced-motion"; confirm the composer jump and panel slide are instant (the global rule in `glass.css` handles this), background lens still works.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/chat/ChatView.vue frontend/src/components/layout/SidePanel.vue
git commit -m "polish(frontend): responsive side panel and hero, reduced-motion check"
```

---

### Task 9.2: Remove the old background system & assets

**Files:**
- Delete: `frontend/src/components/PageBackground/**`, `frontend/src/assets/images/**`, `frontend/src/assets/images_backup/**`, `frontend/src/assets/hero.png`, `frontend/src/SPEC.md`

- [ ] **Step 1: Confirm nothing imports the old system**

Run: `cd frontend && grep -rn "PageBackground\|assets/hero\|assets/images" src || echo "clean"`
Expected: `clean` (App.vue no longer references them).

- [ ] **Step 2: Delete the files**

```bash
cd frontend
git rm -r src/components/PageBackground src/assets/images src/assets/images_backup src/assets/hero.png src/SPEC.md
```

- [ ] **Step 3: Typecheck + build to confirm nothing broke**

Run: `pnpm vue-tsc --noEmit && pnpm build`
Expected: success.

- [ ] **Step 4: Commit**

```bash
git commit -m "chore(frontend): remove old torn-magazine background system and assets"
```

---

### Task 9.3: SPECIFICATION.md updates (per AGENTS.md)

**Files:**
- Create: `frontend/SPECIFICATION.md`
- Modify: root `SPECIFICATION.md`

- [ ] **Step 1: Create `frontend/SPECIFICATION.md`** describing the current module state

Include: stack (Vue 3 + TS + Vite + Tailwind v4 + Pinia + Vue Router + MapLibre + MSW); the dithered background system (prerender script + `public/backgrounds` layers + CSS-mask lens, random on load); glass design system (single token: white 30% / blur 7px / no border; composer radius 90/18); routes (`/login`, `/`, `/c/:id`, `/plans/:id`) with auth guard; chat run flow (POST /chat → ticket → fetch-SSE → reduce); side panel (history/groups/plans); plan view (map + itinerary + edit); the MSW mock standing in for the backend; how to run (`pnpm dev`), regenerate backgrounds (`pnpm prerender:bg`), and regenerate API types (`pnpm gen:api`); tests (`pnpm test`).

- [ ] **Step 2: Update root `SPECIFICATION.md`**

In the module table change the Frontend row Status to: "Implemented: chat UI, dithered backgrounds, side panel, plan map/calendar, auth — all mock-backed (MSW)." In §2.3 replace the "torn magazine scrapbook / API client not built" text with a 2-3 sentence summary pointing to `frontend/SPECIFICATION.md`. Update the module table spec link from `frontend/src/SPEC.md` to `frontend/SPECIFICATION.md`.

- [ ] **Step 3: Commit**

```bash
git add SPECIFICATION.md frontend/SPECIFICATION.md
git commit -m "docs: frontend SPECIFICATION and root index reflect implemented frontend"
```

---

### Task 9.4: Final verification

- [ ] **Step 1: Full test suite** — Run: `cd frontend && pnpm test`. Expected: all specs pass.
- [ ] **Step 2: Typecheck + production build** — Run: `pnpm vue-tsc --noEmit && pnpm build`. Expected: success.
- [ ] **Step 3: Manual smoke (dev)** — Run: `pnpm dev`. Walk the flow: login → centered composer → send → animates to bottom, streamed reply + clarifying chips → answer → plan builds → open plan → map + itinerary + edit + accept → side panel history/groups/plans → logout. Confirm 60fps background and cursor lens throughout.
- [ ] **Step 4: Commit any fixes** discovered during smoke, then stop.

---

## Self-review notes (coverage)

- Spec §3 shell, §4 background, §5 glass, §6 layout/animation, §7 chat/SSE/clarifying, §8 mock (auth/sessions/groups/plans/map/calendar/SSE), §9 stores/client/types/router, §10 component map, §11 removals, §12 a11y/perf, §13 tests, §14 SPECIFICATION updates, §15 subagent-driven + UX bar — each maps to tasks above (Phases 0–9).
- Map + calendar + auth + plan editing are all implemented and mock-backed (the expanded scope), nothing deferred except a real backend.
- Type names are consistent with `src/api/types.ts` aliases throughout; store method names referenced by views (`load`, `accept`, `modify`, `send`, `answer`, `hydrate`, `reset`) match their definitions.
