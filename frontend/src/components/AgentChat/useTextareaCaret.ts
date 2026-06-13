import { useEventListener } from "@vueuse/core";
import { onScopeDispose, shallowRef, type Ref } from "vue";

/**
 * Style properties that affect text layout. They are copied onto the
 * mirror element so its text wraps exactly like the textarea's.
 */
const MIRROR_STYLE_PROPS = [
  "direction",
  "box-sizing",
  "border-top-width",
  "border-right-width",
  "border-bottom-width",
  "border-left-width",
  "padding-top",
  "padding-right",
  "padding-bottom",
  "padding-left",
  "font-style",
  "font-variant",
  "font-weight",
  "font-stretch",
  "font-size",
  "line-height",
  "font-family",
  "text-align",
  "text-transform",
  "text-indent",
  "letter-spacing",
  "word-spacing",
  "tab-size",
] as const;

/** Must stay in sync with `.agent-chat-input__caret` / `__field-caret` CSS. */
const CARET_HEIGHT_EM = 1.2;
const CARET_OFFSET_EM = 0.2;

function measureBaselineFromLineTop(styles: CSSStyleDeclaration): number {
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  if (!ctx) return 0;

  ctx.font = `${styles.fontStyle} ${styles.fontVariant} ${styles.fontWeight} ${styles.fontSize} ${styles.fontFamily}`;
  const metrics = ctx.measureText("Mg");
  const fontSize = Number.parseFloat(styles.fontSize);
  const lineHeight = Number.parseFloat(styles.lineHeight);
  const halfLeading = (lineHeight - fontSize) / 2;

  return halfLeading + metrics.actualBoundingBoxAscent;
}

/**
 * Tracks the pixel position of the caret inside a textarea, using the
 * standard "mirror div" technique: an invisible element with identical
 * text metrics renders the value up to the caret, and a marker span
 * after it lands exactly where the caret is.
 *
 * Lets us hide the native caret (whose size cannot be styled) and draw
 * a custom one in its place.
 */
export function useTextareaCaret(textarea: Ref<HTMLTextAreaElement | null>) {
  const focused = shallowRef(false);
  const x = shallowRef(0);
  const y = shallowRef(0);

  let mirror: HTMLDivElement | null = null;
  let frame = 0;

  function measure() {
    const el = textarea.value;
    if (!el) return;

    if (!mirror) {
      mirror = document.createElement("div");
      mirror.setAttribute("aria-hidden", "true");
      document.body.appendChild(mirror);
    }

    const styles = getComputedStyle(el);
    for (const prop of MIRROR_STYLE_PROPS) {
      mirror.style.setProperty(prop, styles.getPropertyValue(prop));
    }
    Object.assign(mirror.style, {
      position: "absolute",
      top: "0",
      left: "-9999px",
      visibility: "hidden",
      whiteSpace: "pre-wrap",
      overflowWrap: "break-word",
      width: styles.width,
    });

    const index = el.selectionEnd ?? el.value.length;
    mirror.textContent = el.value.slice(0, index);
    const marker = document.createElement("span");
    // Trailing content keeps the marker glued to the text flow; "."
    // guarantees the span has dimensions on an empty line.
    marker.textContent = el.value.slice(index) || ".";
    mirror.appendChild(marker);

    const fontSize = Number.parseFloat(styles.fontSize);
    const baselineFromLineTop = measureBaselineFromLineTop(styles);
    const caretHeight = fontSize * CARET_HEIGHT_EM;
    const caretOffset = fontSize * CARET_OFFSET_EM;

    x.value = marker.offsetLeft - el.scrollLeft;
    // Match the placeholder caret: bottom sits on the text baseline,
    // then shifts down by CARET_OFFSET_EM.
    y.value =
      marker.offsetTop -
      el.scrollTop +
      baselineFromLineTop -
      caretHeight +
      caretOffset;
  }

  function scheduleMeasure() {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(measure);
  }

  useEventListener(textarea, "focus", () => {
    focused.value = true;
    scheduleMeasure();
  });
  useEventListener(textarea, "blur", () => {
    focused.value = false;
  });
  useEventListener(textarea, "input", scheduleMeasure);
  useEventListener(textarea, "scroll", scheduleMeasure, { passive: true });
  useEventListener(document, "selectionchange", () => {
    if (document.activeElement === textarea.value) scheduleMeasure();
  });
  useEventListener(window, "resize", scheduleMeasure, { passive: true });

  onScopeDispose(() => {
    cancelAnimationFrame(frame);
    mirror?.remove();
    mirror = null;
  });

  return { focused, x, y };
}
