import { usePreferredReducedMotion } from "@vueuse/core";
import { onScopeDispose, shallowRef, watch, type Ref } from "vue";

interface UseTypewriterPlaceholderOptions {
  /** While true, the animation freezes (e.g. when the user is typing). */
  paused?: Ref<boolean>;
  typeDelayMs?: number;
  deleteDelayMs?: number;
  holdDelayMs?: number;
  restDelayMs?: number;
}

type Phase = "typing" | "holding" | "deleting" | "resting";

/**
 * Cycles through phrases like a person at a keyboard: types one out,
 * pauses to "read" it, deletes it character by character (faster than
 * typing, as people do), then moves on to the next phrase.
 *
 * Under `prefers-reduced-motion` the per-character animation is replaced
 * with a plain whole-phrase rotation.
 */
export function useTypewriterPlaceholder(
  phrases: readonly string[],
  options: UseTypewriterPlaceholderOptions = {},
) {
  const {
    paused,
    typeDelayMs = 55,
    deleteDelayMs = 26,
    holdDelayMs = 2300,
    restDelayMs = 500,
  } = options;

  const text = shallowRef("");
  const reducedMotion = usePreferredReducedMotion();

  let phraseIndex = 0;
  let charCount = 0;
  let phase: Phase = "typing";
  let timer: ReturnType<typeof setTimeout> | undefined;

  // Human typing isn't metronomic; vary each keystroke a little.
  function jitter(base: number) {
    return base * (0.75 + Math.random() * 0.6);
  }

  function schedule(delayMs: number) {
    clearTimeout(timer);
    timer = setTimeout(tick, delayMs);
  }

  function tick() {
    if (paused?.value) return;

    if (reducedMotion.value === "reduce") {
      text.value = phrases[phraseIndex] ?? "";
      phraseIndex = (phraseIndex + 1) % phrases.length;
      schedule(3000);
      return;
    }

    const phrase = phrases[phraseIndex] ?? "";

    switch (phase) {
      case "typing": {
        charCount += 1;
        text.value = phrase.slice(0, charCount);
        if (charCount >= phrase.length) {
          phase = "holding";
          schedule(holdDelayMs);
        } else {
          schedule(jitter(typeDelayMs));
        }
        break;
      }
      case "holding": {
        phase = "deleting";
        schedule(jitter(deleteDelayMs));
        break;
      }
      case "deleting": {
        charCount = Math.max(charCount - 1, 0);
        text.value = phrase.slice(0, charCount);
        if (charCount === 0) {
          phase = "resting";
          phraseIndex = (phraseIndex + 1) % phrases.length;
          schedule(restDelayMs);
        } else {
          schedule(jitter(deleteDelayMs));
        }
        break;
      }
      case "resting": {
        phase = "typing";
        schedule(jitter(typeDelayMs));
        break;
      }
    }
  }

  if (paused) {
    watch(paused, (isPaused) => {
      if (isPaused) {
        clearTimeout(timer);
      } else {
        // Restart the current phrase from scratch so the resume
        // doesn't pop in mid-word.
        phase = "typing";
        charCount = 0;
        text.value = "";
        schedule(restDelayMs);
      }
    });
  }

  schedule(restDelayMs);

  onScopeDispose(() => clearTimeout(timer));

  return { text };
}
