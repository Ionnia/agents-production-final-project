<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api } from '../../api/endpoints'
import type { PlanSummary } from '../../api/types'
import { useGroupsStore } from '../../stores/groups'
import EmptyState from '../ui/EmptyState.vue'
import { planStatusLabel } from '../../utils/planStatus'
const groups = useGroupsStore()
const plans = ref<PlanSummary[]>([])
const emit = defineEmits<{ navigate: [] }>()
onMounted(async () => {
  if (!groups.list.length) await groups.loadList()
  const all = await Promise.all(groups.list.map(g => api.groupPlans(g.id).then(r => r.items)))
  plans.value = all.flat()
})
</script>
<template>
  <div class="sect">
    <h4>Планы</h4>
    <EmptyState v-if="!plans.length" title="Нет планов" />
    <RouterLink v-for="p in plans" :key="p.plan_id" class="item" :to="`/plans/${p.plan_id}`" @click="emit('navigate')">
      <span class="lbl">{{ p.destination || 'Маршрут' }}</span> <small>{{ planStatusLabel(p.status) }}</small>
    </RouterLink>
  </div>
</template>
<style scoped>
.sect { display: flex; flex-direction: column; gap: 2px; }
h4 { margin: 10px 4px 3px; font-size: 11px; text-transform: uppercase; letter-spacing: .1em; color: #7a6f62; font-weight: 700; }
.item { display: flex; gap: 9px; padding: 8px 10px; border-radius: 9px; color: #3a3024; font-size: 14px; text-decoration: none; transition: var(--tap); }
@media (hover: hover) { .item:hover { background: rgba(255,255,255,.4); } }
.item:active { background: rgba(255,255,255,.5); transform: scale(.99); }
.lbl { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
small { color: #8a7f70; }
</style>
