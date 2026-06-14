<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import MapView from './MapView.vue'
import ItineraryView from './ItineraryView.vue'
import OfferCard from './OfferCard.vue'
import PlanEditBar from './PlanEditBar.vue'
import Skeleton from '../ui/Skeleton.vue'
import { usePlansStore } from '../../stores/plans'
import { useToasts } from '../../composables/useToasts'
import { ApiClientError } from '../../api/client'

const props = defineProps<{ planId: string }>()
const plans = usePlansStore(); const router = useRouter(); const { push } = useToasts()
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
