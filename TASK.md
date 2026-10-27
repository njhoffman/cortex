# Task checklist

Current approved update: display modes and tmux split behavior, released as `v0.5.0`.

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

## Phase 2 — collection coverage (in progress)

See `PLAN.md` section 7, Phase 2. Acceptance: enabling any implemented source joins the same sync/merge; disabling removes only its contributions.

- [x] **eg adapter.** (p2) [feature] Parse `srsudar/eg` `eg/examples/*.md`; enabled by default.
  Indented blocks, `$ ` prompt output dropped, OSX sections skipped. `aliases.json` deferred to Phase 3 search.
- [x] **cheatsheets.zip adapter.** (p2) [feature] 28 allowlisted pages; shell fences plus command/description tables.
  Opt-in. Flag-only lines and syntax tables are skipped; real-corpus sync keeps 824 examples.
- [x] **Devhints adapter.** (p2) [feature] 27 allowlisted CLI pages, shared Markdown parser; disabled, `none-declared` license.
  Sync warns while it is enabled. Tests use synthetic Markdown, not upstream excerpts.
- [x] **Source status command.** (p2) [feature] `cortex sources [ID] [--json]`, offline, from caches and the catalog.
- [ ] **Devhints content license.** (p3) [chore] Ask `rstacruz/cheatsheets` to declare a content license.
  The repo has no LICENSE file and GitHub reports none, so Devhints stays disabled with a warning.
  If upstream adds one, update `license`/`license_files` in `src/cortex/sources.toml` and drop the warning case.
- [ ] **Markdown parser noise.** (p3) [refactor] Diagrams and keybinding tables in shell fences reach the availability filter.
  E.g. cheatsheets.zip `awk.md` box-drawing lines and `tmux.md`/`screen.md` key tables become "unsupported"/"unavailable"
  diagnostics instead of extraction rejections. Harmless to output, but it inflates the counts `cortex sources` shows.
- [x] **awesome-cheatsheets adapter.** (p3) [feature] Opt-in; 13 `tools/` sheets plus four `languages/bash.sh` sections.
  `command  # description` lines, per-file `sections` allowlists; real-corpus sync keeps 379 examples (295 unique).
- [ ] **linux-command collection.** (p3) [feature] Opt-in, Chinese-language `jaywcjlove/linux-command` `command/*.md` source.
  Separate `language`; preserve per-file author attribution. Needs a registry entry and language filtering in merge.
- [ ] **Bounded HTTP transport.** (p3) [feature] Configured-URL HTTP fetches with ETag/Last-Modified and rate limits.
  Deferred (2026-10-27): every registered source has a Git repository, and cht.sh mostly serves cheat.sheets and
  tldr, which are already imported. Build it when a useful source exists only as a website.

## Phase 3 — local lookup and personal management (complete)

Acceptance: lookup works offline; additions and remembered removals survive upstream updates and cache recreation.

- [x] **list/show/search commands.** (p2) [feature] `cortex list`, `show <command> [sub]`, `search <terms>`; offline, `--json`.
- [x] **add/remove/restore commands.** (p2) [feature] Append to `custom/`, rewrite `exclusions.toml` arrays, offline rebuild.
- [x] **Origin and license inspection.** (p3) [feature] `show`/`search --origins` and `--json`.
- [x] **eg aliases in lookup.** (p3) [feature] Snapshot `aliases.json` from eg's map and tldr "alias of" notes (326).
  `show netcat` falls back to `nc` with a note; commands with their own examples keep them and name the target.
- [x] **`.` builtin loses its command name.** (p2) [bug] `.` now counts as an opaque launcher, like `source`.

## Phase 4 — terminal presentation and zsh integration (not started)

Acceptance: optional integrations degrade to stdout; a selection replaces prompt text without running it.

- [x] **Display modes.** (p2) [feature] `--display` / `[display] mode`: stdout, fzf, fzf-split, fzf-popup, split, popup.
- [x] **tmux split behavior.** (p2) [feature] `split-window -d` keeps focus; one reused pane; runtime `M-{` close binding.
- [ ] **Styled output.** (p2) [feature] Width-aware alignment and wrapping for stdout and panes.
  bat highlighting on a terminal is done (0.5.0). Long descriptions still run past the terminal width;
  `cortex show tar` prints multi-hundred-character lines. Wrap descriptions to the width and keep templates unwrapped.
- [ ] **Popup modes untested live.** (p3) [test] `popup`/`fzf-popup` are covered only by fake-tmux tests.
  `display-popup` needs an attached client, so the detached-server check could not exercise it. Try both in a real session.
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
