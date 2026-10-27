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
uv run cortex sources
uv run cortex sources tldr
uv run cortex --version
uv run cortex -v
uv run cortex -h
uv run cortex sync --help
```

`sync` refreshes tldr, cheat, navi, cheat.sh's original cheatsheet repository, and eg by default. It never runs imported commands or navi variable generators. Failed sources retain their last usable cache; publishing replaces the active collection atomically. Every sync rechecks command availability, including offline syncs.

In a terminal, sync shows an animated purple-to-cyan-to-green progress bar, live source statuses, checked-example and written-file counts, and elapsed time. Updated or unchanged sources appear green, stale caches amber, and failed sources red. The bar reaches 100% after the new catalog is published.

```sh
just sync                      # animated dashboard in a terminal
just sync --color always       # force colors, including when output is captured
just sync --color never        # plain stage/status messages
```

Redirected output uses plain stage/status messages automatically. `NO_COLOR` and `TERM=dumb` suppress colors and animation; `--json` always keeps both output streams free of ANSI codes. Progress remains on stderr, and the final summary or JSON report goes to stdout.

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

Use `cortex --config /path/to/config.toml sync` for another config. Enabling an adapter that does not exist reports a configuration error.

Two more sources ship disabled and can be enabled with `enabled = true`:

- `cheatsheets-zip`: an allowlist of command pages from [cheatsheets.zip](https://cheatsheets.zip/) (GPL-3.0).
- `devhints`: command-line pages from [devhints.io](https://devhints.io/). Upstream declares no content license, so sync prints a warning while it is enabled; keep its examples to personal use.

For these Markdown sources Cortex reads shell code blocks and command/description tables. It skips flag-only lines, command output after `$ ` prompts, and sections headed for other platforms.

`cortex sources` lists every configured source with its license, last sync status, revision, check time, and parsed, rejected, and kept example counts. `cortex sources <id>` adds rejection reasons, a sample location for each, and the most common missing commands. It reads only local files; `--json` prints the same data.

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
