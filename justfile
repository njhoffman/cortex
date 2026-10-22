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

# Refresh the actual user collection; pass --offline to use cached sources.
sync *args:
    uv run --locked cortex sync {{args}}

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
