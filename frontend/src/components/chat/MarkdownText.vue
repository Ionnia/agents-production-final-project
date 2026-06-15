<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

// Single source of markdown rendering for assistant/question text. This is the
// ONE place that uses v-html, so sanitization lives here and nowhere else.
// `breaks: true` keeps the old white-space:pre-wrap feel — a single \n becomes
// a <br>, while \n\n starts a new paragraph and `1.`/`-` lists render properly.
const props = defineProps<{ text: string }>()

const html = computed(() => {
  const raw = marked.parse(props.text ?? '', { gfm: true, breaks: true }) as string
  return DOMPurify.sanitize(raw)
})
</script>

<template>
  <div class="md" v-html="html" />
</template>

<style scoped>
/* Tight, bubble-friendly rhythm — paragraphs/lists shouldn't add outer margin. */
.md :deep(> :first-child) { margin-top: 0; }
.md :deep(> :last-child) { margin-bottom: 0; }
.md :deep(p) { margin: 0; }
.md :deep(p + p),
.md :deep(p + ul), .md :deep(p + ol),
.md :deep(ul + p), .md :deep(ol + p) { margin-top: .5em; }
.md :deep(ul), .md :deep(ol) { margin: .35em 0; padding-left: 1.35em; }
.md :deep(li) { margin: .12em 0; }
.md :deep(li > p) { margin: 0; }
.md :deep(h1), .md :deep(h2), .md :deep(h3),
.md :deep(h4), .md :deep(h5), .md :deep(h6) { margin: .4em 0 .25em; font-size: 1em; font-weight: 700; }
.md :deep(a) { color: inherit; text-decoration: underline; }
.md :deep(strong) { font-weight: 700; }
.md :deep(code) { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .92em;
  background: rgba(0,0,0,.07); padding: .08em .35em; border-radius: 5px; }
.md :deep(pre) { margin: .4em 0; padding: 10px 12px; border-radius: 10px;
  background: rgba(0,0,0,.07); overflow-x: auto; }
.md :deep(pre code) { background: none; padding: 0; }
.md :deep(blockquote) { margin: .4em 0; padding-left: .8em; border-left: 3px solid currentColor; opacity: .85; }
/* While streaming, keep the last block inline and append the blinking typing
   caret right after the text, so it tracks the end of the streamed content. */
.md.streaming :deep(> :last-child) { display: inline; }
.md.streaming :deep(> :last-child)::after {
  content: ''; display: inline-block; width: 7px; height: 1.05em; margin-left: 2px;
  vertical-align: -2px; background: currentColor; animation: md-caret-blink 1s steps(2) infinite;
}
@keyframes md-caret-blink { 50% { opacity: 0; } }
</style>
