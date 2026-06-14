// Prerender dithered background layers from the source travel photos.
//
// For every scene it produces TWO master images at 4K-class resolution:
//   <name>-mono.webp   monochrome + the image's own accent  (bottom layer, opaque)
//   <name>-color.webp  faithful colorized dither            (top layer, transparent)
//
// At runtime the frontend stacks them and reveals the color layer through a soft
// radial CSS mask that follows the cursor. Nothing is dithered at runtime.
//
// Add a new background: drop  foo.png  +  foo_colorized.png  into
// src/assets/backgrounds/ and run:  pnpm prerender:bg
//
// Requires the `cwebp` CLI on PATH (libwebp) for WebP encoding.

import { createCanvas, loadImage } from '@napi-rs/canvas'
import { readdirSync, mkdirSync, writeFileSync, unlinkSync, existsSync } from 'node:fs'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const SRC = join(__dirname, '../src/assets/backgrounds')
const OUT = join(__dirname, '../public/backgrounds')

// ─── Look parameters (the values dialled in via the prototype) ──────────────
const OUTPUT_W   = 3840   // master width in px (height follows the source aspect)
const REF_WIDTH  = 1800   // display width the dot pitch is calibrated against (full-screen viewport)
const DOT        = 3      // ~apparent dot pitch (px) at REF_WIDTH → sets dot density
const ACCENT     = 0.85   // how strongly the image's own accent shows in the mono layer
const SATURATION = 1.75   // saturation of the colorized reveal layer (1 = truthful)
const BG         = '#0c0a08' // baked background of the mono (bottom) layer
const WEBP_Q     = 80
// Dot density is resolution-independent: COLS dots across, whatever the output size.
const COLS = Math.round(REF_WIDTH / DOT)
// ───────────────────────────────────────────────────────────────────────────

const smoothstep = (a, b, x) => { const t = Math.max(0, Math.min(1, (x - a) / (b - a))); return t * t * (3 - 2 * t) }

function sampleToGrid(img, cols, rows) {
  const c = createCanvas(cols, rows)
  const o = c.getContext('2d')
  const ir = img.width / img.height, cr = cols / rows
  let sw, sh, sx, sy
  if (ir > cr) { sh = img.height; sw = sh * cr; sx = (img.width - sw) / 2; sy = 0 }
  else { sw = img.width; sh = sw / cr; sx = 0; sy = (img.height - sh) / 2 }
  o.drawImage(img, sx, sy, sw, sh, 0, 0, cols, rows)
  return o.getImageData(0, 0, cols, rows).data
}

function writeWebp(canvas, outPath, alpha) {
  const tmp = outPath.replace(/\.webp$/, '.tmp.png')
  writeFileSync(tmp, canvas.toBuffer('image/png'))
  execFileSync('cwebp', ['-q', String(WEBP_Q), ...(alpha ? ['-alpha_q', '100'] : []), tmp, '-o', outPath], { stdio: 'ignore' })
  unlinkSync(tmp)
}

async function renderScene(name) {
  const baseImg = await loadImage(join(SRC, `${name}.png`))
  const colorImg = await loadImage(join(SRC, `${name}_colorized.png`))

  const OUTPUT_H = Math.round(OUTPUT_W * (baseImg.height / baseImg.width))
  const cell = OUTPUT_W / COLS
  const cols = COLS, rows = Math.round(OUTPUT_H / cell)
  const maxR = cell * 0.62
  const offx = (OUTPUT_W - cols * cell) / 2 + cell / 2
  const offy = (OUTPUT_H - rows * cell) / 2 + cell / 2

  const base = sampleToGrid(baseImg, cols, rows)
  const color = sampleToGrid(colorImg, cols, rows)

  const monoC = createCanvas(OUTPUT_W, OUTPUT_H), m = monoC.getContext('2d')
  const colC = createCanvas(OUTPUT_W, OUTPUT_H), c = colC.getContext('2d')
  m.fillStyle = BG; m.fillRect(0, 0, OUTPUT_W, OUTPUT_H) // color layer stays transparent

  for (let y = 0; y < rows; y++) for (let x = 0; x < cols; x++) {
    const k = (y * cols + x) * 4, px = offx + x * cell, py = offy + y * cell

    // ── mono + accent (from the desaturated base image) ──
    const br = base[k], bg = base[k + 1], bb = base[k + 2]
    const L = (0.299 * br + 0.587 * bg + 0.114 * bb) / 255
    const mxc = Math.max(br, bg, bb), mnc = Math.min(br, bg, bb), S = mxc > 0 ? (mxc - mnc) / mxc : 0
    const v = 0.12 + 0.88 * Math.pow(L, 0.85)
    let r = 238 * v, g = 230 * v, b = 212 * v
    if (S > 0.16) {
      const w = smoothstep(0.16, 0.42, S) * ACCENT, lift = Math.min(1.8, 170 / (mxc || 1))
      r += (Math.min(255, br * lift) - r) * w
      g += (Math.min(255, bg * lift) - g) * w
      b += (Math.min(255, bb * lift) - b) * w
    }
    const rb = maxR * Math.min(1, Math.pow(L, 0.9) + S * 0.5)
    if (rb >= 0.25) { m.fillStyle = `rgb(${r | 0},${g | 0},${b | 0})`; m.beginPath(); m.arc(px, py, rb, 0, 6.2832); m.fill() }

    // ── faithful colorized dither (sizes + colors from the colorized image) ──
    let cr = color[k], cg = color[k + 1], cb = color[k + 2]
    const cL = (0.299 * cr + 0.587 * cg + 0.114 * cb) / 255
    if (SATURATION !== 1) {
      const l = 0.299 * cr + 0.587 * cg + 0.114 * cb
      cr = Math.max(0, Math.min(255, l + (cr - l) * SATURATION))
      cg = Math.max(0, Math.min(255, l + (cg - l) * SATURATION))
      cb = Math.max(0, Math.min(255, l + (cb - l) * SATURATION))
    }
    const rc = maxR * Math.min(1, Math.pow(cL, 0.92))
    if (rc >= 0.25) { c.fillStyle = `rgb(${cr | 0},${cg | 0},${cb | 0})`; c.beginPath(); c.arc(px, py, rc, 0, 6.2832); c.fill() }
  }

  writeWebp(monoC, join(OUT, `${name}-mono.webp`), false)
  writeWebp(colC, join(OUT, `${name}-color.webp`), true)
  console.log(`  ✓ ${name}  ${OUTPUT_W}×${OUTPUT_H}  (${cols}×${rows} dots)`)
}

const scenes = readdirSync(SRC)
  .filter(f => f.endsWith('_colorized.png'))
  .map(f => f.replace('_colorized.png', ''))
  .filter(n => existsSync(join(SRC, `${n}.png`)))
  .sort()

if (!existsSync(OUT)) mkdirSync(OUT, { recursive: true })
console.log(`Prerendering ${scenes.length} scenes @ ${OUTPUT_W}px wide · ${COLS} dot cols · accent ${ACCENT} · saturation ${SATURATION}`)
for (const name of scenes) await renderScene(name)
console.log(`Done → ${OUT}`)
