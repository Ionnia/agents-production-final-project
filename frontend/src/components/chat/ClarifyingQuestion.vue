<script setup lang="ts">
import { ref } from 'vue'
import type { ClarifyingQuestion } from '../../api/types'
const props = defineProps<{ question: ClarifyingQuestion }>()
const emit = defineEmits<{ answer: [optionIds: string[], freeform?: string] }>()
const freeform = ref('')
function pick(id: string) { emit('answer', [id]) }
function sendFree() { if (freeform.value.trim()) emit('answer', [], freeform.value.trim()) }
</script>
<template>
  <div class="q">
    <p class="qt glass">{{ question.text }}</p>
    <div class="chips">
      <button v-for="o in question.options" :key="o.id" class="chip glass" @click="pick(o.id)">{{ o.label }}</button>
    </div>
    <div v-if="question.allow_freeform" class="free">
      <input v-model="freeform" class="fi glass" placeholder="Свой вариант…" @keydown.enter="sendFree" />
      <button class="go" @click="sendFree">→</button>
    </div>
  </div>
</template>
<style scoped>
.q { align-self: flex-start; max-width: 90%; display: flex; flex-direction: column; gap: 8px; }
.qt { margin: 0; padding: 12px 15px; border-radius: 18px 18px 18px 6px; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { padding: 8px 14px; border: none; border-radius: 999px; cursor: pointer; color: var(--ink); font: inherit; font-size: 13.5px; }
.free { display: flex; gap: 8px; }
.fi { flex: 1; padding: 9px 13px; border: none; border-radius: 999px; color: var(--ink); font: inherit; }
.fi::placeholder { color: var(--ink-soft); }
.go { width: 38px; border: none; border-radius: 50%; background: var(--accent); color: #fff; cursor: pointer; }
</style>
