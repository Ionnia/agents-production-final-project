# SPEC: "Torn Magazine Scrapbook" Animated Backgrounds — Travel Website

## 1. Overview

The website uses full-viewport background scenes styled as **glossy luxury travel magazine pages**, with individual **cutout elements ripped out along their silhouettes** (torn white paper edges) layered on top. Cutouts animate with a subtle **wiggle** (paper taped to a page) and **parallax** (scroll-based depth).

There are **5 scenes**, each consisting of:
- 1 base background image (full-bleed, generated at 16:9 or 21:9)
- 4–5 cutout assets (transparent PNGs with torn white border preserved)
- Plus a set of **universal decorative cutouts** usable on any scene (boarding pass, stamp, luggage tag, magazine corner)

All image generation prompts are in **Section 6** and are final — use verbatim.

---

## 2. Visual style

| Property | Value |
|---|---|
| Background style | Glossy editorial travel photography, vibrant saturated colors, coated-paper sheen |
| Cutout style | Same photographic style, torn paper edge following the object contour, narrow rough **white torn border hugging the silhouette** |
| Cutout shadow | CSS `filter: drop-shadow(2px 3px 2px rgba(0,0,0,0.25))` — sells "paper laid on top" |
| Gloss on cutouts | Do NOT bake into asset. Optional CSS overlay: subtle diagonal white gradient at low opacity (can be slowly animated for light-catching effect) |

---

## 3. Asset pipeline

1. Generate cutouts with the prompts in Section 6 (objects come on **plain pure white background**).
2. Remove the white background with `rembg` / Photoshop Remove Background, **masking just outside the torn white border** — the white torn border itself must be kept; it is the core visual cue.
3. Export as transparent PNG (or WebP with alpha). Trim to bounding box.
4. If a generator bakes in a ground shadow or scenery sliver under an object: remove it in cleanup, or accept it if it will be covered.
5. If a generator ignores "empty composition" on a background and inserts an object (e.g. a boat): inpaint it out, or leave it if a cutout will sit on top of it.
6. Backgrounds: generate at 16:9 or 21:9. Zone descriptions in the prompts ("lower half", "upper third") behave predictably only at wide ratios.

**Naming convention:** `scene{N}-bg.webp`, `scene{N}-{asset}.png` (e.g. `scene1-palm.png`), `universal-{asset}.png`.

---

## 4. Animation requirements

### 4.1 Wiggle (idle animation)
- Subtle continuous rotation loop: `rotate(-1.5deg) → rotate(1.5deg)`, ease-in-out, alternate.
- `transform-origin` near one "taped" corner of the cutout (e.g. `top left` or `20% 10%`), NOT center — paper pinned at a corner, not spinning.
- Randomize per element: duration 3–6 s, random negative `animation-delay`, slightly different amplitude (±1° to ±2.5°). No two elements should wiggle in sync.
- Respect `prefers-reduced-motion: reduce` → disable wiggle and parallax.

### 4.2 Parallax (scroll-based)
Three depth bands, applied as scroll-speed multipliers (1.0 = normal scroll):

| Layer | Scroll speed | Elements |
|---|---|---|
| Background | 1.0 (fixed or slowest) | Base scene image |
| Mid | ~0.7 | Trees, buildings, cabin, lamp, cactus, sign |
| Foreground | ~0.4 | People, vehicles, animals, tent, café set, hammock, campfire |
| Sky elements | ~0.55 + optional slow horizontal drift | Boat, eagle, balloon, pigeons |

Implementation: `transform: translateY()` driven by scroll position (IntersectionObserver + rAF, or a library like GSAP ScrollTrigger / Lenis). Avoid `background-attachment: fixed` on mobile.

### 4.3 Performance
- Animate only `transform` / `opacity`; `will-change: transform` on animated cutouts.
- Lazy-load scenes below the fold. Serve backgrounds as WebP/AVIF, ~200–400 KB each; cutouts < 100 KB.
- Cap simultaneous wiggling elements per viewport (~8) on low-end devices.

---

## 5. Scene composition & placement maps

