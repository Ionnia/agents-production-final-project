<script setup lang="ts">
import { computed, watch } from 'vue'
import MarkdownText from './MarkdownText.vue'
import { useTypewriter } from './useTypewriter'
const props = defineProps<{ role: 'user' | 'assistant'; content: string; streaming?: boolean; createdAt?: string; animate?: boolean }>()
const emit = defineEmits<{ grow: [] }>()
// Live assistant replies type out chunk by chunk; user messages and hydrated
// history (`animate` falsy) render their text verbatim.
const { displayed, typing } = useTypewriter(() => props.content, { instant: !props.animate })
const text = computed(() => (props.animate ? displayed.value : props.content))
// Blinking caret while the reply is still typing out (live) or streaming in.
const showCaret = computed(() => (props.animate ? typing.value : props.streaming))
// Keep the scroller pinned to the freshly revealed text as the bubble grows.
watch(displayed, () => emit('grow'))
const timeFmt = new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' })
const time = computed(() => {
  if (!props.createdAt) return ''
  const d = new Date(props.createdAt)
  return Number.isNaN(d.getTime()) ? '' : timeFmt.format(d)
})
</script>
<template>
  <div class="msg" :class="role === 'user' ? 'user' : 'bot glass'">
    <MarkdownText :text="text" :class="{ streaming: showCaret }" />
    <time v-if="time && !showCaret" class="time" :datetime="createdAt">{{ time }}</time>
  </div>
</template>
<style scoped>
.msg { max-width: 80%; padding: 12px 15px; font-size: 14.5px; line-height: 1.5; }
.user { align-self: flex-end; background: var(--accent); color: #fff; border-radius: 18px 18px 6px 18px; box-shadow: var(--bubble-shadow); }
.bot { align-self: flex-start; border-radius: 18px 18px 18px 6px; box-shadow: var(--bubble-shadow); }
.time { display: block; margin-top: 4px; font-size: 10.5px; line-height: 1; }
.user .time { text-align: right; color: rgba(255,255,255,.8); }
.bot .time { text-align: left; color: var(--ink-soft); }
</style>
