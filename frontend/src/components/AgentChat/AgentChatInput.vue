<script setup lang="ts">
import { computed, nextTick, onMounted, useTemplateRef, watch } from "vue";
import { useTextareaCaret } from "./useTextareaCaret";
import { useTypewriterPlaceholder } from "./useTypewriterPlaceholder";

const MAX_LINES = 5;
const TEXTAREA_ARIA_LABEL = "Travel question";

const model = defineModel<string>({ default: "" });

const emit = defineEmits<{
  submit: [message: string];
}>();

const placeholders = [
  "Куда бы мне поехать дальше?",
  "Расскажи про неочевидные места в Тоскане…",
  "Спланируй мне путешествие по пустыне",
  "Найди домик под северным сиянием",
  "Посоветуй, куда сбежать на остров",
] as const;

const hasInput = computed(() => model.value.length > 0);

const { text: placeholderText } = useTypewriterPlaceholder(placeholders, {
  paused: hasInput,
});

const textareaRef = useTemplateRef<HTMLTextAreaElement>("textarea");

const {
  focused: fieldFocused,
  x: caretX,
  y: caretY,
} = useTextareaCaret(textareaRef);

const caretStyle = computed(() => ({
  transform: `translate(${caretX.value}px, ${caretY.value}px)`,
}));

// Recreating the element on each move restarts the blink animation,
// so the caret stays solid while the user is typing or navigating.
const caretBlinkKey = computed(
  () => `${caretX.value}:${caretY.value}:${model.value.length}`,
);

function syncTextareaHeight() {
  const textarea = textareaRef.value;
  if (!textarea) return;

  textarea.style.height = "0px";
  const styles = getComputedStyle(textarea);
  const lineHeight = Number.parseFloat(styles.lineHeight);
  const paddingY =
    Number.parseFloat(styles.paddingTop) +
    Number.parseFloat(styles.paddingBottom);
  const maxHeight = lineHeight * MAX_LINES + paddingY;
  const nextHeight = Math.min(textarea.scrollHeight, maxHeight);

  textarea.style.height = `${nextHeight}px`;
  textarea.style.overflowY =
    textarea.scrollHeight > maxHeight ? "auto" : "hidden";
}

watch(model, async () => {
  await nextTick();
  syncTextareaHeight();
});

onMounted(() => {
  syncTextareaHeight();
});

function onKeydown(event: KeyboardEvent) {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    const trimmed = model.value.trim();
    if (trimmed) emit("submit", trimmed);
  }
}
</script>

<template>
  <div class="agent-chat-input">
    <div class="agent-chat-input__stamp">
      <div class="agent-chat-input__frame">
        <textarea
          ref="textarea"
          v-model="model"
          class="agent-chat-input__field"
          rows="1"
          autocomplete="off"
          autocorrect="off"
          autocapitalize="off"
          spellcheck="false"
          :aria-label="TEXTAREA_ARIA_LABEL"
          @keydown="onKeydown"
        />

        <span
          v-if="fieldFocused"
          :key="caretBlinkKey"
          class="agent-chat-input__field-caret"
          :style="caretStyle"
          aria-hidden="true"
        />

        <span
          v-if="!hasInput"
          class="agent-chat-input__placeholder"
          aria-hidden="true"
        >
          <span class="agent-chat-input__placeholder-text">{{
            placeholderText
          }}</span>
          <!-- Hidden (not removed) on focus: the caret takes part in the
               row's baseline alignment, so removing it would shift the
               placeholder text vertically. -->
          <span
            class="agent-chat-input__caret"
            :class="{ 'agent-chat-input__caret--hidden': fieldFocused }"
          />
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.agent-chat-input {
  width: 100%;
  max-width: 38rem;
  filter: drop-shadow(0 14px 30px rgba(8, 6, 13, 0.16))
    drop-shadow(0 3px 8px rgba(8, 6, 13, 0.08));
  transition: filter 0.3s ease;
}

.agent-chat-input:focus-within {
  filter: drop-shadow(0 18px 38px rgba(8, 6, 13, 0.2))
    drop-shadow(0 0 16px var(--scene-glow, rgba(170, 59, 255, 0.22)));
}

.agent-chat-input__stamp {
  --stamp-paper: #fff;
  --placeholder-color: #a39bb0;

  position: relative;
  border-radius: 18px;
  background: var(--stamp-paper);
  overflow: hidden;
}

.agent-chat-input__frame {
  position: relative;
}

.agent-chat-input__field {
  display: block;
  width: 100%;
  padding: 1.15rem 1.4rem;
  border: none;
  background: transparent;
  color: #000;
  font: inherit;
  font-size: 1.05rem;
  line-height: 1.5;
  letter-spacing: 0.1px;
  /* The native caret can't be sized, so it's hidden and replaced by
     .agent-chat-input__field-caret, drawn at the measured position. */
  caret-color: transparent;
  resize: none;
  overflow-y: hidden;
  outline: none;
  box-sizing: border-box;
}

.agent-chat-input__placeholder {
  position: absolute;
  inset: 1.15rem 1.4rem;
  display: flex;
  align-items: baseline;
  font-size: 1.05rem;
  line-height: 1.5;
  color: var(--placeholder-color);
  pointer-events: none;
  text-align: left;
  white-space: nowrap;
  overflow: hidden;
}

.agent-chat-input__placeholder-text {
  overflow: hidden;
  text-overflow: clip;
}

.agent-chat-input__caret,
.agent-chat-input__field-caret {
  width: 2px;
  height: 1.2em;
  font-size: 1.05rem;
  border-radius: 1px;
  background: var(--scene-accent, var(--accent, #aa3bff));
  animation: agent-chat-input-caret-blink 1.1s steps(2, jump-none) infinite;
}

.agent-chat-input__caret {
  flex: none;
  margin-left: 2px;
  transform: translateY(0.2em);
}

.agent-chat-input__caret--hidden {
  visibility: hidden;
  animation: none;
}

.agent-chat-input__field-caret {
  position: absolute;
  top: 0;
  left: 0;
  pointer-events: none;
}

@keyframes agent-chat-input-caret-blink {
  from {
    opacity: 1;
  }

  to {
    opacity: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .agent-chat-input {
    transition: none;
  }

  .agent-chat-input__caret,
  .agent-chat-input__field-caret {
    animation: none;
  }
}
</style>
