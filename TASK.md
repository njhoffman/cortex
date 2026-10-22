# Task checklist

Current approved update: add visual sync feedback and release `v0.2.0`.

## Visual sync feedback — complete

- [x] Add structured progress events for source refresh, filtering, and publication.
- [x] Add an animated gradient bar, live source statuses, elapsed time, and colored summaries.
- [x] Preserve plain output for pipes, JSON, `NO_COLOR`, and dumb terminals.
- [x] Verify completed-source ordering, progress accounting, terminal cleanup, and CLI output modes.
- [x] Preview the dashboard in a PTY and verify an offline real-corpus sync.
- [x] Update documentation and changelog; bump to `0.2.0`.
- [x] Run `just check`, build, commit, tag, push, and verify the GitHub release.

Validation: 90 offline tests, including 16 terminal/progress tests; full-corpus PTY sync retained the same 15,141 examples for 1,722 commands, restored the cursor, and kept stdout free of ANSI codes. JSON and noninteractive/color-disabled modes remain plain. Short split panes use a compact layout.

## Phase 0 — complete

- [x] Read `OUTLINE.md` and establish Linux/installed-command scope.
- [x] Research GitHub and web cheatsheet collections.
- [x] Record original sources, formats, licenses, and priorities in `PLAN.md`.
- [x] Define the sync pipeline, storage, and acceptance criteria.

## Phase 1 — implementation

- [x] Choose Python 3.11+, TOML configuration, and the bashlex shell parser.
- [x] Create the package scaffold and versioned source registry.
- [x] Implement source adapters and preserve provenance/license metadata.
- [x] Implement Git/local source caching, change detection, and stale-cache recovery.
- [x] Implement Linux/shell filtering and installed-command dependency checks.
- [x] Implement deterministic deduplication, categorization, and personal overlays.
- [x] Publish complete catalog/Markdown snapshots atomically.
- [x] Expose `sync`, `--source`, `--offline`, `--force`, and JSON reporting.
- [x] Support `-v`/`--version` and `-h`/`--help` at the top level and for `sync`.
- [x] Add revision-pinned upstream fixtures and offline integration tests.
- [x] Run a real four-source sync and repeat/offline/availability checks.

## Project and release workflow

- [x] Establish initial SemVer version `0.1.0`.
- [x] Add `justfile` commands for setup, testing, linting, building, and releasing.
- [x] Add `CHANGELOG.md` and document the approved-update release procedure.
- [x] Add GitHub CI and tag-triggered builds/releases.
- [x] Connect the global Codex todo viewer through `TODO.md` and `just todo`.
- [x] Complete lint, tests, build, and installed-wheel smoke check.
- [x] Commit the Phase 1 implementation and create the annotated Git tag `v0.1.0`.
- [x] Push the initial commit and tag; verify GitHub CI.
- [x] Add a manual release-build retry path and publish patch version `v0.1.1`.
- [x] Verify the GitHub release build and wheel/source/checksum assets.

## Later phases — not started

- [ ] Phase 2: additional collection adapters and source inspection.
- [ ] Phase 3: local lookup and personal management commands.
- [ ] Phase 4: configurable display commands and zsh prompt integration.

## Validation record

- `just check`: 74 offline tests passed; lint, formatting, and release versions agree.
- `just build`: source archive and wheel built for version `0.1.0`.
- Installed-wheel smoke: version, bundled registry, first sync, and offline rebuild passed outside the checkout.
- Four-source smoke: 37,534 extracted examples; 15,141 retained for 1,722 available commands on the development machine.
- Forced offline rebuild: catalog, combined Markdown, and command inventory bytes remained identical.
- The global Codex todo renderer and `just todo` read this file through the `TODO.md` link.
