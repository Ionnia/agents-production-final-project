import { useParallax } from './useParallax'

export function useSceneParallax() {
  const { parallaxStyle: skyLayerStyle } = useParallax('sky')
  const { parallaxStyle: midLayerStyle } = useParallax('mid')
  const { parallaxStyle: foregroundLayerStyle } = useParallax('foreground')

  return { skyLayerStyle, midLayerStyle, foregroundLayerStyle }
}
