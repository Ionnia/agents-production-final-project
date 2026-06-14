<script setup lang="ts">
import { watch, nextTick, useTemplateRef } from 'vue'
import MessageBubble from './MessageBubble.vue'
import ClarifyingQuestion from './ClarifyingQuestion.vue'
import PlanStatus from './PlanStatus.vue'
import type { ClarifyingQuestion as CQ } from '../../api/types'

const props = defineProps<{
  messages: { id: string; role: 'user' | 'assistant'; content: string; streaming?: boolean }[]
  question: CQ | null
  planStatus: 'building' | 'ready' | 'error' | null
  planId: string | null
}>()
const emit = defineEmits<{ answer: [optionIds: string[], freeform?: string] }>()
const box = useTemplateRef<HTMLElement>('box')
watch(() => [props.messages.map(m => m.content).join(''), props.question, props.planStatus],
  () => nextTick(() => { if (box.value) box.value.scrollTop = box.value.scrollHeight }))
</script>

<template>
  <div ref="box" class="list">
    <MessageBubble v-for="m in messages" :key="m.id" :role="m.role" :content="m.content" :streaming="m.streaming" />
    <PlanStatus v-if="planStatus" :status="planStatus" :plan-id="planId" />
    <ClarifyingQuestion v-if="question" :question="question" @answer="(o, f) => emit('answer', o, f)" />
  </div>
</template>

<style scoped>
.list { display: flex; flex-direction: column; gap: 13px; overflow: auto; height: 100%; padding: 4px 2px; }
</style>
