# Cortex

Cortex refreshes command cheatsheets from several collections and merges Linux-compatible examples for commands available on your machine into one offline catalog.

Requires Linux, Python 3.11+, and Git. Interactive search and shell widgets are planned; this release implements the sync pipeline.

```sh
uv sync
uv run cortex sync
```

The generated collection is at `~/.local/share/cortex/current/commands.md`. Per-command Markdown and a structured `catalog.jsonl` sit alongside it. XDG configuration, cache, and data directory overrides are supported.

```sh
uv run cortex sync --offline
uv run cortex sync --source tldr
uv run cortex sync --force
uv run cortex sync --json
uv run cortex --version
uv run cortex -v
uv run cortex -h
uv run cortex sync --help
```

`sync` refreshes tldr, cheat, navi, and cheat.sh's original cheatsheet repository by default. It never runs imported commands or navi variable generators. Failed sources retain their last usable cache; publishing replaces the active collection atomically. Every sync rechecks command availability, including offline syncs.

The first run creates `~/.config/cortex/config.toml`. Source overrides extend the bundled [registry](src/cortex/sources.toml):

```toml
[general]
platform = "linux"
shell = "bash"                 # bash, zsh, or sh
language = "en"
only_available = true

[sources.navi]
enabled = false

# A local directory can use any implemented adapter.
[sources.personal]
url = "/absolute/path/to/cheatsheets"
transport = "local"
adapter = "cheat"
include = ["*"]
license = "personal"
```

Use `cortex --config /path/to/config.toml sync` for another config. Sources with adapters scheduled for later phases are disabled in the registry; enabling an unimplemented adapter reports a configuration error.

Put personal `.cheat` or `.md` files in `~/.local/share/cortex/custom/`, using a description comment followed by a shell command. These files are never rewritten:

```sh
# Find large files:
find . -type f -size +100M
```

Remember removals in `~/.local/share/cortex/exclusions.toml` with `ids = ["<catalog-example-id>"]` or `commands = ["find"]`. IDs remain stable across description and source changes. Custom additions still undergo Linux, shell, and availability filtering.

Exit status is `0` for success, `2` for a published collection with failed or missing sources, and `1` for a fatal error or an online refresh where every requested source fails. `--json` prints a structured report to stdout; progress goes to stderr. Per-entry rejection diagnostics are retained in the cache.

Availability means a literal executable on `PATH` or a documented builtin for the configured shell. It does not validate command options, services, privileges, or remote software. Unsupported dynamic shell constructs are skipped and reported; templates remain templates and can contain placeholders.

Development uses [just](https://just.systems/):

```sh
just setup
just check
just build
just sync --offline
just todo
```

`TASK.md` is the live project checklist. `TODO.md` links to it so the installed global Codex `/prompts:todo` command can find the same tasks.

See [PLAN.md](PLAN.md), [CHANGELOG.md](CHANGELOG.md), and [RELEASING.md](RELEASING.md) for scope and release procedures.
