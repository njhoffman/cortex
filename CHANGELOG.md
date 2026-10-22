# Changelog

All approved updates are versioned with SemVer and annotated GitHub tags. New features increment the minor version; compatible fixes and maintenance increment the patch version. Interfaces remain under development before 1.0.0.

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
