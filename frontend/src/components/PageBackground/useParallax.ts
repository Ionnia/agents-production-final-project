import {
  createSharedComposable,
  usePreferredReducedMotion,
  useWindowScroll,
} from '@vueuse/core'
import { computed, type CSSProperties } from 'vue'

export const PARALLAX_SPEEDS = {
  background: 1.0,
  sky: 0.55,
  mid: 0.7,
  foreground: 0.4,
} as const

export type ParallaxLayer = keyof typeof PARALLAX_SPEEDS

const useParallaxState = createSharedComposable(() => {
  const { y: scrollY } = useWindowScroll()
  const prefersReducedMotion = usePreferredReducedMotion()

  function getOffset(layer: ParallaxLayer): number {
    if (import.meta.env.SSR || prefersReducedMotion.value || layer === 'background') {
      return 0
    }
    return scrollY.value * (1 - PARALLAX_SPEEDS[layer])
  }

  function parallaxStyleForLayer(layer: ParallaxLayer): CSSProperties {
    if (import.meta.env.SSR || prefersReducedMotion.value || layer === 'background') {
      return {}
    }

    const offset = getOffset(layer)

    if (layer === 'sky') {
      const drift = scrollY.value * 0.02
      return {
        transform: `translate(${drift}px, ${-offset}px)`,
        willChange: 'transform',
      }
    }

    return {
      transform: `translateY(${-offset}px)`,
      willChange: 'transform',
    }
  }

  return { scrollY, prefersReducedMotion, getOffset, parallaxStyleForLayer }
})

export function useParallax(): {
  scrollY: ReturnType<typeof useParallaxState>['scrollY']
  prefersReducedMotion: ReturnType<typeof useParallaxState>['prefersReducedMotion']
  getOffset: ReturnType<typeof useParallaxState>['getOffset']
  parallaxStyle: ReturnType<typeof useParallaxState>['parallaxStyleForLayer']
}
export function useParallax(layer: ParallaxLayer): {
  offsetY: ReturnType<typeof computed<number>>
  parallaxStyle: ReturnType<typeof computed<CSSProperties>>
}
export function useParallax(layer?: ParallaxLayer) {
  const { scrollY, prefersReducedMotion, getOffset, parallaxStyleForLayer } = useParallaxState()

  if (layer !== undefined) {
    const offsetY = computed(() => getOffset(layer))
    const parallaxStyle = computed(() => parallaxStyleForLayer(layer))
    return { offsetY, parallaxStyle }
  }

  return {
    scrollY,
    prefersReducedMotion,
    getOffset,
    parallaxStyle: parallaxStyleForLayer,
  }
}
