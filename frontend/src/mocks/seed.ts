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
