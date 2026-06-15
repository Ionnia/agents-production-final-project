<script setup lang="ts">
import { ref } from 'vue'
defineProps<{ title: string }>()
// Accordion: header toggles the body. The body caps at ~3 rows and scrolls for the rest.
const open = ref(true)
</script>
<template>
  <div class="sect">
    <button class="head" type="button" :aria-expanded="open" @click="open = !open">
      <svg class="chev" :class="{ closed: !open }" viewBox="0 0 24 24" width="12" height="12" fill="none"
        stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6" /></svg>
      <h4>{{ title }}</h4>
    </button>
    <div class="wrap" :class="{ open }">
      <div class="clip">
        <div class="body">
          <slot />
        </div>
      </div>
    </div>
  </div>
</template>
<style scoped>
.sect { display: flex; flex-direction: column; }
.head { display: flex; align-items: center; gap: 6px; width: 100%; padding: 8px 4px 4px; background: none; border: none; cursor: pointer; text-align: left; border-radius: 7px; transition: var(--tap); }
@media (hover: hover) { .head:hover { background: rgba(255,255,255,.28); } }
.head:active { transform: scale(.99); }
.chev { flex: none; color: #2a2018; transition: transform .2s var(--ease); }
.chev.closed { transform: rotate(-90deg); }
h4 { margin: 0; font-size: 11px; text-transform: uppercase; letter-spacing: .1em; color: #2a2018; font-weight: 700; }
/* Animate height by transitioning the grid row from 0fr → 1fr (no JS, no fixed height). */
.wrap { display: grid; grid-template-rows: 0fr; transition: grid-template-rows .28s var(--ease); }
.wrap.open { grid-template-rows: 1fr; }
.clip { min-height: 0; overflow: hidden; }
/* ~3 items tall; the rest is reachable by scrolling within the section. */
.body { display: flex; flex-direction: column; gap: 2px; max-height: 120px; overflow-y: auto; padding: 2px; }
</style>
