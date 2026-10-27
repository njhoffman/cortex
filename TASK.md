# Task checklist

Current approved update: Claude context and Phase 2-4 checklist, released as `v0.2.1`.

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

## Phase 2 — collection coverage (not started)

See `PLAN.md` section 7, Phase 2. Acceptance: enabling any implemented source joins the same sync/merge; disabling removes only its contributions.

- [ ] **eg adapter.** (p2) [feature] Parse `srsudar/eg` `eg/examples/*.md` with alias metadata.
  Registry entry `sources.eg` exists but is disabled; `config.ADAPTERS` lacks `eg`, so enabling it is a config error.
  Exclude examples for other operating systems; add revision-pinned fixtures under `tests/fixtures/eg/`.
- [ ] **cheatsheets.zip adapter.** (p2) [feature] Allowlisted `source/_posts/*.md` pages with table/code-block extraction.
  Must separate complete shell examples from flag tables, regex syntax, and terminal output (e.g. the grep page).
  Registry entry `sources.cheatsheets-zip` is disabled; GPL-3.0 attribution goes in `ATTRIBUTION.md`.
- [ ] **Devhints adapter and license.** (p2) [feature] Adapter for `rstacruz/cheatsheets` command pages; resolve content license.
  `sources.toml` records `license = "unresolved"` with no include list. Keep it non-default until licensing is established.
- [ ] **Source status command.** (p2) [feature] List sources with revision, freshness, counts, and rejection reasons.
  Data is already in cache metadata and per-source diagnostics; expose it via a `cortex sources` (or `sync --status`) command with `--json`.
- [ ] **awesome-cheatsheets adapter.** (p3) [feature] Opt-in adapter for selected `tools/` material and `languages/bash.sh` recipes.
  Exclude language lessons, editor keystrokes, and macOS sections. Needs a registry entry.
- [ ] **linux-command collection.** (p3) [feature] Opt-in, Chinese-language `jaywcjlove/linux-command` `command/*.md` source.
  Separate `language`; preserve per-file author attribution. Needs a registry entry and language filtering in merge.
- [ ] **Bounded HTTP transport.** (p3) [feature] Configured-URL HTTP fetches with ETag/Last-Modified and rate limits.
  Only for sources lacking original files; also enables an opt-in, disabled-by-default cht.sh single-command lookup.

## Phase 3 — local lookup and personal management (not started)

Acceptance: lookup works offline; additions and remembered removals survive upstream updates and cache recreation.

- [ ] **list/show/search commands.** (p2) [feature] `cortex list`, `cortex show <command>`, `cortex search <query>` on the active catalog.
  Resolve `current` once per operation; search names, subcommands, descriptions, templates, categories; exact command matches first.
- [ ] **add/remove/restore commands.** (p2) [feature] Edit `custom/` and `exclusions.toml`, then rebuild offline.
  `restore` reverses a remembered exclusion by ID or command; never rewrite existing user files destructively.
- [ ] **Origin and license inspection.** (p3) [feature] Structured (`--json`) query output plus per-example origin/license display.

## Phase 4 — terminal presentation and zsh integration (not started)

Acceptance: optional integrations degrade to stdout; a selection replaces prompt text without running it.

- [ ] **Display modes.** (p2) [feature] stdout, fzf, fzf-tmux split/popup, tmux split/popup from `[display] mode` with CLI overrides.
  `[display]` is already written to the starter config by `config.py` but nothing reads it yet. OUTLINE suggests a command-string mode.
- [ ] **tmux split behavior.** (p2) [feature] Keep focus on the prompt pane; bind `M-{` to close the cheatsheet pane.
- [ ] **Styled output.** (p2) [feature] Aligned, colored output with `bat` highlighting; honor width, `NO_COLOR`, non-TTY.
  Keep raw command text separate from presentation; fall back when `bat` is missing.
- [ ] **zsh widget.** (p2) [feature] Read `$BUFFER`, find the command context, open lookup, insert fzf selection.
  Preserve placeholders and quoting; never execute; cancel leaves the prompt unchanged. Ship as a sourceable script.
- [ ] **Non-bash cheatsheets.** (p3) [feature] Eventually support content beyond shell commands (OUTLINE end note).

## Validation record

- `just check`: 74 offline tests passed; lint, formatting, and release versions agree.
- `just build`: source archive and wheel built for version `0.1.0`.
- Installed-wheel smoke: version, bundled registry, first sync, and offline rebuild passed outside the checkout.
- Four-source smoke: 37,534 extracted examples; 15,141 retained for 1,722 available commands on the development machine.
- Forced offline rebuild: catalog, combined Markdown, and command inventory bytes remained identical.
- The global Codex todo renderer and `just todo` read this file through the `TODO.md` link.
