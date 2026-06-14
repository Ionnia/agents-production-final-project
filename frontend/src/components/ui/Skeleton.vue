<script setup lang="ts">
withDefaults(defineProps<{ w?: string; h?: string }>(), { w: '100%', h: '14px' })
</script>
<template><div class="sk" :style="{ width: w, height: h }" /></template>
<style scoped>
.sk { border-radius: 8px; background: linear-gradient(90deg, rgba(255,255,255,.10), rgba(255,255,255,.22), rgba(255,255,255,.10)); background-size: 200% 100%; animation: sh 1.2s infinite; }
@keyframes sh { from { background-position: 200% 0 } to { background-position: -200% 0 } }
</style>
