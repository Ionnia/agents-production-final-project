<script setup lang="ts">
import { computed, watch, nextTick, useTemplateRef } from 'vue'
import MessageBubble from './MessageBubble.vue'
import ClarifyingQuestion from './ClarifyingQuestion.vue'
import PlanStatus from './PlanStatus.vue'
import PlanCard from './PlanCard.vue'
import type { ClarifyingQuestion as CQ } from '../../api/types'

const props = defineProps<{
  messages: { id: string; role: 'user' | 'assistant'; content: string; streaming?: boolean; animate?: boolean; created_at?: string }[]
  question: CQ | null
  planStatus: 'building' | 'ready' | 'error' | null
  planId: string | null
  running?: boolean
  replyStarted?: boolean
}>()
// Show the working indicator while a run is in flight and this turn's reply hasn't
// begun arriving yet (covers the live backend, which emits one final `message`
// with no `message_delta` chunks — there is no `streaming` flag to wait on).
const thinking = computed(() => props.running && !props.replyStarted)
const emit = defineEmits<{ answer: [optionIds: string[], freeform?: string] }>()
const box = useTemplateRef<HTMLElement>('box')
function scrollToBottom() { nextTick(() => { if (box.value) box.value.scrollTop = box.value.scrollHeight }) }
watch(() => [props.messages.map(m => m.content).join(''), props.question, props.planStatus, thinking.value],
  scrollToBottom)
</script>

<template>
  <div ref="box" class="list">
    <MessageBubble v-for="m in messages" :key="m.id" :role="m.role" :content="m.content" :streaming="m.streaming" :animate="m.animate" :created-at="m.created_at" @grow="scrollToBottom" />
    <div v-if="thinking" class="thinking glass" role="status" aria-label="Агент думает">
      <span class="d" /><span class="d" /><span class="d" />
    </div>
    <PlanCard v-if="planStatus === 'ready' && planId" :plan-id="planId" />
    <PlanStatus v-else-if="planStatus" :status="planStatus" :plan-id="planId" />
    <ClarifyingQuestion v-if="question" :question="question" @answer="(o, f) => emit('answer', o, f)" />
  </div>
</template>

<style scoped>
/* Full-width scroller: horizontal padding centres a 720px content column while the
   scrollbar stays at the screen edge. Note: no mask/filter here — that would make this
   a backdrop root and kill the bubbles' backdrop-filter. The composer matches this
   720px / 14px-gutter span so its edges line up with the bubbles' outer edges. */
.list { display: flex; flex-direction: column; gap: 13px; overflow: auto; height: 100%;
  padding: 6px max(14px, calc((100% - 720px) / 2)); }
.thinking { align-self: flex-start; display: flex; gap: 5px; align-items: center; padding: 12px 16px;
  border-radius: 18px 18px 18px 6px; box-shadow: var(--bubble-shadow); }
.thinking .d { width: 7px; height: 7px; border-radius: 50%; background: var(--accent); opacity: .35; animation: bob 1.2s infinite ease-in-out; }
.thinking .d:nth-child(2) { animation-delay: .2s; }
.thinking .d:nth-child(3) { animation-delay: .4s; }
@keyframes bob { 0%, 80%, 100% { opacity: .3; transform: translateY(0); } 40% { opacity: 1; transform: translateY(-4px); } }
</style>