Coordinates are (x%, y%) of viewport, anchor = bottom-center of cutout unless noted. Treat as starting points; fine-tune visually. Cutout widths given as % of viewport width (vw).

### Scene 1 — Tropical Island
Background zones: horizon in upper third; open turquoise water mid-frame; empty white-sand beach = lower ~40%.

| Asset | Position | Width | Layer |
|---|---|---|---|
| Sailboat | (60%, 30%) on water | 10–14vw | sky/water drift |
| Palm tree | (12%, 55%) at beach edge | 14–18vw | mid |
| Hammock | (75%, 70%) on beach | 16–20vw | foreground |
| Traveler (back view) | (40%, 78%) on beach | 8–10vw | foreground |

### Scene 2 — Mountain Camp
Zones: ridges in upper third; large open sky above; flat empty meadow = lower third.

| Asset | Position | Width | Layer |
|---|---|---|---|
| Eagle | (70%, 18%) in sky | 8–10vw | sky drift |
| Pine tree | (10%, 60%) | 12–16vw | mid |
| Tent | (65%, 80%) on meadow | 14–18vw | foreground |
| Campfire | (48%, 86%) near tent | 8–10vw | foreground |
| Hiker | (25%, 82%) on meadow | 8–10vw | foreground |

### Scene 3 — Desert Road Trip
Zones: road runs from bottom edge toward mesas on the LEFT; flat open desert on the RIGHT of road; sky = upper half.

| Asset | Position | Width | Layer |
|---|---|---|---|
| Hot air balloon | (78%, 20%) in sky | 10–14vw | sky drift (slow vertical bob optional) |
| Saguaro cactus | (85%, 62%) right-side desert | 8–12vw | mid |
| Road sign | (35%, 65%) beside road | 6–8vw | mid |
| Camper van | (50%, 82%) on road | 18–24vw | foreground |

### Scene 4 — Old European Town
Zones: empty cobblestone square = lower half; facades pushed to upper part; sky band above rooftops.

| Asset | Position | Width | Layer |
|---|---|---|---|
| Pigeons (flock) | (55%, 15%) sky band | 10–12vw | sky drift |
| Street lamp | (88%, 55%) near facade | 6–8vw | mid |
| Café set | (70%, 75%) on square | 16–20vw | foreground |
| Tourist with map | (35%, 80%) on square | 8–10vw | foreground |
| Vespa scooter | (15%, 83%) on square | 12–16vw | foreground |

### Scene 5 — Northern Lights / Winter
Zones: aurora confined to upper half; low hills at mid horizon; smooth empty snowfield = lower half.

| Asset | Position | Width | Layer |
|---|---|---|---|
| Cabin | (72%, 62%) near horizon | 14–18vw | mid |
| Spruce tree | (12%, 58%) | 12–16vw | mid |
| Person looking up | (40%, 80%) on snowfield | 8–10vw | foreground |
| Husky | (52%, 84%) beside person | 7–9vw | foreground |

### Universal decorative cutouts
Sprinkle 1–3 per scene at low visual weight (corners, margins): boarding pass, postage stamp, luggage tag, torn magazine corner. Slight static rotation (−8° to +8°), gentle wiggle, foreground parallax layer. Must never overlap primary content/CTAs.

> **Implementation note:** Deferred — no `universal-*.png` assets exist in `frontend/src/assets/` yet. Scene components use WebP derivatives of the source PNGs (~45 MB → ~3 MB total).

---

## 6. Final text2image prompts (use verbatim)

### Negative prompt (apply to ALL cutout generations, if supported)
```
background, scenery, landscape, sky, ground, shadow on ground, rectangular crop, frame, border box
```

### Scene 1 — Tropical Island

**Background:**
```
Glossy luxury travel magazine photograph of a tropical island coastline, wide-angle composition, horizon line in upper third, large expanse of calm vivid turquoise ocean filling the middle of the frame with completely open empty water, wide pristine white sand beach filling the entire lower part of the frame as large empty foreground, distant small green island far on the horizon, clear sky, editorial landscape photography, vibrant saturated colors, crisp and sharp, glossy coated paper sheen, generous negative space, no people, no boats, no trees, no objects anywhere, clean minimal composition designed as a backdrop
```

