<script setup lang="ts">
import { ref, useTemplateRef } from 'vue'
import { useCursorLens, LENS_GRADIENT } from '../../composables/useCursorLens'

const SCENES = ['france', 'greece', 'italy', 'japan', 'china', 'india', 'russia', 'usa'] as const
const scene = SCENES[Math.floor(Math.random() * SCENES.length)]
const base = `/backgrounds/${scene}-mono.webp`
const color = `/backgrounds/${scene}-color.webp`

const colorEl = useTemplateRef<HTMLImageElement>('colorEl')
useCursorLens(() => colorEl.value)
const loaded = ref(false)
</script>

<template>
  <div class="bg" aria-hidden="true">
    <img class="layer" :src="base" alt="" @load="loaded = true" />
    <img ref="colorEl" class="layer color" :src="color" alt="" :style="{ '--lens': LENS_GRADIENT }" />
  </div>
</template>

<style scoped>
.bg { position: fixed; inset: 0; z-index: 0; background: var(--bg-base); }
.layer { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
.color {
  -webkit-mask-image: var(--lens); mask-image: var(--lens);
  -webkit-mask-repeat: no-repeat; mask-repeat: no-repeat;
  -webkit-mask-size: var(--d, 0) var(--d, 0); mask-size: var(--d, 0) var(--d, 0);
  -webkit-mask-position: var(--mpx, -9999px) var(--mpy, -9999px); mask-position: var(--mpx, -9999px) var(--mpy, -9999px);
}
</style>
