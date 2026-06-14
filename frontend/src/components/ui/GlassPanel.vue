<script setup lang="ts">
withDefaults(defineProps<{ radius?: string }>(), { radius: '18px' })
</script>
<template>
  <div class="glass" :style="{ borderRadius: radius }"><slot /></div>
</template>