**Palm tree:**
```
Single lush palm tree, glossy luxury travel magazine photograph, vibrant saturated colors, single isolated object only, no background scenery, no environment, nothing else in frame, torn paper edge following the contour of the palm tree, ripped out of a glossy magazine along the object silhouette, narrow rough white torn border hugging the shape, paper fibers visible at edges, centered on plain pure white background, full tree visible from trunk base to leaves, not cropped
```

**Traveler:**
```
Stylish traveler with straw hat and linen outfit, full body, seen from behind, glossy luxury travel magazine photograph, editorial fashion photography, single isolated person only, no background scenery, no environment, nothing else in frame, torn paper edge following the contour of the figure, narrow rough white torn border hugging the silhouette, centered on plain pure white background, full body visible including feet, not cropped
```

**Sailboat:**
```
Elegant white sailboat, glossy luxury travel magazine photograph, vibrant saturated colors, single isolated object only, no water, no background scenery, nothing else in frame, torn paper edge following the contour of the boat and sail, narrow rough white torn border hugging the shape, centered on plain pure white background, full boat visible, not cropped
```

**Hammock:**
```
Beach hammock with white fabric stretched between two wooden posts, glossy travel magazine photograph, single isolated object only, no background scenery, no sand, nothing else in frame, torn paper edge following the contour of the hammock and posts, narrow rough white torn border hugging the shape, centered on plain pure white background, fully visible, not cropped
```

### Scene 2 — Mountain Camp

**Background:**
```
Glossy luxury travel magazine photograph of a mountain valley at golden hour, wide-angle composition, layered mountain ridges positioned in the upper third fading into distance, vast open clear sky above the peaks with plenty of empty space, large flat open alpine meadow filling the entire lower third as empty level foreground ground, editorial landscape photography, vibrant saturated colors, crisp and sharp, glossy coated paper sheen, generous negative space, no people, no tents, no trees in the foreground, no animals, no objects anywhere, clean minimal composition designed as a backdrop
```

**Tent:**
```
Premium orange dome camping tent, glossy luxury travel magazine photograph, vibrant saturated colors, single isolated object only, no background scenery, no ground, nothing else in frame, torn paper edge following the contour of the tent, narrow rough white torn border hugging the shape, centered on plain pure white background, full tent visible, not cropped
```

**Campfire:**
```
Campfire with glowing flames and stacked logs, glossy travel magazine photograph, warm vibrant tones, single isolated object only, no background scenery, no ground, nothing else in frame, torn paper edge following the contour of the fire and logs, narrow rough white torn border hugging the shape, centered on plain pure white background, fully visible, not cropped
```

**Hiker:**
```
Hiker in stylish outdoor gear with backpack and trekking poles, full body, side view, glossy luxury travel magazine photograph, single isolated person only, no background scenery, no trail, nothing else in frame, torn paper edge following the contour of the figure, narrow rough white torn border hugging the silhouette, centered on plain pure white background, full body visible including boots, not cropped
```

**Pine tree:**
```
Tall pine tree, glossy travel magazine photograph, rich green tones, single isolated object only, no background scenery, no ground, nothing else in frame, torn paper edge following the contour of the tree, narrow rough white torn border hugging the shape, centered on plain pure white background, full tree visible from trunk base to top, not cropped
```

**Eagle:**
```
Eagle soaring with spread wings, glossy travel magazine photograph, sharp detail, single isolated bird only, no sky, no background, nothing else in frame, torn paper edge following the contour of the wings and body, narrow rough white torn border hugging the silhouette, centered on plain pure white background, full wingspan visible, not cropped
```

### Scene 3 — Desert Road Trip

**Background:**
```
Glossy luxury travel magazine photograph of a desert landscape, wide-angle composition, empty straight highway running from the bottom edge toward distant red rock mesas positioned on the left side of the frame, wide flat open sandy desert plain on the right side of the road as large empty ground area, vast dramatic open sky filling the upper half of the frame with plenty of empty space, editorial landscape photography, vibrant saturated warm colors, crisp and sharp, glossy coated paper sheen, generous negative space, no vehicles, no cacti, no signs, no objects anywhere, clean minimal composition designed as a backdrop
```

