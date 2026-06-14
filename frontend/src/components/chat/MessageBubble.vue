<script setup lang="ts">
defineProps<{ role: 'user' | 'assistant'; content: string; streaming?: boolean }>()
</script>
<template>
  <div class="msg" :class="role === 'user' ? 'user' : 'bot glass'">
    <span>{{ content }}</span><span v-if="streaming" class="caret" />
  </div>
</template>
<style scoped>
.msg { max-width: 80%; padding: 12px 15px; font-size: 14.5px; line-height: 1.5; white-space: pre-wrap; }
.user { align-self: flex-end; background: var(--accent); color: #fff; border-radius: 18px 18px 6px 18px; }
.bot { align-self: flex-start; border-radius: 18px 18px 18px 6px; }
.caret { display: inline-block; width: 7px; height: 1.05em; margin-left: 2px; vertical-align: -2px; background: currentColor; animation: blink 1s steps(2) infinite; }
@keyframes blink { 50% { opacity: 0; } }
</style>
