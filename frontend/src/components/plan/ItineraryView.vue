<script setup lang="ts">
import { computed } from 'vue'
import type { CalendarEvent } from '../../api/types'
const props = defineProps<{ events: CalendarEvent[]; timezone?: string }>()
const ICON: Record<string, string> = { flight: '✈️', hotel: '🏨', tour: '🗺', activity: '📍' }

const days = computed(() => {
  const map = new Map<string, CalendarEvent[]>()
  for (const e of [...props.events].sort((a, b) => a.start.localeCompare(b.start))) {
    const day = e.start.slice(0, 10); if (!map.has(day)) map.set(day, []); map.get(day)!.push(e)
  }
  return [...map.entries()]
})
const fmtDay = (d: string) => new Date(d).toLocaleDateString('ru-RU', { weekday: 'short', day: 'numeric', month: 'long' })
const fmtTime = (s?: string) => (s ? new Date(s).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }) : '')
</script>

<template>
  <div class="cal">
    <div v-for="[day, evs] in days" :key="day" class="day">
      <div class="dh">{{ fmtDay(day) }}</div>
      <div v-for="e in evs" :key="e.id" class="ev glass">
        <span class="ic">{{ ICON[e.type] }}</span>
        <div class="body"><div class="ti">{{ e.title }}</div><div class="meta">{{ fmtTime(e.start) }}<template v-if="e.end"> – {{ fmtTime(e.end) }}</template><template v-if="e.location"> · {{ e.location }}</template></div></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cal { display: flex; flex-direction: column; gap: 16px; }
.dh { font-size: 12px; text-transform: uppercase; letter-spacing: .08em; color: #cabfb0; margin: 0 0 6px; }
.ev { display: flex; gap: 12px; padding: 12px 14px; border-radius: 14px; margin-bottom: 8px; }
.ic { font-size: 18px; }
.ti { font-weight: 600; color: var(--ink); }
.meta { font-size: 12.5px; color: var(--ink-soft); }
</style>
