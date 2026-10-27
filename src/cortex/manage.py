"""Personal additions and remembered removals."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

from cortex.cache import atomic_text
from cortex.config import Config
from cortex.model import CortexError
from cortex.shell import Availability, Unsupported, inspect
from cortex.sync import read_exclusions

HEADER = [
    "# Remembered removals. `cortex remove` and `cortex restore` rewrite the ids and",
    "# commands arrays; comment lines at the top of this file are kept.",
]


@dataclass
class Exclusions:
    path: Path
    header: list[str] = field(default_factory=list)
    ids: set[str] = field(default_factory=set)
    commands: set[str] = field(default_factory=set)

    @classmethod
    def read(cls, config: Config) -> Exclusions:
        path = config.paths.data / "exclusions.toml"
        ids, commands = read_exclusions(path)
        header = []
        if path.exists():
            for line in path.read_text().splitlines():
                if line.strip() and not line.lstrip().startswith("#"):
                    break
                header.append(line)
        while header and not header[-1].strip():
            header.pop()
        return cls(path, header or list(HEADER), ids, commands)

    def write(self) -> None:
        def array(name: str, values: set[str]) -> list[str]:
            # JSON strings are valid TOML basic strings.
            return [f"{name} = [", *(f"    {json.dumps(v)}," for v in sorted(values)), "]"]

        lines = [*self.header, "", *array("ids", self.ids), "", *array("commands", self.commands)]
        atomic_text(self.path, "\n".join(lines) + "\n")


def add(config: Config, template: str, description: str) -> tuple[Path, list[str]]:
    """Append one recipe to custom/<command>.cheat; return the file and missing commands."""
    template = template.strip()
    description = " ".join(description.split()).lstrip("# ")
    if not template or not description:
        raise CortexError("Both a command and a description are required.")
    lines = template.splitlines()
    if any(not line.rstrip().endswith("\\") for line in lines[:-1]):
        raise CortexError("Multiline commands must use backslash continuations.")
    try:
        result = inspect(template, config.shell)
    except Unsupported as exc:
        raise CortexError(f"Cannot add this command: {exc}") from exc
    availability = Availability(config.shell)
    missing = [name for name in result.required if not availability.has(name)]
    directory = config.paths.data / "custom"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{quote(result.command, safe='')}.cheat"
    existing = path.read_text() if path.exists() else ""
    separator = "" if not existing else ("\n" if existing.endswith("\n") else "\n\n")
    with path.open("a") as handle:
        handle.write(f"{separator}# {description}\n{template}\n")
    return path, missing