**Camper van:**
```
Polished retro camper van in teal and cream, side view, glossy luxury travel magazine photograph, vibrant saturated colors, single isolated vehicle only, no road, no background scenery, nothing else in frame, torn paper edge following the contour of the van, narrow rough white torn border hugging the shape, centered on plain pure white background, full vehicle visible including wheels, not cropped
```

**Cactus:**
```
Tall saguaro cactus, glossy travel magazine photograph, vivid green, single isolated object only, no desert, no background scenery, nothing else in frame, torn paper edge following the contour of the cactus, narrow rough white torn border hugging the shape, centered on plain pure white background, full cactus visible from base to top, not cropped
```

**Road sign:**
```
Rustic wooden road sign with directional arrow on a post, glossy travel magazine photograph, single isolated object only, no background scenery, no ground, nothing else in frame, torn paper edge following the contour of the sign and post, narrow rough white torn border hugging the shape, centered on plain pure white background, fully visible, not cropped
```

**Hot air balloon:**
```
Colorful striped hot air balloon with basket, glossy luxury travel magazine photograph, vibrant saturated colors, single isolated object only, no sky, no background, nothing else in frame, torn paper edge following the contour of the balloon and basket, narrow rough white torn border hugging the shape, centered on plain pure white background, full balloon and basket visible, not cropped
```

### Scene 4 — Old European Town

**Background:**
```
Glossy luxury travel magazine photograph of an old European town, wide-angle composition, large wide empty cobblestone square filling the entire lower half of the frame as open level foreground, pastel building facades with terracotta rooftops pushed back along the upper part of the frame, clear band of open sky visible above the rooftops, golden morning light, editorial travel photography, vibrant saturated colors, crisp and sharp, glossy coated paper sheen, generous negative space, completely empty square, no people, no vehicles, no café tables, no street furniture, no objects anywhere, clean minimal composition designed as a backdrop
```

**Vespa scooter:**
```
Shiny red vintage Vespa scooter, side view, glossy luxury travel magazine photograph, vibrant saturated colors, single isolated vehicle only, no street, no background scenery, nothing else in frame, torn paper edge following the contour of the scooter, narrow rough white torn border hugging the shape, centered on plain pure white background, full scooter visible including wheels, not cropped
```

**Tourist:**
```
Elegant tourist in summer dress holding a paper map, full body, glossy luxury travel magazine photograph, editorial fashion photography, single isolated person only, no background scenery, no street, nothing else in frame, torn paper edge following the contour of the figure, narrow rough white torn border hugging the silhouette, centered on plain pure white background, full body visible including shoes, not cropped
```

**Café set:**
```
Chic café table with umbrella and two bistro chairs, glossy travel magazine photograph, vibrant colors, single isolated furniture set only, no background scenery, no pavement, nothing else in frame, torn paper edge following the contour of the table, chairs and umbrella, narrow rough white torn border hugging the shape, centered on plain pure white background, fully visible, not cropped
```

**Pigeons:**
```
Three pigeons in flight, glossy travel magazine photograph, sharp detail, isolated birds only, no sky, no background, nothing else in frame, torn paper edge following the contour of the birds as one cluster, narrow rough white torn border hugging the silhouettes, centered on plain pure white background, all birds fully visible, not cropped
```

**Street lamp:**
```
Ornate street lamp with hanging flower basket, glossy travel magazine photograph, vibrant colors, single isolated object only, no background scenery, no ground, nothing else in frame, torn paper edge following the contour of the lamp post and basket, narrow rough white torn border hugging the shape, centered on plain pure white background, full lamp visible from base to top, not cropped
```

### Scene 5 — Northern Lights / Winter

**Background:**
```
Glossy luxury travel magazine photograph of a snowy nordic landscape at night, wide-angle composition, vivid aurora borealis in green and violet contained in the upper half of the sky, low distant snow-covered hills along the horizon line in the middle of the frame, vast smooth open snowfield filling the entire lower half as large flat empty foreground ground, editorial landscape photography, vibrant saturated colors, crisp and sharp, glossy coated paper sheen, generous negative space, no cabins, no trees, no people, no animals, no objects anywhere, clean minimal composition designed as a backdrop
```

