<script setup lang="ts">
import { computed } from 'vue'
import MarkdownText from './MarkdownText.vue'
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
    <MarkdownText :text="content" :class="{ streaming }" />
    <time v-if="time && !streaming" class="time" :datetime="createdAt">{{ time }}</time>
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
