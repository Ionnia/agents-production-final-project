# AGENTS.md

Guidance for AI coding agents working in this repository. `CLAUDE.md` is a symlink to this file.

## Spec files

The repository is described by `SPECIFICATION.md` files that must always reflect the **current state** of the project.

- The repository **root** contains `SPECIFICATION.md` describing the **global architecture**.
- Each **module** contains its own `SPECIFICATION.md` describing the current state of that module specifically.
- Every module `SPECIFICATION.md` must be **referenced from the root (global) `SPECIFICATION.md`**.

Whenever you change something, **update the relevant `SPECIFICATION.md` in the same change** so that:

- the root `SPECIFICATION.md` always describes the current global architecture, and
- each module `SPECIFICATION.md` always describes the current state of that module.

Keep the specs in sync with the code at all times — a spec that no longer matches the code is a bug.
