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
