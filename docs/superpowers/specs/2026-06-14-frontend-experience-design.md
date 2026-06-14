# Frontend Experience — Glassmorphism Travel-Planning Chat UI

**Status:** Design (approved interactively via visual prototype; pending written-spec review).
**Date:** 2026-06-14
**Module:** `frontend/` (Vue 3 + TS + Vite + Tailwind v4).
**Consumes:** `api/openapi.yaml` (frontend↔backend contract) via a mock backend (no real backend exists yet).

---

## 1. Goal

Turn the current visual shell into a beautiful, working travel-planning **chat application**: an
immersive **dithered particle background**, a **frosted-glass** UI, a left **side panel** (history /
groups / plans), and a chat that starts **centered** and **animates to the bottom** after the first
message. Because no backend exists yet, the app runs end-to-end against a **mock** implementing the
OpenAPI contract, so it is fully demoable.

## 2. Scope

**In scope — the entire frontend, every feature mock-backed**
- Full visual rework: new dithered backgrounds (replacing the "torn magazine scrapbook" system),
  glassmorphism design system, cursor color-reveal lens.
- Chat experience: centered→bottom composer animation, streamed assistant messages, closed
  **clarifying questions** as chips, `plan_status` indicator.
- Left side panel: **История** (chat sessions), **Группы** (travel parties), **Планы** (plans), plus
  "New chat" + search.
- **Plan view** with an interactive **map** (settlements + route line) and a **calendar / itinerary**
  (flights, hotel nights, tours), plus **plan editing** (add/remove points → rebuild run) — all
  mock-backed.
- **Auth**: a lightweight glass **login / register** screen wired to the mock JWT/refresh flow.
- A **mock backend** (MSW) implementing the **whole** `api/` contract (auth, chat/run + SSE, sessions,
  groups, plans, map, calendar), with seed data drawn from `data/`.
- Typed API client generated from `api/openapi.yaml`; Pinia stores.

**Out of scope**
- The real backend / agent implementation (the mock stands in; the client is already contract-typed,
  so swapping to a real server later is a config change).

## 3. Architecture overview

A single full-viewport SPA shell:

```
┌──────────────────────────────────────────────────────────────┐
│  DitheredBackground  (fixed, full-screen, behind everything)  │
│   ├─ <img> mono+accent layer      (always visible)            │
│   └─ <img> colorized layer        (revealed by CSS-mask lens) │
│                                                                │
│  MenuButton (top-left, glass)  →  SidePanel (slides in, glass) │
│                                                                │
│  ChatView                                                      │
│   ├─ Hero (centered)        — initial state only              │
│   ├─ MessageList            — conversation state              │
│   └─ ChatComposer (glass)   — center → bottom on first send   │
└──────────────────────────────────────────────────────────────┘
```

Layers communicate through Pinia stores; the only network surface is the typed API client, which in
dev/demo is served by MSW.

## 4. Background system (validated via prototype)

**Approach:** dithered images are **prerendered offline** to two raster layers per scene; the
frontend never dithers at runtime. This gives 60fps, crispness on 4K, and zero scene-switch lag.

### 4.1 Prerender script — `frontend/scripts/prerender-backgrounds.mjs` (built)
- Discovers scenes from `frontend/src/assets/backgrounds/`: any `<name>_colorized.png` with a matching
  `<name>.png`. **Add a background later** = drop the two PNGs in and run `pnpm prerender:bg`.
- For each scene, renders two **4K** masters (3840×2161) to `frontend/public/backgrounds/`:
  - `<name>-mono.webp` — monochrome cream + **the image's own accent** (saturated focal elements keep
    their hue: gold tower, blue domes), opaque dark background baked in. The always-visible layer.
  - `<name>-color.webp` — a **faithful** dithered render of the colorized photo (dot size from the
    colorized luminance, colors saturation-boosted), **transparent** background. The reveal layer.
