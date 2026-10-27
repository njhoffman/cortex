# Cortex

Cortex refreshes command cheatsheets from several collections and merges Linux-compatible examples for commands available on your machine into one offline catalog.

Requires Linux, Python 3.11+, and Git. It syncs the catalog and supports offline lookup, fzf/tmux display, and personal edits; a zsh widget is planned.

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
uv run cortex search extract archive
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

## Lookup and personal changes

These commands read the active snapshot and never use the network:

```sh
cortex list [--category archives]        # commands with example counts
cortex show tar                          # every tar example, with short IDs
cortex show git commit --origins         # one subcommand, plus sources and licenses
cortex search extract archive            # every term must match; command names rank first
```

`show` and `search` accept `--json`. Templates are printed without styling so they can be copied. `search` returns up to 50 examples (`--limit N`) and exits `1` when nothing matches.

### Display modes

`list`, `show`, and `search` take `--display MODE`, which overrides `[display] mode`:

| Mode | Behavior |
| --- | --- |
| `stdout` | Print the results, piped through `highlighter` (bat) when stdout is a terminal. |
| `fzf` | Pick an example in fzf with a highlighted preview. The raw command is printed; Esc prints nothing and exits `130`. |
| `fzf-split`, `fzf-popup` | The same, in a tmux split (`fzf-tmux` when installed) or a tmux popup. |
| `split` | Open the results in a tmux pane through `pager` (`less -R`), leaving focus on your prompt. Later lookups reuse that pane. |
| `popup` | Open the results in a tmux popup. |

With fzf modes, `list` offers every example (or every example in `--category`). The first time a split opens, cortex binds `M-{` (tmux root table) to close the cheatsheet pane and prints the matching `tmux.conf` line to keep it. If `M-{` is already bound to something else, cortex leaves it alone. Without tmux, the tmux modes fall back to `fzf` or `stdout`, and fzf modes fall back to `stdout` when fzf is missing.

```toml
[display]
mode = "stdout"
highlighter = ["bat", "--plain", "--language=sh", "--color=always"]  # [] disables it
pager = ["less", "-R"]
split_args = ["-h", "-l", "40%"]          # tmux split-window options
popup_args = ["-w", "80%", "-h", "80%"]   # tmux display-popup options
fzf_args = []
```

Configs created before 0.5.0 have a `highlighter` without `--color=always`, so bat output is uncolored in panes and fzf previews; add the flag to get colors there.

```sh
cortex add "tar -tvf archive.tar | less" -d "Page through an archive listing"
cortex remove 6d66139bc8                 # an ID prefix from `show` (6+ characters)
cortex remove --command 7z               # every example for a command
cortex restore                           # list remembered removals
cortex restore 6d66139bc8                # or: cortex restore --command 7z
```

`add` checks the command with the same shell parser sync uses and appends it to `custom/<command>.cheat`; earlier lines are never changed. It warns when the command is not installed, because sync will skip it. `remove` and `restore` rewrite the `ids` and `commands` arrays in `exclusions.toml`, keeping comment lines at the top of the file. Removing a custom example hides it the same way; the custom file is left alone. Each change runs an offline rebuild; pass `--no-sync` to batch several changes, then run `cortex sync --offline`. Removed examples are kept in each snapshot's `excluded.jsonl`.

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
