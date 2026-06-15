<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { RouterLink } from 'vue-router'
import { api } from '../../api/endpoints'
import { useToasts } from '../../composables/useToasts'
import { ApiClientError } from '../../api/client'
import type { Plan } from '../../api/types'

// Inline, in-thread plan card: when the agent's plan is ready it is presented here for
// approval (map link, flight/hotel/tour, total) so the user can accept/reject without
// leaving the conversation. Accepting persists the plan (status → accepted).
const props = defineProps<{ planId: string }>()
const { push } = useToasts()
const plan = ref<Plan | null>(null)
const busy = ref(false)
// Guards against out-of-order responses: every load/accept/reject takes a token and only
// commits if it is still the latest in-flight request (planId can change mid-fetch as the
// user keeps chatting). Stale responses are discarded instead of clobbering the current plan.
let token = 0

async function load(id: string) {
  const t = ++token
  try { const data = await api.plan(id); if (t === token) plan.value = data }
  catch { if (t === token) plan.value = null }
}
watch(() => props.planId, (id) => { plan.value = null; if (id) load(id) }, { immediate: true })

const rub = (n?: number) => (n == null ? '' : n.toLocaleString('ru-RU') + ' ₽')
const fmt = (d?: string) => {
  if (!d) return ''
  const date = new Date(d)
  return isNaN(date.getTime()) ? d : date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}
const dates = computed(() => {
  const p = plan.value
  if (!p?.start_date && !p?.end_date) return ''
  return [fmt(p?.start_date), fmt(p?.end_date)].filter(Boolean).join(' – ')
})

async function accept() {
  if (busy.value || !plan.value) return
  busy.value = true
  const t = ++token  // invalidate any in-flight load so it can't overwrite the accepted state
  try { const data = await api.acceptPlan(props.planId); if (t === token) plan.value = data; push({ kind: 'success', text: 'План принят' }) }
  catch (e) { push({ kind: 'error', text: e instanceof ApiClientError ? e.message : 'Не удалось принять план' }) }
  finally { busy.value = false }
}
async function reject() {
  if (busy.value || !plan.value) return
  busy.value = true
  const t = ++token
  try { const data = await api.rejectPlan(props.planId); if (t === token) plan.value = data; push({ kind: 'info', text: 'План отклонён' }) }
  catch (e) { push({ kind: 'error', text: e instanceof ApiClientError ? e.message : 'Не удалось отклонить план' }) }
  finally { busy.value = false }
}
</script>

<template>
  <div v-if="plan" class="pc glass" :data-status="plan.status">
    <div class="head">
      <span class="title">{{ plan.status === 'accepted' ? '✓ План принят' : plan.status === 'rejected' ? 'План отклонён' : 'План готов' }}</span>
      <span class="meta">{{ [plan.destination, dates].filter(Boolean).join(' · ') }}</span>
    </div>
    <p v-if="plan.decision_rationale" class="rat">{{ plan.decision_rationale }}</p>
    <ul class="items">
      <li v-if="plan.items.flight">✈ {{ plan.items.flight.origin_city }} → {{ plan.items.flight.destination }} · {{ rub(plan.items.flight.price_rub) }}</li>
      <li v-if="plan.items.hotel">🏨 {{ plan.items.hotel.stars }}★ · {{ plan.items.hotel.nights }} ноч. · {{ rub(plan.items.hotel.price_per_night_rub) }}/ночь</li>
      <li v-if="plan.items.tour">🎟 Тур{{ plan.items.tour.includes_flight ? ' (перелёт включён)' : '' }} · {{ rub(plan.items.tour.total_price_rub) }}</li>
    </ul>
    <div v-if="plan.estimated_total_rub != null" class="total">Итого ≈ <b>{{ rub(plan.estimated_total_rub) }}</b></div>
    <div class="actions">
      <RouterLink class="map" :to="`/plans/${planId}`">Карта →</RouterLink>
      <template v-if="plan.status === 'ready'">
        <button class="accept" :disabled="busy" @click="accept">Принять</button>
        <button class="reject" :disabled="busy" @click="reject">Отклонить</button>
      </template>
    </div>
  </div>
</template>

<style scoped>
.pc { align-self: flex-start; max-width: 90%; display: flex; flex-direction: column; gap: 8px; padding: 14px 16px; border-radius: 18px 18px 18px 6px; box-shadow: var(--bubble-shadow); }
.head { display: flex; flex-direction: column; gap: 2px; }
.title { font-weight: 700; color: var(--ink); }
.meta { font-size: 13px; color: var(--ink-soft); }
.rat { margin: 0; font-size: 13.5px; color: var(--ink); }
.items { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; font-size: 13.5px; color: var(--ink); }
.total { color: var(--ink); font-size: 14px; } .total b { color: var(--accent-press); }
.actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 2px; }
.map { color: var(--accent-press); font-weight: 600; font-size: 13.5px; align-self: center; }
.accept { padding: 8px 16px; border: none; border-radius: 999px; background: var(--accent); color: #fff; font: inherit; font-weight: 600; cursor: pointer; transition: var(--tap); }
@media (hover: hover) { .accept:not(:disabled):hover { filter: brightness(1.06); transform: translateY(-1px); box-shadow: var(--accent-glow); } }
.accept:not(:disabled):active { transform: translateY(0) scale(.97); }
.accept:disabled { opacity: .5; cursor: default; }
.reject { padding: 8px 14px; border: none; border-radius: 999px; background: rgba(0,0,0,.12); color: var(--ink); font: inherit; cursor: pointer; transition: var(--tap); }
@media (hover: hover) { .reject:not(:disabled):hover { background: rgba(0,0,0,.18); transform: translateY(-1px); } }
.reject:not(:disabled):active { transform: translateY(0) scale(.97); }
.reject:disabled { opacity: .5; cursor: default; }
</style>
