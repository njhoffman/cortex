set shell := ["bash", "-euo", "pipefail", "-c"]

# List available development commands.
default:
    @just --list

# Install the package and locked development dependencies.
setup:
    uv sync --locked

# Run offline unit and integration tests.
test *args:
    uv run --locked pytest {{args}}

# Check imports, basic correctness, and formatting.
lint:
    uv run --locked ruff check src tests scripts
    uv run --locked ruff format --check src tests scripts

# Apply formatting and safe import fixes.
fmt:
    uv run --locked ruff check --fix src tests scripts
    uv run --locked ruff format src tests scripts

# Run the release's local validation.
check: lint
    uv run --locked pytest
    uv run --locked python scripts/release.py verify

# Build the source distribution and wheel.
build:
    uv build

# Run any cortex command from this checkout, e.g. `just cortex show tar`.
[positional-arguments]
cortex *args:
    @uv run --locked cortex "$@"

# Refresh the actual user collection; pass --offline to use cached sources.
[positional-arguments]
sync *args:
    @uv run --locked cortex sync "$@"

# Configured sources and their last sync status; pass an ID for details.
[positional-arguments]
sources *args:
    @uv run --locked cortex sources "$@"

# Commands in the catalog with example counts.
[positional-arguments]
list *args:
    @uv run --locked cortex list "$@"

# A command's examples, e.g. `just show git commit --display split`.
[positional-arguments]
show command *args:
    @uv run --locked cortex show "$@"

# Search descriptions and templates, e.g. `just search extract archive`.
[positional-arguments]
search +terms:
    @uv run --locked cortex search "$@"

# Add a personal example, e.g. `just add 'du -sh *' 'Size of each entry'`.
[positional-arguments]
add template description:
    @uv run --locked cortex add "$1" --description "$2"

# Remember a removal by example ID, or `--command NAME`.
[positional-arguments]
remove +args:
    @uv run --locked cortex remove "$@"

# Undo a remembered removal; without arguments, list removals.
[positional-arguments]
restore *args:
    @uv run --locked cortex restore "$@"

# Put `cortex` on PATH as a uv tool that tracks this checkout's source.
install:
    uv tool install --editable --force .

# Remove the `cortex` uv tool.
uninstall:
    uv tool uninstall cortex-cheatsheets

# View the project checklist using the installed global Codex todo renderer.
todo:
    @if [[ -f "${CODEX_HOME:-$HOME/.codex}/skills/todo/scripts/show_todo.py" ]]; then python3 "${CODEX_HOME:-$HOME/.codex}/skills/todo/scripts/show_todo.py" --path TASK.md --color auto; else cat TASK.md; fi

# Prepare the next version and changelog from a Markdown notes file.
bump part notes_file:
    uv run --locked python scripts/release.py bump {{part}} --notes-file {{quote(notes_file)}}
    uv lock

# Validate, build, commit staged approved changes, tag, and atomically push.
release:
    uv run --locked python scripts/release.py publish
