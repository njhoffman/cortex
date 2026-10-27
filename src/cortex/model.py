"""Serializable records shared by adapters, filtering, and rendering."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = 1
PARSER_VERSION = 2


class CortexError(Exception):
    """An actionable configuration, source, or publication error."""


@dataclass
class Origin:
    source: str
    url: str
    revision: str
    path: str
    line: int
    license: str
    description: str
    template: str


@dataclass
class Example:
    description: str
    template: str
    origins: list[Origin]
    tags: list[str] = field(default_factory=list)
    shell: str = "posix"
    language: str = "en"
    platforms: list[str] = field(default_factory=lambda: ["linux"])
    placeholders: list[str] = field(default_factory=list)
    command: str = ""
    subcommand: str = ""
    required_commands: list[str] = field(default_factory=list)
    category: str = "other"
    id: str = ""
    schema_version: int = SCHEMA_VERSION

    def identify(self) -> None:
        # Descriptions, origin revisions, and source priority do not affect identity.
        value = [self.template.strip(), self.shell, self.language, sorted(self.platforms)]
        self.id = hashlib.sha256(json.dumps(value, ensure_ascii=False).encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Example:
        data = dict(value)
        data["origins"] = [Origin(**origin) for origin in data["origins"]]
        return cls(**data)


@dataclass
class Diagnostic:
    source: str
    path: str
    line: int
    reason: str


@dataclass
class Parsed:
    examples: list[Example] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    files: int = 0


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
