# Frontend Module — Specification

**Status:** Implemented — chat UI, dithered backgrounds, side panel, plan map/calendar, auth — all mock-backed (MSW).

This document describes the current implemented state of the `frontend/` module. Keep it in sync with the code; a spec that no longer matches the code is a bug.

## 1. Tech stack

| Concern | Choice |
|---|---|
| Framework | Vue 3.5 — `<script setup lang="ts">` throughout (Composition API) |
| Build tool | Vite 8 |
| Styling | Tailwind v4 + scoped CSS per component |
| State management | Pinia |
| Routing | Vue Router 4 |
| Map | MapLibre GL |
| Mock backend | MSW 2 (browser service worker) |
| API types | `openapi-typescript` — generated from `../api/openapi.yaml` |
| Tests | Vitest + Vue Test Utils + jsdom |
| Canvas (prerender) | `@napi-rs/canvas` (Node; not bundled into the app) |

Run commands:

```bash
pnpm dev            # start dev server (boots MSW automatically)
pnpm build          # production build (vue-tsc then vite build)
pnpm test           # run all specs
pnpm prerender:bg   # regenerate public/backgrounds/*.webp (requires @napi-rs/canvas)
pnpm gen:api        # regenerate src/api/schema.d.ts from ../api/openapi.yaml
```

## 2. Dithered background system

- **Prerender script:** `scripts/prerender-backgrounds.mjs` — uses `@napi-rs/canvas` to render 8 travel scenes (france, greece, italy, japan, china, india, russia, usa) as dithered images.
- **Output:** `public/backgrounds/<scene>-mono.webp` (grayscale dithered) and `<scene>-color.webp` (full-color dithered). 16 files total, served as static assets.
- **Component:** `src/components/background/DitheredBackground.vue` — picks a random scene on each load, stacks the two layers; the color layer is masked with a CSS radial-gradient (lens) whose position/size is driven by CSS custom properties (`--mpx`, `--mpy`, `--d`).
- **Cursor lens composable:** `src/composables/useCursorLens.ts` — listens to `pointermove`, writes `--mpx`/`--mpy`/`--d` onto the color `<img>` element once per `requestAnimationFrame`. `lensVars(x, y, r)` is pure and tested.

## 3. Glass design system

Single token defined in `src/styles/glass.css`, imported by `src/style.css`:

