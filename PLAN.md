# Cortex roadmap

Turn the requirements in [OUTLINE.md](OUTLINE.md) into a Linux command cheatsheet collection that can be refreshed with `cortex sync` and queried locally afterward. Build the source cache and consolidation pipeline first; add interactive lookup after its output is reliable.

Status: Phases 0 and 1 implemented. Phase 2 has the eg, cheatsheets.zip, Devhints, and awesome-cheatsheets adapters and `cortex sources`; Devhints has no upstream content license and stays disabled. The bounded HTTP transport is deferred until a website-only source is needed. Phase 3 lookup (`list`, `show`, `search`, with alias fallback) and personal management (`add`, `remove`, `restore`) are implemented. Phase 4 display modes and tmux split behavior are implemented; styled width-aware output and the zsh widget remain. The live checklist and release progress are in [TASK.md](TASK.md).

## 1. Resources to fetch

Research date: 2026-10-22. These are content sources found through GitHub and web searches. Prefer their original repositories over rendered websites, and retain the upstream URL, revision, file path, and license with imported examples. Priorities describe implementation order; inclusion in this list does not enable a source automatically.

### Initial sources

| ID | Collection and fetch location | Content to ingest | Format and license | Priority |
| --- | --- | --- | --- | --- |
| `tldr` | [tldr-pages/tldr](https://github.com/tldr-pages/tldr) | English `pages/common/*.md` and `pages/linux/*.md`; combine relevant examples from both. Do not also import language-directory aliases of the same pages. | Markdown with description/example pairs; [CC BY 4.0 content](https://github.com/tldr-pages/tldr/blob/main/LICENSE.md). | 1: default |
| `cheat` | [cheat/cheatsheets](https://github.com/cheat/cheatsheets) | Extensionless, command-named files at the repository root; exclude project metadata, editor configuration, and non-Linux topics. | Commented shell examples, sometimes with YAML front matter; [CC0 1.0](https://github.com/cheat/cheatsheets/blob/master/.github/LICENSE.txt). | 1: default |
| `navi` | [denisidoro/cheats](https://github.com/denisidoro/cheats) | Linux-compatible `**/*.cheat` recipes, selected by content rather than importing every platform/category indiscriminately. | Navi tags, descriptions, command templates, and variable definitions; [CC0 1.0](https://github.com/denisidoro/cheats/blob/master/LICENSE). | 1: default |
| `cheat-sheets` | [chubin/cheat.sheets](https://github.com/chubin/cheat.sheets) | Command sheets under `sheets/`; omit programming-language namespaces such as `_python` and unrelated topics. | Plain-text comment/example blocks; [MIT](https://github.com/chubin/cheat.sheets/blob/master/LICENSE). | 1: default |

### Additional collections and websites

| ID | Collection, website, and fetch location | Content to ingest | Format and license | Priority |
| --- | --- | --- | --- | --- |
| `eg` | [srsudar/eg](https://github.com/srsudar/eg), specifically [eg/examples](https://github.com/srsudar/eg/tree/master/eg/examples) | `eg/examples/*.md`; use its alias metadata where applicable and exclude examples specific to other operating systems. | Markdown examples; [MIT](https://github.com/srsudar/eg/blob/master/LICENSE.txt). | 2 |
| `devhints` | [devhints.io](https://devhints.io/) → [rstacruz/cheatsheets](https://github.com/rstacruz/cheatsheets) | Explicitly selected command pages such as `curl.md`, `grep.md`, `sed.md`, `ssh.md`, `git.md`, and `docker.md`. Shell-language reference pages need separate treatment. | Markdown with front matter, tables, and code blocks. Content license was not established from the inspected README and repository overview; record it as unresolved. | 2: adapter and license investigation |
| `cheatsheets-zip` | [cheatsheets.zip](https://cheatsheets.zip/) → [Fechin/reference](https://github.com/Fechin/reference) | Selected `source/_posts/*.md` command pages, including grep, find, sed, awk, curl, chmod, SSH, and lsof. | Markdown with front matter, tables, and code blocks; [GPL-3.0](https://github.com/Fechin/reference/blob/main/LICENSE). | 2 |
| `awesome-cheatsheets` | [LeCoupa/awesome-cheatsheets](https://github.com/LeCoupa/awesome-cheatsheets) | Selected CLI material under `tools/`, plus standalone command recipes from [languages/bash.sh](https://github.com/LeCoupa/awesome-cheatsheets/blob/master/languages/bash.sh). Exclude language lessons, editor keystrokes, and macOS sections. | Mixed commented scripts and Markdown; [MIT](https://github.com/LeCoupa/awesome-cheatsheets/blob/master/LICENSE). | 3: opt-in |
| `linux-command` | [Linux Command website](https://jaywcjlove.github.io/linux-command/) → [jaywcjlove/linux-command](https://github.com/jaywcjlove/linux-command) | `command/*.md`; examples rather than full manual text. Descriptions are primarily Chinese. | Markdown; repository declares [MIT](https://github.com/jaywcjlove/linux-command/blob/master/LICENSE), with original-author notices in its README. Preserve per-file attribution. | 3: opt-in, separate language |

Fetch and parser notes:

- [Tealdeer](https://github.com/tealdeer-rs/tealdeer) is a tldr client. Import the tldr corpus once; tealdeer is not another independent content source.
- [Navi](https://github.com/denisidoro/navi) is the client; `denisidoro/cheats` is the initial content source. Its [featured repository list](https://github.com/denisidoro/cheats/blob/master/featured_repos.txt) can supply future candidates, each added explicitly to Cortex configuration. Avoid importing generated tldr mirrors as extra sources.
- [cheat.sh / cht.sh](https://github.com/chubin/cheat.sh) already aggregates other collections. Fetch its original `chubin/cheat.sheets` content and other upstreams directly. Keep a future HTTP adapter for explicit command lookups, such as `https://cht.sh/tar?T`, disabled by default; do not crawl programming-language queries or duplicate the entire aggregate service.
- Devhints and cheatsheets.zip each count as one source even though both a repository and a website exist. Use Git by default. Add an HTML adapter only when a useful configured source lacks original files.
- [Navi syntax documentation](https://github.com/denisidoro/navi/tree/master/docs/cheatsheet/syntax) and [tldr's page specification](https://github.com/tldr-pages/tldr/blob/main/contributing-guides/style-guide.md) are parser references, not extra datasets.
- A website adapter must use configured URLs and selectors, conditional requests, and bounded request rates. It must distinguish complete shell examples from flag tables, regular-expression syntax, terminal output, and navigation text. For example, [the grep sheet](https://cheatsheets.zip/grep) contains both complete commands and syntax-only tables.
- Store licenses and attribution beside the generated collection, including an indication that formatting was transformed. Resolve the missing Devhints content-license metadata before treating it as a default redistributable source. Keep source content licensing separate from Cortex's own code license.

## 2. Scope and first usable milestone

The first release should provide a working `cortex sync` that refreshes every enabled source, normalizes its Linux command examples, filters them against commands available on this machine, removes exact redundancies, and publishes one central collection. Everything required for later queries is stored locally.

Interpret “Linux commands” as Linux-compatible terminal commands, including cross-platform programs such as git, ffmpeg, curl, and docker when installed. Import Linux and compatible common examples; exclude macOS/BSD-only variants, Windows/PowerShell examples, programming-language lessons, GUI shortcuts, and configuration fragments. The presence of `sed` alone does not establish that a BSD-specific `sed` example is compatible with Linux.

Interpret “available” as an executable resolvable through the invoking process's `PATH`, or a builtin supported by the configured shell. Availability is checked again on every sync, even when upstream content has not changed. This checks command presence, not argument validity, installed feature versions, privileges, running services, or container/remote-host software.

Search, fzf, tmux presentation, custom editing commands, and the zsh widget follow the sync milestone. Their storage needs should be accounted for now.

## 3. Source registry and local storage

Ship a versioned source manifest in the project, then let user configuration enable, disable, add, or override sources by stable ID. Each source specifies its URL, transport (`git`, `http`, or `local`), adapter, include/exclude paths, language, platform rules, priority, and license metadata. Resolve a repository's default branch on first fetch unless a ref is configured; record the actual commit used.

Use these paths, honoring the corresponding XDG environment variables:

```text
~/.config/cortex/config.toml              # settings and source overrides
~/.cache/cortex/sources/<source-id>/      # raw upstream snapshots and fetch metadata
~/.cache/cortex/parsed/<source-id>/       # normalized records before availability filtering
~/.local/share/cortex/custom/            # user-owned additions; never regenerated
~/.local/share/cortex/exclusions.toml     # remembered removals; never regenerated
~/.local/share/cortex/snapshots/<id>/     # complete generated collection
~/.local/share/cortex/current            # symlink to the active snapshot
```

Create a starter config only when absent. Keep user settings and personal additions outside the disposable cache. A clean cache can always be recreated from configured sources; losing the cache must not lose custom additions or removals.

Each generated snapshot contains:

```text
catalog.jsonl          # canonical structured examples, ready for later queries
commands.json          # sorted command names with retained examples and counts
commands/<name>.md     # one merged cheatsheet per command
commands.md            # single combined Markdown collection
manifest.json          # schema version, source revisions, availability context, counts
ATTRIBUTION.md         # source URLs, notices, licenses, and transformation notes
licenses/              # preserved upstream license texts
```

Expose stable paths through `current`, for example `~/.local/share/cortex/current/commands.md`. Query code resolves `current` once per operation so all files come from the same snapshot. Encode command filenames safely; do not use arbitrary upstream names as filesystem paths.

Keep the inventory of all discovered source commands in cache metadata, including commands not installed locally. Only the published snapshot is filtered to available commands. Installing a previously missing program can then reveal its cached examples on the next sync.

## 4. `cortex sync` behavior

Proposed interface:

```sh
cortex sync                     # refresh every enabled source and rebuild
cortex sync --source tldr       # refresh one source; merge with other enabled caches
cortex sync --offline           # rebuild from cached sources without network access
cortex sync --force             # bypass fetch/reparse shortcuts
```

For `--source`, do not silently omit enabled sources without a cache: report them as missing and return partial-success status. `--force` does not remove personal data or enable disabled sources.

Processing order:

1. Load/validate configuration, create missing directories, and acquire a sync lock. Queries may continue reading the active snapshot.
2. Refresh all enabled sources with bounded concurrency and per-source timeouts. On initial Git fetch, obtain a shallow snapshot; on later runs fetch updates without merging user changes. Use process argument arrays, not shell-interpolated commands. HTTP fetches use ETag/Last-Modified when supported and content hashes otherwise.
3. Stage each download separately and validate it before replacing that source's last usable cache. Record revision or HTTP validators, content checksum, fetch/check timestamps, parser version, and status. A changed include rule, parser, or configuration invalidates the corresponding parsed cache even if upstream is unchanged.
4. Extract Linux-compatible examples with source-specific adapters. Record malformed/unsupported entries and reasons. Treat an unexpectedly empty or structurally invalid source as a source failure rather than deleting all of its previously valid content.
5. Merge persistent custom examples, apply platform/shell rules, and resolve executable dependencies against current local availability. Keep rejected entries and explanations in diagnostics outside the published catalog.
6. Deduplicate, assign function categories, apply persistent exclusions, and sort deterministically. Rebuild generated output from current inputs so successful upstream deletions and disabled sources disappear.
7. Write and validate a complete new snapshot on the same filesystem as `current`. Atomically replace the active symlink only after the snapshot is complete. Keep the previous snapshot for recovery; an interrupted run leaves the active collection usable.
8. Print a compact per-source report and totals: updated, unchanged, stale, failed, parsed, unsupported, unavailable, duplicate, excluded, and retained. Send progress/diagnostics to stderr; keep machine-readable output available for later automation.

Failure policy:

- A source refresh or parse failure retains its last usable content and marks its revision stale in the new manifest. Never treat a failed fetch as upstream deletion.
- A failing new source with no cache is reported as unavailable; other sources can still produce a collection.
- Exit `0` when all requested sources succeed or are unchanged; `2` for a published collection with source failures/missing caches; `1` for fatal configuration, lock, build, or publication errors. If every requested online refresh fails, retain the active snapshot and return `1`; `--offline` explicitly permits rebuilding usable caches without refreshes.
- A fully successful offline rebuild returns `0` and records that freshness was not checked. Missing enabled caches yield `2`. If no usable inputs exist, return `1` without publishing an empty replacement. A valid input set filtered to zero installed commands may publish an explicitly reported empty collection.
- Identical content, parser/configuration, custom data, exclusions, and availability yield identical catalog and Markdown bytes. Refresh timestamps may differ in metadata.

## 5. Normalization and availability rules

Use one normalized example record independent of source format:

| Field | Purpose |
| --- | --- |
| `schema_version`, `id` | Version the format and give equivalent command templates a stable identity. |
| `command`, `subcommand` | Real executable/builtin name and optional argument sequence, e.g. `git` and `commit`. |
| `description` | One readable comment line describing the operation. |
| `template`, `placeholders` | Command text with quoting, pipes, and variable meaning preserved. |
| `required_commands` | All statically identifiable executable dependencies in the recipe. |
| `platforms`, `shell`, `language` | Compatibility and language metadata. |
| `category`, `tags` | Function-based grouping and searchable source tags. |
| `origins` | Every contributing source ID, URL, revision, original path/location, license, and original description/template. |

Rendered Markdown groups examples under command and category headings. Each recipe has exactly one descriptive `#` line immediately above its command, matching the outline:

```sh
# Save a 128 by 128 video frame at a chosen timestamp:
ffmpeg -ss <timestamp> -i <video> -frames:v 1 -vf scale=128:128 <image.png>
```

Normalization must preserve behavior. Collapse multiline descriptions into one comment. Remove syntax wrappers and actual prompt markers, while preserving shell `$` expansions. Join backslash continuations only when semantics are unchanged; retain genuine multiline recipes as one record with one description. Do not flatten heredocs or scripts into invalid one-liners.

Treat placeholders as template data. Support tldr `{{...}}` placeholders, optional flag alternatives, and navi `<...>` variables without confusing them with shell redirects or literal braces. Preserve ambiguous constructs for review or skip them with a reason. Never execute a recipe, source a downloaded file, or run a navi variable-generation expression during import or query.

Availability handling:

- Resolve literal executables with executable-file checks against `PATH`; preserve real hyphenated names such as `apt-get`. Use source metadata and parsed examples to map topic filenames such as `git-commit` to `git commit`, rather than splitting every hyphen.
- Recognize a documented set of builtins for the configured shell, including commands such as `cd` that may have no external binary. Do not source interactive shell startup files to discover availability. User aliases/functions need explicit metadata or later shell integration.
- Parse simple invocations, assignments, supported wrappers such as `sudo`/`env`/`command`, pipelines, and compound commands structurally. All required local executables must exist: `sudo missing-tool` and `cat file | missing-tool` are excluded even when `sudo` or `cat` exists.
- Include dependencies in command/process substitutions when statically parseable. Commands inside quoted awk/sed programs are program text, not separate shell executables. Dynamic command names, opaque `sh -c` strings, remote payloads, and unsupported syntax are skipped with diagnostics in the initial implementation.
- A recipe that requires a shell dialect different from the configured shell is excluded unless it explicitly invokes that shell and its dependencies can be resolved. Local command presence does not imply support for another platform's flags.
- Prioritize correctness over extraction volume. A source adapter supplies platform evidence and exclusions; unknown platform-specific examples are not assumed Linux-compatible just because an executable name matches.

Deduplicate only demonstrably equivalent command templates within the same compatibility context. Initially normalize surrounding whitespace and safe continuations; preserve quoted whitespace, option order, literal values, and meaningful argument differences. Merge all provenance for exact matches. Source priority selects the displayed description, with custom descriptions first. Similar-looking recipes remain separate until equivalence can be established.

Assign categories with a small editable mapping: files, text processing, archives, networking, processes, system/services, storage, packages, permissions/security, development, containers, media, shell, and other. Use command/subcommand rules plus source tags; unknown commands go to `other`. No network service or language model is needed to build the catalog.

## 6. Configuration and personal changes

Proposed configuration shape, with the complete source registry shipped separately:

```toml
[general]
platform = "linux"
language = "en"
shell = "zsh"
only_available = true

[sync]
concurrency = 4
timeout_seconds = 30

[display]
mode = "stdout"               # later: fzf or tmux
highlighter = ["bat", "--plain", "--language=sh"]

[sources.tldr]
enabled = true

[sources.cheat]
enabled = true

[sources.navi]
enabled = true

[sources.cheat-sheets]
enabled = true

[sources.devhints]
enabled = false

[sources.cheatsheets-zip]
enabled = false               # enable after its adapter is implemented
```

Keep display options in configuration now, but implement them after sync. CLI display switches override config; absent optional display tools fall back to stdout.

Custom additions use the canonical comment/template format with optional metadata and live in `custom/`. Sync reads them without rewriting their files. Remember removals in `exclusions.toml` using stable template IDs and optional whole-command rules. Apply exclusions after cross-source deduplication so another upstream cannot reintroduce the same removed example. Description/source changes do not change an example's ID; materially changed command text is a new example. Add a later restore operation for intentional reversals.

## 7. Delivery sequence

### Phase 0 — source research and roadmap

- Read the outline and identify its Linux-only, installed-command requirement.
- Search GitHub and the web for usable collections, including the named websites.
- Separate clients/aggregators from original content and document formats, paths, licenses, and priorities.
- Define sync behavior, output layout, and acceptance criteria in this plan.

### Phase 1 — registry, adapters, and first complete sync

- Use Python 3.11+, standard-library TOML and source-specific text adapters, and bashlex for structural shell inspection. Keep transport, adapters, normalization, and rendering separate.
- Create the CLI scaffold, source manifest, TOML configuration, XDG paths, and sync lock.
- Collect small, revision-pinned fixtures for the four initial sources, including attribution and expected extraction results.
- Implement Git fetch/cache refresh, per-source metadata, stale-cache recovery, and `--source`, `--offline`, and `--force` semantics.
- Implement tldr, cheat, navi, and cheat.sheets adapters. Verify placeholder handling and shell dependency parsing before accepting compound recipes.
- Implement Linux/shell filtering, local availability checks, stable IDs, exact deduplication, categories, and deterministic rendering.
- Publish the structured catalog, merged per-command files, combined Markdown, and attribution as an atomic snapshot.
- Read custom files and exclusions during assembly, even before management commands exist.

Acceptance: one `cortex sync` refreshes all four default sources and produces one consolidated collection containing only supported Linux recipes whose local command dependencies are available. A second unchanged sync preserves catalog/Markdown bytes, while a changed `PATH` or installed-command set updates eligibility.

### Phase 2 — expand collection coverage

- Add the eg Markdown adapter and alias handling.
- Add explicit command-page allowlists and table/code-block extraction for cheatsheets.zip and Devhints; complete the missing Devhints license metadata.
- Add opt-in adapters for selected awesome-cheatsheets material and a separate Chinese-language linux-command collection.
- Support configured local repositories/directories and bounded HTTP sources when needed.
- Add source status/listing output with revision, freshness, counts, and rejection reasons.

Acceptance: enabling any implemented source includes it in the same sync/merge process; unsupported adapter names produce a clear configuration error. Disabling a source removes only its contributions on the next successful rebuild. No generic web crawling is needed.

### Phase 3 — local lookup and personal management

- Add `cortex list`, `cortex show <command>`, and `cortex search <query>` against the active local catalog.
- Search command/subcommand names, descriptions, templates, and categories, with exact command matches first.
- Add `add`, `remove`, and `restore` operations that update persistent custom data/exclusions and rebuild locally.
- Offer structured query output and origin/license inspection.

Acceptance: lookup works with network access disabled; additions and remembered removals survive upstream updates, duplicate imports, and cache recreation.

### Phase 4 — terminal presentation and zsh integration

- Implement stdout, fzf, and tmux display modes with CLI overrides, aligned output, colors, and bat highlighting.
- Honor terminal width and no-color/non-TTY output; preserve raw command text separately from colored presentation.
- Add a zsh widget that reads the prompt buffer, finds its command context, and opens the relevant local lookup.
- Insert an fzf selection into the prompt buffer for editing, preserving placeholders and quoting. Do not execute it automatically; cancel leaves the prompt unchanged.

Acceptance: optional display integrations degrade to stdout, and selection reliably replaces the intended prompt text without running the selected recipe.

## 8. Verification for the sync milestone

Use focused fixture and integration tests with temporary config/cache/data directories and a controlled `PATH`. Routine tests run offline; live upstream smoke checks are separate.

| Scenario | Required result |
| --- | --- |
| First run; second unchanged run; remote revision changes | Initial import, cache reuse, then updated examples; repeatable catalog bytes. |
| Program installed/removed with unchanged upstream files | Next sync adds/removes its examples through availability filtering. |
| Linux/common versus macOS/Windows examples | Only compatible Linux examples are published, even when executable names overlap. |
| `apt-get`, `git commit`, builtin `cd`, assignment/wrapper/pipeline | Correct executable mapping and dependency checks; a missing downstream executable excludes the whole recipe. |
| tldr placeholders, flag alternatives, navi variables, quoted strings, continuations | Meaning preserved; no placeholder evaluation, variable generator, or recipe execution. |
| Exact duplicate across sources; similar recipe with different arguments | One record with multiple origins for the duplicate; distinct recipes remain separate. |
| Upstream deletion, disabled source, source timeout, invalid response | Valid deletions/disablement remove contributions; failures retain last usable contributions and report stale state. |
| One source fails; every online refresh fails; offline cache missing | Defined partial/fatal exit status, accurate report, and no accidental empty replacement. |
| Interrupted build, concurrent sync, query during publication | Active snapshot stays complete; locking prevents concurrent writers. |
| Custom recipe and persistent exclusion across refresh/cache rebuild | Custom file remains untouched; excluded duplicate stays removed. |
| No installed matching commands; malformed upstream entry | Explicit empty-result report when legitimate; malformed entries diagnosed rather than silently misparsed. |

The first implementation task is Phase 1: turn the four default source entries into a versioned registry and fixture-backed adapters, then complete `cortex sync` end to end before adding interactive UI.
