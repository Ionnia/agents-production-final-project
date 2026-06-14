<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useSessionsStore } from '../../stores/sessions'
import Skeleton from '../ui/Skeleton.vue'
import EmptyState from '../ui/EmptyState.vue'
const sessions = useSessionsStore()
const props = defineProps<{ filter: string }>()
const emit = defineEmits<{ navigate: [] }>()
onMounted(() => { if (!sessions.list.length) sessions.loadList() })
function match(s: { summary: string }) { return s.summary.toLowerCase().includes(props.filter.toLowerCase()) }
</script>
<template>
  <div class="sect">
    <h4>История</h4>
    <template v-if="sessions.loading && !sessions.list.length"><Skeleton v-for="i in 3" :key="i" h="32px" /></template>
    <EmptyState v-else-if="!sessions.list.length" title="Пока нет чатов" />
    <RouterLink v-for="s in sessions.list.filter(match)" :key="s.id" class="item" :to="`/c/${s.id}`" @click="emit('navigate')">
      💬 <span class="lbl">{{ s.summary }}</span>
    </RouterLink>
  </div>
</template>
<style scoped>
.sect { display: flex; flex-direction: column; gap: 2px; }
h4 { margin: 10px 4px 3px; font-size: 11px; text-transform: uppercase; letter-spacing: .1em; color: #7a6f62; font-weight: 700; }
.item { display: flex; gap: 9px; padding: 8px 10px; border-radius: 9px; color: #3a3024; font-size: 14px; text-decoration: none; }
.item:hover { background: rgba(255,255,255,.4); }
.lbl { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
