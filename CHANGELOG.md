# Changelog

All approved updates are versioned with SemVer and annotated GitHub tags. New features increment the minor version; compatible fixes and maintenance increment the patch version. Interfaces remain under development before 1.0.0.

## [0.3.0] - 2026-10-27

### Added

- eg (`srsudar/eg`) source, enabled by default. Reads its indented examples, drops command output shown after `$ ` prompts, and skips macOS sections.
- Opt-in cheatsheets.zip source, covering 28 allowlisted command pages. Shell code blocks and command/description tables are imported.
- Opt-in Devhints source, covering 27 command-line pages. Upstream declares no content license, so it ships disabled and sync warns while it is enabled.
- `cortex sources [ID] [--json]` shows each source's license, last sync status, revision, check time, and parsed, rejected, and kept counts. With an ID it also lists rejection reasons and the most common missing commands. It works offline.
- Sync reports (`--json`) include a `warnings` list.

### Changed

- Lines that contain only flags (such as `-i  # --include`) are now rejected as "flag-only fragment" for every source. Before, they were dropped later as unavailable commands. The parser version changed, so the next sync re-parses cached sources once.

## [0.2.1] - 2026-10-27

### Added

- `CLAUDE.md` project context for Claude Code, importing the shared `AGENTS.md` workflow rules.

### Changed

- Broke the Phase 2-4 roadmap in `TASK.md` into prioritized, categorized checklist items.

## [0.2.0] - 2026-10-22

### Added

- Animated gradient progress dashboard for sync, with live source statuses, elapsed time, checked-example counts, and written-file counts.
- Colored success, stale-cache, and failure feedback, plus `--color auto|always|never`.

### Changed

- Report source completion immediately while preserving registry priority in the merged catalog.
- Keep redirected output, JSON reports, `NO_COLOR`, and dumb terminals free of terminal control codes.

## [0.1.1] - 2026-10-22

### Fixed

- Allow manual release builds against an exact version tag when GitHub does not schedule a tag event, and document retrying without moving published tags.

## [0.1.0] - 2026-10-22

### Added

- Phase 0 research of nine command cheatsheet collections, source priorities, and a phased roadmap.
- Phase 1 `cortex sync` with tldr, cheat, navi, and cheat.sh content adapters.
- Git and local source caching, offline rebuilds, selective refresh, force refresh, and stale-source recovery.
- Linux and shell compatibility filtering, installed-command dependency checks, exact deduplication, and functional categories.
- Structured catalogs, combined and per-command Markdown, source attribution, and atomic snapshots.
- Persistent custom additions and remembered example/command exclusions.
- TOML configuration, XDG paths, JSON reports, diagnostics, and source inventories.
- Offline fixture/integration tests, a `justfile`, Python wheel/source builds, and GitHub CI/tag releases.
- `TASK.md` for the active checklist and a documented approved-update release workflow.
- `TODO.md` compatibility link and `just todo` for the global Codex checklist viewer.

[0.1.0]: https://github.com/njhoffman/cortex/releases/tag/v0.1.0

[0.1.1]: https://github.com/njhoffman/cortex/releases/tag/v0.1.1

[0.2.0]: https://github.com/njhoffman/cortex/releases/tag/v0.2.0

[0.2.1]: https://github.com/njhoffman/cortex/releases/tag/v0.2.1

[0.3.0]: https://github.com/njhoffman/cortex/releases/tag/v0.3.0
