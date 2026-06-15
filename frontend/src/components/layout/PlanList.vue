<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { api } from '../../api/endpoints'
import type { PlanSummary } from '../../api/types'
import CollapsibleSection from './CollapsibleSection.vue'
import EmptyState from '../ui/EmptyState.vue'
import { planStatusLabel } from '../../utils/planStatus'
const plans = ref<PlanSummary[]>([])
// `open` drives a reload every time the panel is shown: the panel stays mounted
// (v-show), so without this the list would only ever reflect its first fetch and
// miss plans accepted/created since (e.g. just-accepted inline plans).
const props = defineProps<{ filter: string; open: boolean }>()
const emit = defineEmits<{ navigate: [] }>()
// Filter by destination, most recent first; the section caps the visible window to ~3 rows and scrolls.
const sorted = computed(() =>
  plans.value
    .filter(p => (p.destination ?? '').toLowerCase().includes(props.filter.toLowerCase()))
    .slice()
    .sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? '')),
)
// Lists every plan the user owns — including group-less plans from the inline-chat
// approval flow, which the per-group endpoint cannot return.
async function load() { plans.value = (await api.plans()).items }
watch(() => props.open, (open) => { if (open) load() }, { immediate: true })
</script>
<template>
  <CollapsibleSection title="Планы">
    <EmptyState v-if="!sorted.length" title="Нет планов" />
    <RouterLink v-for="p in sorted" :key="p.plan_id" class="item" :to="`/plans/${p.plan_id}`" @click="emit('navigate')">
      <span class="lbl">{{ p.destination || 'Маршрут' }}</span> <small>{{ planStatusLabel(p.status) }}</small>
    </RouterLink>
  </CollapsibleSection>
</template>
<style scoped>
.item { display: flex; gap: 9px; padding: 8px 10px; border-radius: 9px; color: #3a3024; font-size: 14px; text-decoration: none; transition: var(--tap); }
@media (hover: hover) { .item:hover { background: rgba(255,255,255,.4); } }
.item:active { background: rgba(255,255,255,.5); transform: scale(.99); }
.lbl { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
small { color: #8a7f70; }
</style>
