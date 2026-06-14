<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useGroupsStore } from '../../stores/groups'
import EmptyState from '../ui/EmptyState.vue'
const groups = useGroupsStore()
const props = defineProps<{ filter: string }>()
const filtered = computed(() => groups.list.filter(g => g.name.toLowerCase().includes(props.filter.toLowerCase())))
onMounted(() => { if (!groups.list.length) groups.loadList() })
</script>
<template>
  <div class="sect">
    <h4>Группы</h4>
    <EmptyState v-if="!groups.list.length" title="Нет групп" hint="Создайте группу путешественников" />
    <div v-for="g in filtered" :key="g.id" class="item">
      <span class="lbl">{{ g.name }}</span> <small>{{ g.member_count }}</small>
    </div>
  </div>
</template>
<style scoped>
.sect { display: flex; flex-direction: column; gap: 2px; }
h4 { margin: 10px 4px 3px; font-size: 11px; text-transform: uppercase; letter-spacing: .1em; color: #7a6f62; font-weight: 700; }
.item { display: flex; gap: 9px; padding: 8px 10px; border-radius: 9px; color: #3a3024; font-size: 14px; transition: var(--tap); }
@media (hover: hover) { .item:hover { background: rgba(255,255,255,.4); } }
.item:active { background: rgba(255,255,255,.5); transform: scale(.99); }
.lbl { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
small { color: #8a7f70; }
</style>
