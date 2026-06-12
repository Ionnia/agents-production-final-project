<script setup lang="ts">
import { computed } from 'vue'
import { createWiggleConfig, wiggleStyle } from './useWiggle'

const props = defineProps<{
  src: string
  alt: string
  x: number
  y: number
  width: string
  wiggleOrigin?: string
}>()

const wiggle = createWiggleConfig()

const positionStyle = computed(() => ({
  left: `${props.x}%`,
  top: `${props.y}%`,
  width: props.width,
}))

const cutoutWiggleStyle = computed(() =>
  wiggleStyle({
    ...wiggle,
    ...(props.wiggleOrigin ? { origin: props.wiggleOrigin } : {}),
  }),
)
</script>

<template>
  <div
    class="absolute -translate-x-1/2 -translate-y-full pointer-events-none"
    :style="positionStyle"
  >
    <img
      class="block h-auto w-full origin-[var(--wiggle-origin,20%_10%)] drop-shadow-[2px_3px_2px_rgba(0,0,0,0.25)] will-change-transform motion-reduce:animate-none motion-reduce:will-change-auto"
      :src="src"
      :alt="alt"
      :style="cutoutWiggleStyle"
      draggable="false"
      decoding="async"
    />
  </div>
</template>
