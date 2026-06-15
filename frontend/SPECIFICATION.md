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
| Routing | Vue Router 5 |
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
- **Component:** `src/components/background/DitheredBackground.vue` — picks a random scene on each load, stacks the two layers; the color layer is revealed under the cursor by `useCursorLens` (radial-gradient masks). On mount it also sets the global `--accent` / `--accent-press` tokens from a per-scene `ACCENTS` map (china=jade, russia=blue, usa=dark blue, india=soft pink, japan=reddish pink, italy=terracotta, france=vibrant gold, greece=Aegean blue), so all accent-tinted UI (buttons, user bubbles, map route, links) matches the active background.
- **Cursor lens composable:** `src/composables/useCursorLens.ts` — listens to `pointermove` and imperatively writes a stack of radial-gradient mask layers onto the color `<img>` once per `requestAnimationFrame`: a fully-revealed head under the cursor plus a sampled trail of recent positions whose mask alpha decays over each point's own lifetime, so the revealed streak fades out behind the cursor. Each trail point fades over `TRAIL_MS` (≈1600 ms). The behaviour is a single hover effect — there is no mouse-button interaction. The reveal radius scales with cursor speed (eased from `LEAK_RADIUS` up to `MAX_RADIUS`). Collapses to just the head (no trail) under `prefers-reduced-motion`. `lensGradient(a)` builds an alpha-scaled gradient; `lensVars(x, y, r)` is pure and tested.

## 3. Glass design system

Single token defined in `src/styles/glass.css`, imported by `src/style.css`:

