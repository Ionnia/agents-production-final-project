<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useSessionsStore } from '../../stores/sessions'
import Skeleton from '../ui/Skeleton.vue'
import EmptyState from '../ui/EmptyState.vue'
const sessions = useSessionsStore()
const props = defineProps<{ filter: string }>()
const emit = defineEmits<{ navigate: [] }>()
const filtered = computed(() => sessions.list.filter(s => s.summary.toLowerCase().includes(props.filter.toLowerCase())))
onMounted(() => { if (!sessions.list.length) sessions.loadList() })

const timeFmt = new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' })
const dateFmt = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short' }) // "27 янв."
// Time only when the chat was created today; otherwise prefix the short date.
function whenLabel(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const now = new Date()
  const today = d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate()
  return today ? timeFmt.format(d) : `${dateFmt.format(d)} ${timeFmt.format(d)}`
}
</script>
<template>
  <div class="sect">
    <h4>История</h4>
    <template v-if="sessions.loading && !sessions.list.length"><Skeleton v-for="i in 3" :key="i" h="32px" /></template>
    <EmptyState v-else-if="!sessions.list.length" title="Пока нет чатов" />
    <RouterLink v-for="s in filtered" :key="s.id" class="item" :to="`/c/${s.id}`" @click="emit('navigate')">
      <span class="lbl">{{ s.summary }}</span>
      <time class="when" :datetime="s.created_at">{{ whenLabel(s.created_at) }}</time>
    </RouterLink>
  </div>
</template>
<style scoped>
.sect { display: flex; flex-direction: column; gap: 2px; }
h4 { margin: 10px 4px 3px; font-size: 11px; text-transform: uppercase; letter-spacing: .1em; color: #2a2018; font-weight: 700; }
.item { display: flex; flex-direction: column; align-items: flex-start; gap: 1px; padding: 7px 10px; border-radius: 9px; color: #3a3024; font-size: 14px; text-decoration: none; transition: var(--tap); }
@media (hover: hover) { .item:hover { background: rgba(255,255,255,.4); } }
.item:active { background: rgba(255,255,255,.5); transform: scale(.99); }
.lbl { max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.when { font-size: 11px; color: #6a5f52; }
</style>
