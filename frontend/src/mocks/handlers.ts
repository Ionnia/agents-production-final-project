import { http, HttpResponse } from 'msw'
import type { ChatRequest, ModifyRequest, CalendarEvent } from '../api/types'
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
