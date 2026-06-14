<script setup lang="ts">
import { useToasts } from '../../composables/useToasts'
const { toasts, remove } = useToasts()
</script>
<template>
  <div class="host">
    <div v-for="t in toasts" :key="t.id" class="toast glass-dark" :data-kind="t.kind" @click="remove(t.id)">
      {{ t.text }}
    </div>
  </div>
</template>
<style scoped>
.host { position: fixed; bottom: 18px; left: 50%; transform: translateX(-50%); z-index: 100; display: flex; flex-direction: column; gap: 8px; }
.toast { padding: 10px 16px; border-radius: 10px; font-size: 14px; cursor: pointer; max-width: 90vw; transition: var(--tap); }
@media (hover: hover) { .toast:hover { filter: brightness(1.05); } }
.toast:active { transform: scale(.98); }
.toast[data-kind='error'] { border-color: rgba(217,119,87,.6); color: #f3c0ab; }
</style>