**Cabin:**
```
Cozy wooden cabin with warm glowing windows and snow-covered roof, glossy luxury travel magazine photograph, vibrant rich colors, single isolated building only, no landscape, no background scenery, nothing else in frame, torn paper edge following the contour of the cabin, narrow rough white torn border hugging the shape, centered on plain pure white background, full cabin visible, not cropped
```

**Spruce tree:**
```
Snow-covered spruce tree, glossy travel magazine photograph, crisp winter detail, single isolated object only, no snowy ground, no background scenery, nothing else in frame, torn paper edge following the contour of the tree, narrow rough white torn border hugging the shape, centered on plain pure white background, full tree visible from base to top, not cropped
```

**Person:**
```
Person in stylish winter parka gazing upward, full body, back view, glossy luxury travel magazine photograph, single isolated person only, no background scenery, no snow, nothing else in frame, torn paper edge following the contour of the figure, narrow rough white torn border hugging the silhouette, centered on plain pure white background, full body visible including boots, not cropped
```

**Husky:**
```
Fluffy husky dog sitting, glossy travel magazine photograph, sharp vibrant detail, single isolated animal only, no snow, no background scenery, nothing else in frame, torn paper edge following the contour of the dog, narrow rough white torn border hugging the silhouette, centered on plain pure white background, full dog visible, not cropped
```

### Universal decorative cutouts

**Boarding pass:**
```
Luxury boarding pass with gold foil accents, glossy print, single isolated object only, nothing else in frame, torn rough edge on one side, centered on plain pure white background, fully visible, not cropped
```

**Postage stamp:**
```
Glossy printed postage stamp with airplane motif, vibrant colors, single isolated stamp only, nothing else in frame, perforated edges, slightly torn corner, centered on plain pure white background, fully visible, not cropped
```

**Luggage tag:**
```
Premium paper luggage tag with leather strap, glossy photograph style, single isolated object only, nothing else in frame, torn corner, centered on plain pure white background, fully visible, not cropped
```

**Magazine corner:**
```
Torn glossy magazine page corner with partial elegant headline typography, shiny coated paper, torn edges on all sides, single isolated paper fragment only, nothing else in frame, centered on plain pure white background, fully visible, not cropped
```

---

## 7. Troubleshooting generation issues

| Problem | Fix |
|---|---|
| Tear edges too clean | Add: `deckled ripped edge, irregular tear` |
| Cutout includes scenery rectangle instead of silhouette tear | Re-emphasize: `torn edge following the contour of the object`, regenerate; keep negative prompt active |
| Object cropped (feet/trunk base cut off) | Keep `full object visible, not cropped`; increase canvas margin or generate at taller aspect for tall objects (palm, lamp, cactus) |
| Ground shadow baked under object | Negative prompt `shadow on ground`; otherwise erase in cleanup |
| Background generator inserts focal object despite "empty" instructions | Inpaint out, or cover with a cutout |
| Lighting mismatch between cutout and scene | Append scene lighting to cutout prompt, e.g. `golden hour warm lighting` (Scene 2/4), `cool blue night ambient light` (Scene 5) |
| Glossy sheen renders as white smear on cutouts | Remove sheen phrasing from that cutout; add gloss via CSS overlay instead |

---

## 8. Acceptance criteria

- [ ] 5 backgrounds, wide aspect, each with verifiably empty placement zones per Section 5
- [ ] All cutouts: transparent PNG/WebP, torn white border intact, object complete (not cropped), no scenery remnants
- [ ] Consistent glossy-editorial style across all assets within a scene
- [ ] Wiggle: corner-anchored, desynchronized, ±1–2.5°, 3–6 s loops
- [ ] Parallax: 3 depth bands per Section 4.2, smooth at 60 fps on mid-range mobile
- [ ] `prefers-reduced-motion` disables all motion
- [ ] Cutouts never overlap primary UI content or CTAs