- **Locked parameters** (documented constants in the script):
  `OUTPUT_W=3840`, `REF_WIDTH=1800`, `DOT=3` (→ **600 dot columns**), `ACCENT=0.85`,
  `SATURATION=1.75`, WebP `q=80`. Dot density is resolution-independent (constant column count).
- Uses `@napi-rs/canvas` (added) + the `cwebp` CLI for encoding. ~2.7 MB per layer; one scene
  (~5.4 MB) loads per visit.

**Dithering algorithm (per dot cell):**
- Mono layer: dot **size** = `min(1, L^0.9 + S*0.5)` (L = base luminance, S = saturation, so dark-but-
  saturated focal elements still show); **color** = cream `[238,230,212]·(0.12+0.88·L^0.85)`, blended
  toward the lifted source color by `smoothstep(0.16,0.42,S)·ACCENT` (gates out compression speckle).
- Color layer: dot **size** = `min(1, cL^0.92)` (cL = colorized luminance — faithful tonal structure);
  **color** = colorized pixel with saturation scaled by `SATURATION`.
- Dot radius = `cell·0.62`.

### 4.2 Runtime — `DitheredBackground.vue` + `useCursorLens.ts`
- Stack the two `<img>` layers (`object-fit: cover`), pick a **random scene on load** (no swap, no
  wind — dropped per decision).
- **Cursor reveal:** a soft radial CSS **mask** on the color layer that follows the cursor, so only
  color *bleeds through* near the pointer — GPU-composited, ~0 per-frame JS (only two CSS variables
  updated in a rAF). No dot displacement.
  - `mask-image: var(--lens)`, `mask-size: 160px` (leak radius **80px**), `mask-position` tracks cursor.
  - Lens gradient (seamless tail): `radial-gradient(closest-side, rgba(0,0,0,1) 0%, .97 35%, .85 55%,
    .62 70%, .38 82%, .20 90%, .07 96%, 0 100%)`.
