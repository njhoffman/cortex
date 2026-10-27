"""Offline lookup against the active catalog snapshot."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from cortex.config import Config
from cortex.model import CortexError, Example
from cortex.progress import style

SHORT_ID = 10
MINIMUM_PREFIX = 6


@dataclass
class Snapshot:
    path: Path
    examples: list[Example]
    excluded: list[Example]


def read_examples(path: Path) -> list[Example]:
    if not path.exists():
        return []
    try:
        return [Example.from_dict(json.loads(line)) for line in path.read_text().splitlines()]
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        raise CortexError(f"Cannot read {path}: {exc}") from exc


def load_snapshot(config: Config) -> Snapshot:
    link = config.paths.data / "current"
    if not link.exists():
        raise CortexError("No catalog has been published yet; run `cortex sync` first.")
    # Resolve once so every file in this operation comes from the same snapshot.
    path = link.resolve()
    return Snapshot(
        path, read_examples(path / "catalog.jsonl"), read_examples(path / "excluded.jsonl")
    )


def find_by_id(prefix: str, examples: list[Example]) -> Example:
    prefix = prefix.lower()
    if len(prefix) < MINIMUM_PREFIX or any(c not in "0123456789abcdef" for c in prefix):
        raise CortexError(
            f"Example IDs are hexadecimal with at least {MINIMUM_PREFIX} characters; "
            "use --command NAME for a whole command."
        )
    matches = [example for example in examples if example.id.startswith(prefix)]
    if not matches:
        raise CortexError(f"No example with ID {prefix}.")
    if len(matches) > 1:
        candidates = ", ".join(f"{item.id[:SHORT_ID]} ({item.command})" for item in matches[:5])
        raise CortexError(f"ID {prefix} is ambiguous: {candidates}")
    return matches[0]


def commands(examples: list[Example], category: str | None = None) -> list[dict]:
    groups: dict[str, list[Example]] = defaultdict(list)
    for example in examples:
        groups[example.command].append(example)
    rows = []
    for name, items in sorted(groups.items()):
        categories = sorted({item.category for item in items})
        if category and category not in categories:
            continue
        rows.append({"command": name, "categories": categories, "examples": len(items)})
    return rows


def show(examples: list[Example], command: str, subcommand: str | None = None) -> list[Example]:
    return [
        example
        for example in examples
        if example.command == command and (not subcommand or example.subcommand == subcommand)
    ]


def score(example: Example, terms: list[str]) -> int:
    """Rank one example; every term must match somewhere, command names weigh most.

    Each term scores its strongest match, plus a small bonus when it also names
    the category, so "extract archive" prefers archive tools.
    """
    total = 0
    command = example.command.lower()
    for term in terms:
        best = max(
            50 * (term == command),
            30 * command.startswith(term),
            20 * (term in example.subcommand.lower().split()),
            10 * (term in example.description.lower()),
            5 * (term in example.template.lower()),
        )
        bonus = 3 * (term in example.category)
        if not best and not bonus:
            return 0
        total += best + bonus
    return total


def search(examples: list[Example], query: list[str], limit: int) -> list[Example]:
    terms = [term.lower() for term in " ".join(query).split()]
    if not terms:
        raise CortexError("Search needs at least one term.")
    ranked = [(score(example, terms), example) for example in examples]
    ranked = [item for item in ranked if item[0]]
    ranked.sort(key=lambda item: (-item[0], item[1].command, item[1].template))
    return [example for _, example in ranked[:limit]]


def command_table(rows: list[dict], *, colored: bool) -> str:
    if not rows:
        return "No commands."
    width = max(len(row["command"]) for row in rows)
    count = max(len(str(row["examples"])) for row in rows)
    return "\n".join(
        f"{row['command'].ljust(width)}  {str(row['examples']).rjust(count)}  "
        + style(", ".join(row["categories"]), "dim", colored)
        for row in rows
    )


def render(examples: list[Example], *, colored: bool, origins: bool = False) -> str:
    """Group by command in first-seen order; templates stay unstyled for copying."""
    groups: dict[str, list[Example]] = {}
    for example in examples:
        groups.setdefault(example.command, []).append(example)
    output = []
    for name, items in groups.items():
        if output:
            output.append("")
        categories = ", ".join(sorted({item.category for item in items}))
        output.append(style(name, "accent", colored) + "  " + style(categories, "dim", colored))
        for example in items:
            output.append(
                "  "
                + style(f"# {example.description}", "success", colored)
                + "  "
                + style(f"[{example.id[:SHORT_ID]}]", "dim", colored)
            )
            output += [f"  {line}" for line in example.template.splitlines()]
            if origins:
                for origin in example.origins:
                    output.append(
                        style(
                            f"    from {origin.source} {origin.path}:{origin.line}"
                            f" ({origin.license}, {origin.revision[:12]})",
                            "dim",
                            colored,
                        )
                    )
    return "\n".join(output)
