<script setup lang="ts">
import { RouterLink } from 'vue-router'
defineProps<{ status: 'building' | 'ready' | 'error'; planId?: string | null }>()
</script>
<template>
  <div class="ps glass" :data-status="status">
    <template v-if="status === 'building'"><span class="dot" /> Собираю маршрут…</template>
    <template v-else-if="status === 'ready'">
      ✓ Маршрут готов
      <RouterLink v-if="planId" class="open" :to="`/plans/${planId}`">Открыть план →</RouterLink>
    </template>
    <template v-else>Не удалось построить план</template>
  </div>
</template>
<style scoped>
.ps { align-self: flex-start; padding: 9px 14px; border-radius: 12px; font-size: 13.5px; display: flex; gap: 8px; align-items: center; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); animation: pulse 1s infinite; }
@keyframes pulse { 50% { opacity: .3; } }
.open { color: var(--accent-press); font-weight: 600; }
</style>
