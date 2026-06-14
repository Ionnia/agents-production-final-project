<script setup lang="ts">
import type { FlightSel, HotelSel, TourSel } from '../../api/types'
defineProps<{ flight?: FlightSel; hotel?: HotelSel; tour?: TourSel }>()
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