- `prefers-reduced-motion`: lens still allowed (it's pointer-driven, not autonomous); no other motion.

## 5. Glassmorphism design system

A **single shared glass token**, applied uniformly to every glass surface (menu button, side panel,
composer, assistant bubbles, chips):

```css
--glass-bg:        rgba(255,255,255,0.30);   /* frosted white, "whiteness" 30% */
--glass-blur:      7px;
--glass-saturate:  1;                         /* 100% */
/* no border (border strength 0); depth via shadow only */
box-shadow: 0 18px 50px rgba(0,0,0,0.35);
color: #241c14;                               /* dark text on frost */
```

- **Accent:** `#d97757` (rust) — user message bubble, primary buttons, send button.
- **Background base:** `#0c0a08`.
- **Composer corner radius:** **elliptical** `90px / 18px` (wide-arched left/right, gentle top/bottom).
  Other surfaces use ordinary radii but the same frost+blur.
- Text on glass dark (`#241c14`); placeholders `rgba(40,30,20,0.55)`; hero text white with shadow
  (sits directly on the background, not on glass).

## 6. Layout & interaction

- **Full-bleed** background; all UI floats above it.
- **MenuButton** top-left → toggles **SidePanel** (slides in from left, `translateX`, ~0.42s).
- **Initial state:** centered **Hero** ("Куда отправимся?") above a centered **ChatComposer**.
- **First message:** body gets `chat` state → composer animates `top` from center to bottom
  (~0.6s cubic-bezier), Hero fades out, **MessageList** fades in.
- **Conversation:** user bubbles (accent), assistant bubbles (glass), **clarifying-question chips**
  (glass) for closed questions; a small **plan-status** indicator (building → ready).
- App language: **Russian** (matches the product and existing placeholders).

## 7. Chat / run flow (against `api/openapi.yaml`)

Implements the async run model from the API spec:
1. `POST /chat { message, session_id?, group_id? }` → `202 { run_id, session_id }`.
2. `POST /chat/{run_id}/stream-ticket` → single-use ticket.
3. `GET /chat/{run_id}/stream?ticket=…` → SSE consumed via **fetch + ReadableStream** (not native
   `EventSource`) so it is mockable and header-friendly. Parse `event:`/`data:` frames.
4. Handle events: `run_status`, `message_delta` (append streaming text), `message`,
   `clarifying_question` (render chips; `allow_freeform` → also accept typed answer), `plan_status`
   (status indicator; gates map editing — read-only until `ready`), `map` (rendered live on the
   **MapView**), `error`.
5. **Answer a clarifying question** = `POST /chat { in_reply_to_question_id, selected_option_ids?,
   freeform? }` (reuses the same endpoint), starting a new run.
6. **Plan view & editing:** `GET /plans/{id}` + `/map` + `/calendar` populate the **PlanView**;
   `POST /plans/{id}/accept|reject`; **edit the route** via `POST /plans/{id}/modify` (batch
   added/removed points) → `202 { run_id }`, plan flips to `building` and the agent (mock) rebuilds,
   streaming on the new run. While not `ready`, the map is read-only.

Sessions/groups/plans are loaded via their REST endpoints to populate the side panel and context.

## 8. Mock backend (MSW)

- `src/mocks/` — MSW v2 handlers implementing the `api/` endpoints (auth, chat/run + SSE, sessions,
  groups, plans). Enabled in dev and in the demo build behind a flag.
- **SSE simulation:** the stream handler returns a streamed `Response` (`text/event-stream`) that
  emits a scripted run: `run_status: started` → a few `message_delta` chunks → optionally a
  `clarifying_question` → `plan_status: building → ready` → `message` → `run_status: completed`.
- **Auth:** `register`/`login`/`refresh`/`logout`/`me` implemented against an in-memory user store;
  issues mock JWT + refresh; the login screen uses them. Ticket endpoint returns a short-lived token
  the stream handler validates.
- **Map & calendar:** `/plans/{id}/map` returns settlements with **coordinates** (a city→lat/lng
  lookup baked into the seed) + the route order; `/plans/{id}/calendar` returns RFC3339
  `CalendarEvent[]` derived from the plan's flights/hotel-nights/tours. `modify` mutates the seed plan
  and re-streams a rebuild.
- **Seed data:** sourced from `data/travelers/*` (groups, members, preferences, offer tables) and
  `data/reference/*` (plan rationale) so the UI shows realistic content. A small adapter maps CSV
  columns → API schemas (money integer `*_rub`, `0/1`→boolean, etc.).

## 9. State, API client, tech

- **API client:** `src/api/` — types generated from `api/openapi.yaml` via `openapi-typescript`
  (`pnpm gen:api`), a thin `fetch` wrapper (bearer token, error-envelope handling, pagination), and
  `sse.ts` (fetch-based event-stream reader).
- **Stores (Pinia, added):** `auth`, `sessions`, `groups`, `plans` (incl. map + calendar + edit
  buffer), `chat` (active run + messages + clarifying questions + plan status). Composition API +
  `<script setup>` + TS throughout.
- **Map:** **MapLibre GL JS** with a free, no-API-key dark vector style (matches the dark glass
  aesthetic); glass markers + popups, an animated route line. **Calendar:** a custom glass
  **itinerary/timeline** view grouped by day (no heavy calendar lib).
- **Routing:** **Vue Router** — `/login`, `/` (chat, optional `/c/:sessionId` deep-link),
  `/plans/:planId` (PlanView). An auth guard redirects to `/login` when the mock has no session. The
  background, menu, and side panel persist across routes (app-shell layout); only the main pane swaps.
- **Dependencies:** add `pinia`, `vue-router`, `maplibre-gl`, `msw` (dev), `openapi-typescript` (dev).
  Already added: `@napi-rs/canvas` (dev, prerender). Existing: `@vueuse/core`, Tailwind v4.

## 10. Component & file structure

```
frontend/src/
  App.vue                         shell: <DitheredBackground/> + <MenuButton/> + <SidePanel/> + <ChatView/>
  styles/glass.css                glass tokens + shared surface class
  components/
    background/DitheredBackground.vue, useCursorLens.ts
    layout/MenuButton.vue, SidePanel.vue, SessionList.vue, GroupList.vue, PlanList.vue
    auth/AuthView.vue                      login / register (glass)
    chat/ChatView.vue, ChatComposer.vue, MessageList.vue, MessageBubble.vue,
         ClarifyingQuestion.vue, PlanStatus.vue
    plan/PlanView.vue, MapView.vue (MapLibre), ItineraryView.vue, PlanEditBar.vue,
         OfferCard.vue
  stores/auth.ts, sessions.ts, groups.ts, plans.ts, chat.ts
  api/ (generated types, client.ts, sse.ts)
  mocks/ (browser.ts, handlers.ts, seed.ts, geo.ts, sse-script.ts)
scripts/prerender-backgrounds.mjs   (built)
public/backgrounds/<scene>-{mono,color}.webp  (generated)
```

- **ChatComposer** evolves the existing `AgentChatInput.vue` (its custom caret + typewriter
  placeholder are reused).

## 11. Removals (replace old background system)

Delete the "torn magazine scrapbook" implementation and its assets; update App.vue accordingly:
- `src/components/PageBackground/**` (all scene components, `CutoutLayer`, parallax/wiggle composables,
  css).
- `src/assets/images/**`, `src/assets/images_backup/**`, `src/assets/hero.png`.
- Replace `src/SPEC.md` (scrapbook) with the new module `SPECIFICATION.md`.

## 12. Accessibility & performance

- 60fps confirmed: backgrounds are static images; only the mask position moves.
- `prefers-reduced-motion`: disable composer/hero transitions and panel slide; keep the static scene
  (lens optional). Keyboard: focusable composer, Enter to send / Shift+Enter newline, focusable chips,
  Esc closes panel. Hero/background marked `aria-hidden`.

## 13. Testing

- **Vitest + Vue Test Utils** for components (composer state transition, clarifying-question handling,
  SSE event reducer) and stores. MSW reused in tests. Playwright E2E deferred.

## 14. SPECIFICATION.md updates (per AGENTS.md)

- New `frontend/SPECIFICATION.md` describing this module's current state (background system, glass
  design system, chat flow, mock backend); remove obsolete `src/SPEC.md`.
