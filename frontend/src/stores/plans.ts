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
  // Drop the signed-in user's cached plan so the next user can't see it.
  function reset() { current.value = null; map.value = null; calendar.value = null; loading.value = false; resetEdits() }
  return { current, map, calendar, loading, pendingRemove, pendingAdd, hasEdits, load, toggleRemove, stageAdd, resetEdits, accept, reject, modify, reset }
})
