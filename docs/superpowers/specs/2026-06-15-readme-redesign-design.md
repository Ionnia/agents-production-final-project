# README Redesign + Asset Pipeline — Design

**Date:** 2026-06-15
**Status:** Approved (design)
**Scope:** Presentation only. No application code, contracts, or module behavior change.

## Goal

Turn the root `README.md` into a beautiful, well-structured project page that **leads with a
description of the agent and what it can do**, embeds the demo assets from `docs/readme_assets/`,
and preserves all existing technical substance. Language stays **Russian** (course, GigaChat, and
current README are all Russian-context). Visual direction: **Approach 1 — polished product README**
(centered hero + badges + inline demo + capabilities section + screenshot showcase + TOC, with the
long dataset tables tucked into collapsible `<details>` blocks).

## Assets

Source files in `docs/readme_assets/`:

| File | Source state | Action |
|---|---|---|
| `demo_movie.mov` | 1.0 GB, 4K 3840×2072, 120 fps, H.264 ~69 Mbps, **no audio** | Source for 3 re-encodes; **never committed** |
| `login_screen.png` | 13 MB, 4K 3840×2064 | Resize ~1600 px wide, recompress PNG (<500 KB); committed |
| `authorized_screen.png` | 13 MB, 4K 3840×2064 | Resize ~1600 px wide, recompress PNG (<500 KB); committed |

### Video encodes (3 versions for the user to choose)

Identical high-quality settings, quality favored over speed:

```
-c:v libx264 -preset veryslow -crf 20 -pix_fmt yuv420p -movflags +faststart -r 30 -an
```

- `demo_4k.mp4` — native 3840×2072 (no scale)
- `demo_1440p.mp4` — `scale=-2:1440` ("2K")
- `demo_1080p.mp4` — `scale=-2:1080`

Encoded fastest-first (1080p → 1440p → 4K). Final size + encode time reported for each so the user
can pick by the size/quality tradeoff. The 4K `veryslow` encode may exceed GitHub's **100 MB** file
limit — flagged if so (still usable via inline upload, just not committable).

## Demo embed mechanism

Inline `<video>` playback (user's choice). GitHub only renders an inline player for files uploaded
through its web editor, which yields a `user-attachments` URL. The README therefore ships with:

1. A clearly-marked `<video src="…PLACEHOLDER…">` block.
2. An HTML comment with step-by-step instructions: drag-drop the chosen `demo_*.mp4` into a GitHub
   markdown editor → copy the returned `user-attachments` URL → paste into `src`.
3. A poster frame + plain link as a fallback so the README never looks broken pre-upload.

The encoded `demo_*.mp4` files are local artifacts for the user to choose from and upload; they are
**git-ignored**, not committed (the inline embed uses the uploaded URL, not a repo file).

## README structure (Approach 1, Russian)

1. **Hero** (centered): title · one-line tagline · tech-stack badge row (Vue 3, TypeScript, FastAPI,
   LangGraph, Chroma, GigaChat, Docker, SQLite, Python 3.13) · inline demo video
2. **Возможности** — what the agent can do, scannable bullets: планирование, перепланирование,
   конфликты предпочтений, лимиты бюджета, уточнения, эскалация, RAG-ответы по политикам, учёт
   состава группы, карта/календарь в UI
3. **Скриншоты** — login + authorized
4. **Содержание** (table of contents)
5. **Архитектура** — existing module table + ASCII diagram + `SPECIFICATION.md` link
6. **Запуск** — Docker + local; long no-Docker variant inside `<details>`
7. **Структура репозитория** — kept
8. **Учебный кейс и данные** — kept; large dataset tables inside `<details>`
9. **Документация** — links to `docs/*` and the SPECIFICATION files

Every technical detail currently in the README is preserved — reorganized, not removed.

## Housekeeping

- Add to `.gitignore`: `docs/readme_assets/demo_movie.mov` and `docs/readme_assets/demo_*.mp4`
  (keeps the 1 GB source and heavy encodes out of git history).
- Commit only the optimized screenshots.
- **No `SPECIFICATION.md` change** — architecture, contracts, and modules are unchanged; this is
  presentation only. (Noted explicitly because repo rules require specs to track code.)

## Verification

- Confirm every asset path referenced in the README resolves on disk.
- Report final encode sizes + times; flag any file over 100 MB.
- Sanity-check markdown structure (headings, TOC anchors, `<details>`, badge URLs) before claiming done.

## Out of scope

- Translating the README to English or making it bilingual.
- Hosting the video externally (YouTube/CDN) or generating a banner/logo image.
- Any change to application code, data, or specs.