- `.glass` — `background: rgba(255,255,255,0.30)`, `backdrop-filter: blur(7px) saturate(1)`, `box-shadow: 0 18px 50px rgba(0,0,0,0.35)`. No border. This is the only frosted-glass surface variant.
- `.glass-dark` — darker variant for toasts/controls that sit on light frost.
- CSS custom properties: `--accent` (#d97757), `--accent-press` (#cf5f3f), `--bg-base` (#0c0a08), `--ink` (#241c14), `--ink-soft` (rgba(40,30,20,0.55)), plus the glass spec vars.
- Global `prefers-reduced-motion` rule collapses all animation and transition durations to 0.001 ms.

## 4. App entry and routing

- **`src/main.ts`** — bootstraps MSW (in `DEV` or `VITE_USE_MOCKS=true`) before mounting the Vue app with Pinia and Vue Router.
- **`src/App.vue`** — thin shell: renders `<AppShell><RouterView /></AppShell>`.
- **`src/router/index.ts`** — four routes:

| Name | Path | Component | Guard |
|---|---|---|---|
| `login` | `/login` | `AuthView` | public |
| `chat` | `/` | `ChatView` | auth required |
| `session` | `/c/:sessionId` | `ChatView` | auth required |
| `plan` | `/plans/:planId` | `PlanView` | auth required |

The `beforeEach` guard lazily imports `useAuthStore`, calls `auth.restore()` on first navigation, and redirects unauthenticated users to `/login`.

## 5. App shell and layout components

- **`AppShell.vue`** — fixed full-screen chrome: `DitheredBackground` (z-index 0), `MenuButton` (top-left, z-index 10), `SidePanel` (z-index 25), `<main class="pane">` slot for `<RouterView>` (z-index 1), `ToastHost` (z-index 100).
- **`MenuButton.vue`** — hamburger button; emits `toggle`.
- **`SidePanel.vue`** — slides in from the left (transition `translateX(-104%)`); 308 px wide, full-width on ≤ 480 px (`border-radius: 0`). Contains: title, "New chat" button, search input, scrollable `SessionList` / `GroupList` / `PlanList`, logout button.
- **`SessionList.vue`**, **`GroupList.vue`**, **`PlanList.vue`** — list sub-components for the side panel; each pulls from its Pinia store and filters by the `filter` prop.

## 6. UI primitives

All in `src/components/ui/`:

- **`GlassPanel.vue`** — `<div class="glass">` wrapper with configurable `border-radius`.
- **`Skeleton.vue`** — shimmer placeholder (animated gradient); accepts `w`/`h` props.
- **`EmptyState.vue`** — centered `title` + optional `hint` message.
- **`ToastHost.vue`** — fixed bottom-center overlay; renders toasts from `useToasts` composable; click to dismiss.

Composables in `src/composables/`:

- **`useToasts.ts`** — module-level singleton `ref<Toast[]>`; `push({ kind, text, ttl })` auto-removes after `ttl` ms (default 4000); tested.
- **`useCursorLens.ts`** — described in §2 above; tested.

## 7. API layer

All files under `src/api/`:

| File | Purpose |
|---|---|
| `schema.d.ts` | Generated from `../api/openapi.yaml` via `openapi-typescript`. Do not edit manually. |
| `types.ts` | Friendly type aliases over `schema.d.ts`; discriminated `SseEvent` union on the event name field. |
| `client.ts` | `createClient(opts)` — fetch wrapper; attaches Bearer token, parses JSON, maps non-OK responses to `ApiClientError` carrying status/code/details. Tested. |
| `sse.ts` | `parseEventStream(body)` — async generator over a `ReadableStream<Uint8Array>`; `streamRun(args)` opens the ticket-authenticated SSE endpoint. Tested. |
| `endpoints.ts` | One typed function per OpenAPI operation; exports `api` object and `setTokenGetter`. |

## 8. Pinia stores

All in `src/stores/`:

| Store | Key state | Key actions |
|---|---|---|
| `auth.ts` | `user`, `accessToken`, `ready`, `isAuthenticated` | `restore()`, `login()`, `register()`, `logout()`, `refreshAccess()` |
| `sessions.ts` | `list: SessionSummary[]`, `current: SessionDetail \| null` | `loadList()`, `loadDetail(id)` |
| `groups.ts` | `list: GroupSummary[]`, `current: Group \| null` | `loadList()`, `loadOne(id)` |
| `plans.ts` | `current: Plan \| null`, `map`, `calendar`, `loading`, `pendingAdd` | `load(id)`, `accept(id)`, `reject(id)`, `modify(id)`, `stageAdd(city)`, `hasEdits()` |
| `chat.ts` | `messages`, `sessionId`, `pendingQuestion`, `planStatus`, `planId`, `streaming` | `send(text)`, `answer(qId, optIds, freeform)`, `hydrate(id, msgs)`, `reset()` |

All stores are tested (`*.spec.ts` co-located).

## 9. Mock backend (MSW)

All files under `src/mocks/`:

- **`geo.ts`** — city name → `{lat, lng}` lookup for 12 Russian/international cities.
- **`seed.ts`** — `createDb()` builds the in-memory database: 1 demo user (`demo@travel.app` / `password`), 2 groups, 2 sessions, 1 ready plan (`PL-0001`) with map points. Exported `sessionSummary()` helper. Tested.
- **`sse-script.ts`** — `buildRunFrames(spec)` returns an ordered array of `SseEvent` objects for a scripted run: `first` kind emits a clarifying question; `answer`/`rebuild` kind builds a plan with map points and a final `message`. Tested.
- **`handlers.ts`** — MSW request handlers implementing every endpoint: auth (register/login/refresh/logout/me), chat (POST /chat → run, stream ticket, cancel, SSE stream), sessions, groups, plans (CRUD + map + calendar + accept/reject/modify). Tested.
- **`browser.ts`** — `setupWorker(...handlers)` for the browser service worker.

## 10. Feature views

### Chat (`src/components/chat/`)

- **`ChatView.vue`** — route-level component. Hero state (composer centred at 48%, `Куда отправимся?` heading) transitions to chatting state (composer at bottom, message thread visible) when the first message is sent. Responsive: `font-size: 28px` for the heading and `width: 94%` for the thread on ≤ 600 px.
- **`ChatComposer.vue`** — textarea with auto-grow and send button; emits `submit(text)`.
- **`MessageList.vue`** — scrollable list; renders `MessageBubble` per message, `ClarifyingQuestion` when `question` prop is set, `PlanStatus` when `planStatus` is set.
- **`MessageBubble.vue`** — user/assistant bubble with optional `plan_ref` link to the plan view.
- **`ClarifyingQuestion.vue`** — renders option chips + optional freeform input; emits `answer(optionIds, freeform)`.
- **`PlanStatus.vue`** — live status badge (`building` / `ready` / `error`) with a link to the plan when ready.

### Auth (`src/components/auth/AuthView.vue`)

Login/register form (tab-switched). On success navigates to the `redirect` query param or `/`.

### Side panel lists

- **`SessionList.vue`** — renders session history; filter by `filter` prop; navigates to `/c/:id`.
- **`GroupList.vue`** — renders groups; navigates to group detail (currently shows info in side panel).
- **`PlanList.vue`** — renders plans from the active session; navigates to `/plans/:id`.

### Plan view (`src/components/plan/`)

- **`PlanView.vue`** — fixed full-screen layout: sticky header (back button + destination + status), two-column grid (map/itinerary pane left, details right; stacks on ≤ 860 px). Loads plan + map + calendar on mount.
- **`MapView.vue`** — MapLibre GL canvas rendering `MapPoint[]`; `origin` (blue), `destination` (orange), `stop` (green) markers with popups.
- **`ItineraryView.vue`** — day-grouped list of `CalendarEvent[]` with time, title, description, location, and price.
- **`OfferCard.vue`** — renders a `FlightSel`, `HotelSel`, or `TourSel` in a glass card.
- **`PlanEditBar.vue`** — input to stage `AddPoint` cities + "Rebuild route" button; calls `plans.modify()` and emits `rebuild(runId)`.

## 11. Test coverage

17 spec files co-located with sources. Run with `pnpm test` (Vitest, jsdom environment):

- `api/client.spec.ts` — HTTP client (bearer token, error envelope)
- `api/sse.spec.ts` — SSE stream parser
- `composables/useToasts.spec.ts` — toast lifecycle
- `composables/useCursorLens.spec.ts` — lens variable computation
- `mocks/seed.spec.ts` — seed database factory
- `mocks/sse-script.spec.ts` — scripted SSE frames
- `mocks/handlers.spec.ts` — MSW handler integration (login + me + sessions)
- `stores/auth.spec.ts`, `sessions.spec.ts`, `groups.spec.ts`, `plans.spec.ts`, `chat.spec.ts` — Pinia store unit tests

## 12. File structure (current)

```
frontend/
  package.json                         pnpm scripts: dev, build, test, gen:api, prerender:bg
  vitest.config.ts                     Vitest config (jsdom, globals, src/**/*.spec.ts)
  scripts/
    prerender-backgrounds.mjs          @napi-rs/canvas prerender — writes public/backgrounds/
  public/
    backgrounds/                       16 prerendered .webp files (8 scenes × mono+color)
    mockServiceWorker.js               MSW service worker
  src/
    main.ts                            Bootstrap: MSW → Pinia → Router → mount
    style.css                          Tailwind import + glass.css import + base resets
    App.vue                            Thin shell: <AppShell><RouterView /></AppShell>
    styles/glass.css                   .glass token + .glass-dark + CSS vars + reduced-motion
    router/index.ts                    Routes + beforeEach auth guard
    api/
      schema.d.ts                      GENERATED — do not edit
      types.ts                         Friendly aliases + SseEvent union
      client.ts                        createClient fetch wrapper + ApiClientError
      sse.ts                           parseEventStream + streamRun
      endpoints.ts                     api.* typed functions + setTokenGetter
    mocks/
      geo.ts                           City → {lat,lng}
      seed.ts                          createDb() in-memory DB
      sse-script.ts                    buildRunFrames() ordered SSE events
      handlers.ts                      MSW handlers (all endpoints)
      browser.ts                       setupWorker(...handlers)
    stores/
      auth.ts  sessions.ts  groups.ts  plans.ts  chat.ts  (+ *.spec.ts each)
    composables/
      useCursorLens.ts  (+ .spec.ts)   Cursor → CSS mask vars via rAF
      useToasts.ts      (+ .spec.ts)   Toast singleton composable
    components/
      background/DitheredBackground.vue
      layout/AppShell.vue MenuButton.vue SidePanel.vue
              SessionList.vue GroupList.vue PlanList.vue
      ui/GlassPanel.vue Skeleton.vue EmptyState.vue ToastHost.vue
      auth/AuthView.vue
      chat/ChatView.vue ChatComposer.vue MessageList.vue MessageBubble.vue
           ClarifyingQuestion.vue PlanStatus.vue
      plan/PlanView.vue MapView.vue ItineraryView.vue OfferCard.vue PlanEditBar.vue
      AgentChat/                       Legacy prototype components (not used by main app)
    assets/
      vite.svg  vue.svg                Default Vite template icons (unused by app)
    test-setup.ts                      Vitest global setup
```
