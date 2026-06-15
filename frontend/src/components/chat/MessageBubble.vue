<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ role: 'user' | 'assistant'; content: string; streaming?: boolean; createdAt?: string }>()
const timeFmt = new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' })
const time = computed(() => {
  if (!props.createdAt) return ''
  const d = new Date(props.createdAt)
  return Number.isNaN(d.getTime()) ? '' : timeFmt.format(d)
})
</script>
<template>
  <div class="msg" :class="role === 'user' ? 'user' : 'bot glass'">
    <span>{{ content }}</span><span v-if="streaming" class="caret" />
    <time v-if="time && !streaming" class="time" :datetime="createdAt">{{ time }}</time>
  </div>
</template>
<style scoped>
.msg { max-width: 80%; padding: 12px 15px; font-size: 14.5px; line-height: 1.5; white-space: pre-wrap; }
.user { align-self: flex-end; background: var(--accent); color: #fff; border-radius: 18px 18px 6px 18px; box-shadow: var(--bubble-shadow); }
.bot { align-self: flex-start; border-radius: 18px 18px 18px 6px; box-shadow: var(--bubble-shadow); }
.caret { display: inline-block; width: 7px; height: 1.05em; margin-left: 2px; vertical-align: -2px; background: currentColor; animation: blink 1s steps(2) infinite; }
.time { display: block; margin-top: 4px; font-size: 10.5px; line-height: 1; }
.user .time { text-align: right; color: rgba(255,255,255,.8); }
.bot .time { text-align: left; color: var(--ink-soft); }
@keyframes blink { 50% { opacity: 0; } }
</style>