- Update root `SPECIFICATION.md` §2.3 (Frontend) + module table to reflect "implemented: chat UI,
  dithered backgrounds, mock backend; defers auth/map/calendar".

## 15. Implementation approach & UX bar

- **Subagent-driven development:** the implementation plan (writing-plans) is decomposed into
  independent, well-bounded tasks executed by subagents — e.g. design tokens/glass, background
  component, API client + types, mock backend, each Pinia store, each feature view (chat, side panel,
  plan/map, calendar, auth). Shared contracts (types, glass tokens, store interfaces) are defined first
  so feature tasks can proceed in parallel without shared-state conflicts.
- **Modern UI / strong UX (acceptance bar):** responsive (mobile → wide), full keyboard support and
  visible focus states, **loading skeletons**, **empty states**, and **error toasts** (from the error
  envelope), optimistic chat send, smooth 60fps motion that respects `prefers-reduced-motion`, WCAG-AA
  contrast on glass, and consistent use of the single glass token + accent.

## 16. Open items / deferred

- Replacing the mock with the real backend once it exists (client is already contract-typed).

## Appendix — Locked parameters

| Area | Value |
|---|---|
| Background master | 3840×2161 WebP, q80, ~2.7 MB/layer |
| Dot density | 600 columns (`REF_WIDTH 1800`, `DOT 3`) |
| Prerender accent / saturation | 0.85 / 1.75 |
| Cursor leak radius | 80px, soft smoothstep tail |
| Glass | white 30% · blur 7px · saturate 100% · no border |
| Composer radius | 90px / 18px (elliptical) |
| Accent / base | `#d97757` / `#0c0a08` |
| Scene selection | random on load (no swap/wind) |
