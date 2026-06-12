<script setup lang="ts">
import { useIntervalFn } from "@vueuse/core";
import { computed, nextTick, onMounted, ref, useTemplateRef, watch } from "vue";

const MAX_LINES = 5;
const TEXTAREA_ARIA_LABEL = "Travel question";

const model = defineModel<string>({ default: "" });

const emit = defineEmits<{
  submit: [message: string];
}>();

const placeholders = [
  "Where would you like to wander next?",
  "Ask about hidden gems in Tuscany…",
  "Plan a desert road trip for me",
  "Find a cabin under the northern lights",
  "Suggest an island escape",
] as const;

const placeholderIndex = ref(0);

const currentPlaceholder = computed(
  () => placeholders[placeholderIndex.value],
);

const { pause: pausePlaceholderRotation, resume: resumePlaceholderRotation } =
  useIntervalFn(() => {
    placeholderIndex.value =
      (placeholderIndex.value + 1) % placeholders.length;
  }, 3000);

const textareaRef = useTemplateRef<HTMLTextAreaElement>("textarea");

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

watch(model, async (value) => {
  if (value) {
    pausePlaceholderRotation();
  } else {
    resumePlaceholderRotation();
  }

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
      <div class="agent-chat-input__field-wrap">
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

        <Transition name="agent-chat-input-placeholder" mode="out-in">
          <span
            v-if="!model"
            :key="placeholderIndex"
            class="agent-chat-input__placeholder"
            aria-hidden="true"
          >
            {{ currentPlaceholder }}
          </span>
        </Transition>
      </div>
    </div>
  </div>
</template>

<style scoped>
.agent-chat-input {
  width: 100%;
  max-width: 36rem;
}

.agent-chat-input__stamp {
  --notch-size: 6px;
  --notch-step: 15px;
  --stamp-radius: 24px;
  --stamp-border: #b8b2c2;
  --stamp-surface: #fff;
  --placeholder-color: #9ca3af;

  position: relative;
  padding: 3px;
  border-radius: var(--stamp-radius);
  filter: drop-shadow(0 10px 28px rgba(8, 6, 13, 0.12))
    drop-shadow(0 2px 8px rgba(8, 6, 13, 0.06));
}

.agent-chat-input__stamp::before {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: var(--stamp-radius);
  background: var(--stamp-border);
  pointer-events: none;
  -webkit-mask:
    radial-gradient(
        circle at 50% calc(100% + var(--notch-size)),
        transparent calc(var(--notch-size) - 0.5px),
        #000 var(--notch-size)
      )
      50% 100% / var(--notch-step) calc(var(--notch-size) * 2.5) repeat-x,
    radial-gradient(
        circle at 50% calc(var(--notch-size) * -1),
        transparent calc(var(--notch-size) - 0.5px),
        #000 var(--notch-size)
      )
      50% 0 / var(--notch-step) calc(var(--notch-size) * 2.5) repeat-x,
    radial-gradient(
        circle at calc(100% + var(--notch-size)) 50%,
        transparent calc(var(--notch-size) - 0.5px),
        #000 var(--notch-size)
      )
      100% 50% / calc(var(--notch-size) * 2.5) var(--notch-step) repeat-y,
    radial-gradient(
        circle at calc(var(--notch-size) * -1) 50%,
        transparent calc(var(--notch-size) - 0.5px),
        #000 var(--notch-size)
      )
      0 50% / calc(var(--notch-size) * 2.5) var(--notch-step) repeat-y,
    linear-gradient(#000 0 0) center / 100% 100% no-repeat;
  mask:
    radial-gradient(
        circle at 50% calc(100% + var(--notch-size)),
        transparent calc(var(--notch-size) - 0.5px),
        #000 var(--notch-size)
      )
      50% 100% / var(--notch-step) calc(var(--notch-size) * 2.5) repeat-x,
    radial-gradient(
        circle at 50% calc(var(--notch-size) * -1),
        transparent calc(var(--notch-size) - 0.5px),
        #000 var(--notch-size)
      )
      50% 0 / var(--notch-step) calc(var(--notch-size) * 2.5) repeat-x,
    radial-gradient(
        circle at calc(100% + var(--notch-size)) 50%,
        transparent calc(var(--notch-size) - 0.5px),
        #000 var(--notch-size)
      )
      100% 50% / calc(var(--notch-size) * 2.5) var(--notch-step) repeat-y,
    radial-gradient(
        circle at calc(var(--notch-size) * -1) 50%,
        transparent calc(var(--notch-size) - 0.5px),
        #000 var(--notch-size)
      )
      0 50% / calc(var(--notch-size) * 2.5) var(--notch-step) repeat-y,
    linear-gradient(#000 0 0) center / 100% 100% no-repeat;
  -webkit-mask-composite: source-in;
  mask-composite: intersect;
}

.agent-chat-input__field-wrap {
  position: relative;
  z-index: 1;
  border-radius: calc(var(--stamp-radius) - 3px);
  background: var(--stamp-surface);
}

.agent-chat-input__field {
  display: block;
  width: 100%;
  padding: 1rem 1.25rem;
  border: none;
  border-radius: calc(var(--stamp-radius) - 3px);
  background: #fff;
  color: #000;
  font: inherit;
  line-height: 1.45;
  resize: none;
  overflow-y: hidden;
  outline: none;
  box-sizing: border-box;
}

.agent-chat-input__field:focus-visible {
  outline: 2px solid var(--accent-border);
  outline-offset: -2px;
}

.agent-chat-input__placeholder {
  position: absolute;
  inset: 1rem 1.25rem;
  color: var(--placeholder-color);
  pointer-events: none;
  text-align: left;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.agent-chat-input-placeholder-enter-active,
.agent-chat-input-placeholder-leave-active {
  transition:
    opacity 0.35s ease,
    transform 0.35s ease;
}

.agent-chat-input-placeholder-enter-from,
.agent-chat-input-placeholder-leave-to {
  opacity: 0;
  transform: translateY(4px);
}

@media (prefers-reduced-motion: reduce) {
  .agent-chat-input-placeholder-enter-active,
  .agent-chat-input-placeholder-leave-active {
    transition: none;
  }

  .agent-chat-input-placeholder-enter-from,
  .agent-chat-input-placeholder-leave-to {
    transform: none;
  }
}

@media (prefers-color-scheme: dark) {
  .agent-chat-input__stamp {
    --stamp-border: #4a4658;
  }
}
</style>
