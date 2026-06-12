<script setup lang="ts">
import { ref } from 'vue'
import AgentChatInput from './AgentChatInput.vue'

const message = ref('')

function onSubmit(value: string) {
  message.value = value
}
</script>

<template>
  <section class="agent-chat">
    <AgentChatInput
      v-model="message"
      @submit="onSubmit"
    />
  </section>
</template>

<style scoped>
.agent-chat {
  position: fixed;
  inset: 0;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
  box-sizing: border-box;
  pointer-events: none;
}

.agent-chat :deep(.agent-chat-input) {
  pointer-events: auto;
}
</style>
