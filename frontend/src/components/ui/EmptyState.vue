<script setup lang="ts">defineProps<{ title: string; hint?: string }>()</script>
<template>
  <div class="empty">
    <p class="t">{{ title }}</p>
    <p v-if="hint" class="h">{{ hint }}</p>
  </div>
</template>
<style scoped>
.empty { text-align: center; padding: 28px 16px; color: #cfc7ba; }
.t { font-weight: 600; color: #fff; margin: 0 0 4px; }
.h { margin: 0; font-size: 13px; opacity: .7; }
</style>
