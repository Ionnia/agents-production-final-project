<script setup lang="ts">
import { computed, ref } from 'vue'
import { usePlansStore } from '../../stores/plans'
const props = defineProps<{ planId: string }>()
const emit = defineEmits<{ rebuild: [runId: string] }>()
const plans = usePlansStore()
const editable = computed(() => plans.map?.editable ?? false)
const newPoint = ref('')
function add() { if (newPoint.value.trim()) { plans.stageAdd(newPoint.value.trim()); newPoint.value = '' } }
async function submit() { const runId = await plans.modify(props.planId); emit('rebuild', runId) }
</script>
<template>
  <div class="bar glass" :class="{ disabled: !editable }">
    <div class="row">
      <input v-model="newPoint" class="in" :disabled="!editable" placeholder="Добавить точку (город)…" @keydown.enter="add" />
      <button class="add" :disabled="!editable" @click="add">＋</button>
    </div>
    <div v-if="plans.pendingAdd.length" class="staged">
      <span v-for="p in plans.pendingAdd" :key="p.id" class="tag">＋ {{ p.name }}</span>
    </div>
    <p v-if="!editable" class="note">Изменять можно только готовый план.</p>
    <button class="rebuild" :disabled="!editable || !plans.hasEdits()" @click="submit">Перестроить маршрут</button>
  </div>
</template>
<style scoped>
.bar { padding: 14px; border-radius: 14px; display: flex; flex-direction: column; gap: 8px; }
.row { display: flex; gap: 8px; }
.in { flex: 1; padding: 9px 12px; border: none; border-radius: 10px; background: rgba(255,255,255,.4); color: var(--ink); }
.add { width: 38px; border: none; border-radius: 10px; background: var(--accent); color: #fff; cursor: pointer; }
.staged { display: flex; flex-wrap: wrap; gap: 6px; }
.tag { font-size: 12px; padding: 4px 9px; border-radius: 999px; background: rgba(217,119,87,.18); color: var(--accent-press); }
.note { margin: 0; font-size: 12px; color: var(--ink-soft); }
.rebuild { padding: 10px; border: none; border-radius: 10px; background: var(--accent); color: #fff; font-weight: 600; cursor: pointer; }
.rebuild:disabled { opacity: .5; cursor: default; }
</style>
