<script setup lang="ts">defineEmits<{ toggle: [] }>()</script>
<template>
  <button class="menu glass" type="button" aria-label="Меню" @click="$emit('toggle')">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 6h18M3 12h18M3 18h18"/></svg>
  </button>
</template>
<style scoped>
.menu { position: fixed; top: 20px; left: 20px; z-index: 30; width: 44px; height: 44px; border-radius: 14px; display: grid; place-items: center; cursor: pointer; border: none; }
.menu svg { width: 20px; height: 20px; }
</style>
