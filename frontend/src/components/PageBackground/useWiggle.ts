export interface WiggleConfig {
  duration: string
  delay: string
  amplitude: string
  origin: string
}

const ORIGINS = [
  'top left',
  'top right',
  '20% 10%',
  '80% 15%',
  '15% 85%',
  '90% 90%',
] as const

function random(min: number, max: number): number {
  return min + Math.random() * (max - min)
}

export function createWiggleConfig(): WiggleConfig {
  const durationSec = random(3, 6)
  const amplitudeDeg = random(1, 2.5)
  const delaySec = -random(0, durationSec)
  const origin = ORIGINS[Math.floor(Math.random() * ORIGINS.length)]!

  return {
    duration: `${durationSec.toFixed(2)}s`,
    delay: `${delaySec.toFixed(2)}s`,
    amplitude: `${amplitudeDeg.toFixed(2)}deg`,
    origin,
  }
}

export function wiggleStyle(config: WiggleConfig): Record<string, string> {
  // Per-element longhands — inherited --animate-cutout-wiggle on :root resolves
  // nested vars once at root (all cutouts sync). Keyframes still read --wiggle-amplitude.
  return {
    '--wiggle-amplitude': config.amplitude,
    '--wiggle-origin': config.origin,
    animationName: 'cutout-wiggle',
    animationDuration: config.duration,
    animationDelay: config.delay,
    animationTimingFunction: 'ease-in-out',
    animationIterationCount: 'infinite',
    animationDirection: 'alternate',
  }
}