- `.glass` — `background: rgba(255,255,255,0.38)`, `backdrop-filter: blur(10px) saturate(1)`, `box-shadow: 0 18px 50px rgba(0,0,0,0.35)`. No border. This is the only frosted-glass surface variant.
- `.glass-dark` — darker variant for toasts/controls that sit on light frost.
- CSS custom properties: `--accent` / `--accent-press` (default terracotta #d97757 / #cf5f3f, overridden at runtime by `DitheredBackground` to match the active scene), `--bg-base` (#0c0a08), `--ink` (#241c14), `--ink-soft` (rgba(40,30,20,0.55)), plus the glass spec vars.
- Interaction tokens: `--ease` (shared easing), `--tap` (the standard control transition), `--accent-glow` / `--accent-glow-press` (hover/pressed shadows, derived from `--accent` via `color-mix` so they follow the scene accent). All interactive controls use these for a uniform hover (lift + brightness + shadow) and pressed (`scale .97`) feel, guarded by `@media (hover: hover)` and `:not(:disabled)`.
- Global `prefers-reduced-motion` rule collapses all animation and transition durations to 0.001 ms.

## 4. App entry and routing

- **`src/main.ts`** — bootstraps MSW (in `DEV` or `VITE_USE_MOCKS=true`) before mounting the Vue app with Pinia and Vue Router. An explicit `VITE_USE_MOCKS=false` opts out of mocks even in dev, so the dev server talks to the real backend at `VITE_API_BASE` (e.g. `http://localhost:8000/api/v1`); see `.env.example`. Production builds never start MSW.
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

- **`AppShell.vue`** — fixed full-screen chrome: `DitheredBackground` (z-index 0), `MenuButton` (top-left, z-index 30, shown only when authenticated and hidden via `v-show` while the panel is open), the `КудаЕдем` wordmark logo (`src/assets/logo.png`, top-right, z-index 30, rendered white via `brightness(0) invert(1)` + drop-shadow so it reads over any scene), `SidePanel` (rendered only when authenticated; panel z-index 35 over a click-to-close scrim at z-index 30), `<main class="pane">` slot for `<RouterView>` (z-index 1), `ToastHost` (z-index 100).
- **`MenuButton.vue`** — hamburger button; emits `toggle`.
- **`SidePanel.vue`** — slides in from the left (transition `translateX(-104%)`) above the menu button, over a dimmed scrim that closes the panel on click; 308 px wide, full-width on ≤ 480 px (`border-radius: 0`). Contains: header (title + ✕ close button), "New chat" button, search input, scrollable `GroupList` / `PlanList` / `SessionList` (top-to-bottom order), logout button. Closes on ✕, scrim click, `Escape`, list navigation, new-chat, or logout.
- **`SessionList.vue`**, **`GroupList.vue`**, **`PlanList.vue`** — list sub-components for the side panel; each pulls from its Pinia store and filters by the `filter` prop. `GroupList` and `PlanList` wrap their items in **`CollapsibleSection.vue`** (an accordion: the header toggles the body open/closed, and the body shows the most-recent items capped at ~3 rows tall, scrolling for the rest).

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
| `sse.ts` | `parseEventStream(body)` — async generator over a `ReadableStream<Uint8Array>` that accepts LF and CRLF SSE frame endings, including CRLF split across chunks and a final unterminated frame; `streamRun(args)` opens the ticket-authenticated SSE endpoint. Tested. |
| `endpoints.ts` | One typed function per OpenAPI operation; exports `api` object and `setTokenGetter`. |

## 8. Pinia stores

All in `src/stores/`:

| Store | Key state | Key actions |
|---|---|---|
| `auth.ts` | `user`, `accessToken`, `ready`, `isAuthenticated` | `restore()`, `login()`, `register()`, `logout()`, `refreshAccess()` |
| `sessions.ts` | `list: SessionSummary[]`, `current: SessionDetail \| null` | `loadList()`, `loadDetail(id)` |
| `groups.ts` | `list: GroupSummary[]`, `current: Group \| null` | `loadList()`, `loadOne(id)` |
| `plans.ts` | `current: Plan \| null`, `map`, `calendar`, `loading`, `pendingAdd` | `load(id)`, `accept(id)`, `reject(id)`, `modify(id)`, `stageAdd(city)`, `hasEdits()` |
| `chat.ts` | `messages`, `sessionId`, `pendingQuestion`, `planStatus`, `planId`, `running` | `send(text)`, `answer(qId, optIds, freeform)`, `hydrate(id, msgs)`, `reset()`, `waitForIdle()` |

`send`/`answer` resolve with the `ChatAccepted` (`run_id`, `session_id`) **as soon as the run is accepted** (set `sessionId` early) and stream the reply into the same store in the background; `waitForIdle()` resolves when that background run finishes. Each run is tracked by an `AbortController` and a run token: starting a new run, calling `reset()` (new-chat / session switch), or hydrating an existing session aborts the in-flight stream, clears `running`, and bumps the token so the stale loop stops mutating the store — no cross-talk into the next chat. Hydration also clears live-only `planStatus`/`planId`, and starting a new run clears stale pending-question and plan state before streaming begins. The stream loop **does not break on a terminal `run_status`** — it drains until the server closes the connection, so a `message` emitted after `run_status: completed` is not lost (no manual reload needed). A well-formed `error` SSE frame sets `planStatus` to `error` and surfaces a toast rather than closing silently, but a streamed assistant reply from the same run takes precedence over the generic live plan-error fallback so the live thread matches the persisted reload view. `hydrate()` shows a trailing clarifying-question message only as the question panel, never also as a plain bubble (no duplicate). When a new run starts (`send`/`answer`), any still-pending clarifying question is first demoted to a plain assistant bubble (its text) — mirroring `hydrate()`, which renders every non-trailing question as a bubble — so an answered or superseded question stays in the live thread instead of disappearing until a reload.

All stores are tested (`*.spec.ts` co-located).
`auth.restore()` clears in-memory access state when the persisted token cannot be restored (for
example, `/auth/me` returns 401), matching logout cleanup semantics.

## 9. Mock backend (MSW)

All files under `src/mocks/`:

- **`geo.ts`** — city name → `{lat, lng}` lookup for 12 Russian/international cities.
- **`seed.ts`** — `createDb()` builds the in-memory database: 1 demo user (`demo@travel.app` / `password`), 2 groups, 2 sessions, 1 ready plan (`PL-0001`) with map points. Exported `sessionSummary()` helper. Tested.
- **`sse-script.ts`** — `buildRunFrames(spec)` returns an ordered array of `SseEvent` objects for a scripted run: `first` kind emits a clarifying question; `answer`/`rebuild` kind builds a plan with map points and a final `message`. Tested.
- **`handlers.ts`** — MSW request handlers implementing every endpoint: auth (register/login/refresh/logout/me), chat (POST /chat → run, stream ticket, cancel, SSE stream), sessions, groups, plans (CRUD + map + calendar + accept/reject/modify). Tested.
- **`browser.ts`** — `setupWorker(...handlers)` for the browser service worker.

## 10. Feature views

### Chat (`src/components/chat/`)

- **`ChatView.vue`** — route-level component. Hero state (composer centred at 48%, `Куда отправимся?` heading) transitions to chatting state (composer at bottom, message thread visible) when the first message is sent. The centre→bottom slide is gated behind an `animate` flag set only on that first send, so a direct load (`/c/:id`) — which hydrates messages already "started" — renders the composer at the bottom immediately instead of sliding down over already-loaded bubbles. The hero block is likewise gated to the home route (`heroVisible = !started && !sessionId`), so it never flashes over the bubbles while a session route hydrates. The `sessionId` watcher skips re-hydration when the route param already matches the live store session, so live state (e.g. a pending clarifying question) survives the `router.replace` after the first message. On the first message it calls `router.replace('/c/:id')` **immediately after the run is accepted** (not after the whole agent run), so the URL reflects the new chat right away while the reply streams in. After each completed run it calls `sessions.loadList()` so a newly started chat appears in the side-panel history without a reload. Responsive: `font-size: 28px` for the heading and `width: 94%` for the thread on ≤ 600 px.
- When a clarifying question is pending, the main composer submits text through `chat.answer(question.id, [], text)` rather than starting a fresh chat turn, so freeform clarification replies keep the correct answer context.
- **`ChatComposer.vue`** — textarea with auto-grow and send button; emits `submit(text)`. While `busy` (a run is in flight) the textarea is disabled and shows an "Агент отвечает…" placeholder, and the send button is disabled.
- **`MessageList.vue`** — scrollable list; renders `MessageBubble` per message, an animated "thinking" indicator while `running` is set and no text is streaming yet (covers the live backend, which emits one final `message` with no `message_delta` chunks), `ClarifyingQuestion` when `question` prop is set, `PlanStatus` when `planStatus` is set. Assistant bubbles carry no drop shadow.
- **`MessageBubble.vue`** — user/assistant bubble with optional `plan_ref` link to the plan view and a small `HH:MM` (ru-RU) timestamp from the message's `created_at`. Body text is rendered via `MarkdownText`; while `streaming` it passes the `streaming` class so the blinking typing caret tracks the end of the text. Assistant bubbles carry no drop shadow.
- **`MarkdownText.vue`** — the single Markdown renderer for chat text (assistant bubbles + clarifying-question prompt). Parses with `marked` (`gfm: true`, `breaks: true` — a single `\n` becomes `<br>`, `\n\n` starts a paragraph, `1.`/`-` render as lists) and sanitizes the result with `DOMPurify` before the lone `v-html` in the app. Renders immediately, so live (un-reloaded) text respects newlines and `.md` formatting. When given the `streaming` class it appends a blinking caret after the last block.
- **`ClarifyingQuestion.vue`** — renders the question prompt via `MarkdownText` (newlines + Markdown honoured live), option chips + optional freeform input; emits `answer(optionIds, freeform)`.
- **`PlanStatus.vue`** — live status badge (`building` / `ready` / `error`) with a link to the plan when ready.

### Auth (`src/components/auth/AuthView.vue`)

Login/register form (tab-switched). On success navigates to the `redirect` query param or `/`.

### Side panel lists

- **`SessionList.vue`** — renders session history with each chat's creation time (Russian locale: time only when created today, otherwise short date + time, e.g. `27 янв. 14:37`); filter by `filter` prop; navigates to `/c/:id`.
- **`GroupList.vue`** — renders groups (most recent first) inside a `CollapsibleSection`; filters by the `filter` prop. Group rows are currently display-only (name + member count) and not navigable — there is no group-detail route.
- **`PlanList.vue`** — renders plans across the user's groups (most recent first) inside a `CollapsibleSection`; filters by destination via the `filter` prop; navigates to `/plans/:id`.
- **`CollapsibleSection.vue`** — accordion wrapper: a clickable header (chevron + title) toggles a scrollable body capped at ~3 visible rows.

### Plan view (`src/components/plan/`)

- **`PlanView.vue`** — fixed full-screen layout: sticky header (back button + destination + status), two-column grid (map/itinerary pane left, details right; stacks on ≤ 860 px). Loads plan + map + calendar on mount.
- **`MapView.vue`** — MapLibre GL canvas rendering `MapPoint[]` as accent-coloured pin markers with popups, plus a dashed accent route line. Basemap is CARTO's free (no-API-key) **vector** dark style; on load every symbol layer's `text-field` is rewritten to `coalesce(name:ru, name)` so map labels display in Russian. Plan status text is localised via `utils/planStatus.ts` (`planStatusLabel`), shared with the side-panel `PlanList`.
- **`ItineraryView.vue`** — day-grouped list of `CalendarEvent[]` with time, title, location, and notes (description). `CalendarEvent` carries no price field, so none is shown.
- **`OfferCard.vue`** — renders a `FlightSel`, `HotelSel`, or `TourSel` in a glass card.
- **`PlanEditBar.vue`** — input to stage `AddPoint` cities + "Rebuild route" button; calls `plans.modify()` and emits `rebuild(runId)`.

## 11. Test coverage

18 spec files co-located with sources (22 tests). Run with `pnpm test` (Vitest, jsdom environment):

- `api/client.spec.ts` — HTTP client (bearer token, error envelope)
- `api/sse.spec.ts` — SSE stream parser
- `composables/useToasts.spec.ts` — toast lifecycle
- `composables/useCursorLens.spec.ts` — lens variable computation
- `mocks/seed.spec.ts` — seed database factory
- `mocks/sse-script.spec.ts` — scripted SSE frames
- `mocks/handlers.spec.ts` — MSW handler integration (login + me + sessions)
- `stores/auth.spec.ts`, `sessions.spec.ts`, `groups.spec.ts`, `plans.spec.ts`, `chat.spec.ts` — Pinia store unit tests
- `components/chat/ChatView.spec.ts` — chat-flow regression tests (reply visible without reload, message-after-`run_status` not dropped, no duplicated clarifying question on hydrate, input disabled while running)

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
    styles/glass.css                   .glass token + .glass-dark + CSS vars + interaction tokens + reduced-motion
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
      useCursorLens.ts  (+ .spec.ts)   Cursor → fading reveal-trail mask layers via rAF
      useToasts.ts      (+ .spec.ts)   Toast singleton composable
    components/
      background/DitheredBackground.vue
      layout/AppShell.vue MenuButton.vue SidePanel.vue
              SessionList.vue GroupList.vue PlanList.vue CollapsibleSection.vue
      ui/GlassPanel.vue Skeleton.vue EmptyState.vue ToastHost.vue
      auth/AuthView.vue
      chat/ChatView.vue ChatComposer.vue MessageList.vue MessageBubble.vue
           MarkdownText.vue ClarifyingQuestion.vue PlanStatus.vue
      plan/PlanView.vue MapView.vue ItineraryView.vue OfferCard.vue PlanEditBar.vue
      AgentChat/                       Legacy prototype components (not used by main app)
    assets/
      vite.svg  vue.svg                Default Vite template icons (unused by app)
    test-setup.ts                      Vitest global setup
```
