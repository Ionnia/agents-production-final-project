<script setup lang="ts">
import { onMounted, useTemplateRef } from 'vue'
import { useCursorLens } from '../../composables/useCursorLens'

const SCENES = ['france', 'greece', 'italy', 'japan', 'china', 'india', 'russia', 'usa'] as const
// Each scene drives the app accent so buttons, bubbles, etc. match its background.
// [--accent, --accent-press]; press is the darker shade also used as text on glass.
const ACCENTS: Record<(typeof SCENES)[number], readonly [string, string]> = {
  china: ['#1fa47a', '#15805f'],  // jade
  russia: ['#3d6fd0', '#2e57ae'], // blue
  usa: ['#2b4c8f', '#1e3a73'],    // dark blue
  india: ['#ce7396', '#b25a7e'],  // soft pink
  japan: ['#e0556e', '#c13e58'],  // reddish pink
  italy: ['#d97757', '#cf5f3f'],  // terracotta
  france: ['#e8a51c', '#bd820c'], // vibrant gold
  greece: ['#2e84c9', '#2169aa'], // Aegean blue
}
const scene = SCENES[Math.floor(Math.random() * SCENES.length)]
const base = `/backgrounds/${scene}-mono.webp`
const color = `/backgrounds/${scene}-color.webp`

onMounted(() => {
  const [accent, press] = ACCENTS[scene]
  const root = document.documentElement.style
  root.setProperty('--accent', accent)
  root.setProperty('--accent-press', press)
})

const colorEl = useTemplateRef<HTMLImageElement>('colorEl')
useCursorLens(() => colorEl.value)
</script>

<template>
  <div class="bg" aria-hidden="true">
    <img class="layer" :src="base" alt="" />
    <img ref="colorEl" class="layer color" :src="color" alt="" />
  </div>
</template>

<style scoped>
.bg { position: fixed; inset: 0; z-index: 0; background: var(--bg-base); }
.layer { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
/* useCursorLens drives the mask layers (reveal + fading trail) imperatively.
   A zero-sized mask-image must be present from load so the color layer stays
   fully hidden until the first pointer move (mask-size alone has no effect
   without a mask-image). */
.color {
  -webkit-mask-image: linear-gradient(#000, #000); mask-image: linear-gradient(#000, #000);
  -webkit-mask-repeat: no-repeat; mask-repeat: no-repeat;
  -webkit-mask-size: 0 0; mask-size: 0 0;
}
</style>
