<script setup lang="ts">
import { nextTick, watch, useTemplateRef } from 'vue'
const props = defineProps<{ busy?: boolean }>()
const model = defineModel<string>({ default: '' })
const emit = defineEmits<{ submit: [text: string] }>()
const ta = useTemplateRef<HTMLTextAreaElement>('ta')
const MAX = 6

function autosize() {
  const el = ta.value; if (!el) return
  el.style.height = '0px'
  const cs = getComputedStyle(el); const line = parseFloat(cs.lineHeight); const pad = parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom)
  el.style.height = Math.min(el.scrollHeight, line * MAX + pad) + 'px'
}
watch(model, () => nextTick(autosize))
function onKey(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); fire() }
}
function fire() { if (props.busy) return; const t = model.value.trim(); if (t) { emit('submit', t); model.value = '' } }
</script>

<template>
  <div class="composer glass">
    <div class="row">
      <textarea ref="ta" v-model="model" class="field" rows="1"
        :placeholder="busy ? 'Агент отвечает…' : 'Спланируй путешествие…'" :disabled="busy"
        autocomplete="off" spellcheck="false" @keydown="onKey" />
      <button class="send" :disabled="!model.trim() || busy" aria-label="Отправить" @click="fire">↑</button>
    </div>
  </div>
</template>

<style scoped>
/* Match the message column span (720px centred, 14px gutters) so the composer's
   edges line up with the outer edges of the chat bubbles. */
.composer { width: min(720px, calc(100% - 28px)); border-radius: 90px / 18px; padding: 6px; }
.row { display: flex; align-items: flex-end; gap: 10px; padding: 9px 12px; }
.field { flex: 1; resize: none; border: none; background: transparent; color: var(--ink); font: inherit; font-size: 16px; outline: none; padding: 8px; max-height: 160px; }
.field::placeholder { color: var(--ink-soft); }
.field:disabled { opacity: .55; cursor: not-allowed; }
.send { width: 40px; height: 40px; flex: none; border-radius: 50%; border: none; cursor: pointer; color: #fff; font-size: 18px;
  background: linear-gradient(160deg, var(--accent), var(--accent-press)); transition: var(--tap); }
@media (hover: hover) { .send:not(:disabled):hover { filter: brightness(1.06); transform: translateY(-1px); box-shadow: var(--accent-glow); } }
.send:not(:disabled):active { transform: translateY(0) scale(.97); filter: brightness(.95); box-shadow: var(--accent-glow-press); }
.send:disabled { opacity: .5; cursor: default; transform: none; }
</style>
