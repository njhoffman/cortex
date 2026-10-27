"""Configuration, bundled registry, and XDG locations."""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import asdict, dataclass, field
from importlib.resources import files
from pathlib import Path
from typing import Any

from cortex.model import CortexError

ADAPTERS = {"tldr", "cheat", "navi", "cheat-sheets", "eg", "cheatsheets-zip", "devhints", "custom"}
STARTER = """# Cortex configuration. Relative source URLs are not supported; use absolute paths.
[general]
platform = "linux"
language = "en"
shell = "bash"
only_available = true

[sync]
concurrency = 4
timeout_seconds = 60

[display]
# stdout, fzf, fzf-split, fzf-popup, split, or popup; `--display` overrides it.
mode = "stdout"
highlighter = ["bat", "--plain", "--language=sh", "--color=always"]
# pager = ["less", "-R"]
# split_args = ["-h", "-l", "40%"]      # tmux split-window options
# popup_args = ["-w", "80%", "-h", "80%"]  # tmux display-popup options
# fzf_args = []

# Source overrides extend the bundled registry by ID.
# [sources.tldr]
# enabled = false
"""


@dataclass(frozen=True)
class Paths:
    config: Path
    cache: Path
    data: Path

    @classmethod
    def discover(cls, config: str | None = None) -> Paths:
        home = Path.home()
        return cls(
            Path(config).expanduser().resolve()
            if config
            else Path(os.environ.get("XDG_CONFIG_HOME", home / ".config")) / "cortex/config.toml",
            Path(os.environ.get("XDG_CACHE_HOME", home / ".cache")) / "cortex",
            Path(os.environ.get("XDG_DATA_HOME", home / ".local/share")) / "cortex",
        )


@dataclass
class Source:
    id: str
    url: str
    adapter: str
    enabled: bool = True
    transport: str = "git"
    ref: str = ""
    include: list[str] = field(default_factory=lambda: ["**/*"])
    exclude: list[str] = field(default_factory=list)
    license: str = "unresolved"
    license_files: list[str] = field(default_factory=list)
    priority: int = 100
    language: str = "en"
    platforms: list[str] = field(default_factory=lambda: ["linux"])
    shell: str = "posix"

    def fingerprint_data(self) -> dict[str, Any]:
        return asdict(self)


DISPLAY_MODES = ("stdout", "fzf", "fzf-split", "fzf-popup", "split", "popup")


@dataclass
class Display:
    mode: str = "stdout"
    highlighter: list[str] = field(
        default_factory=lambda: ["bat", "--plain", "--language=sh", "--color=always"]
    )
    pager: list[str] = field(default_factory=lambda: ["less", "-R"])
    split_args: list[str] = field(default_factory=lambda: ["-h", "-l", "40%"])
    popup_args: list[str] = field(default_factory=lambda: ["-w", "80%", "-h", "80%"])
    fzf_args: list[str] = field(default_factory=list)


@dataclass
class Config:
    paths: Paths
    sources: list[Source]
    shell: str = "bash"
    language: str = "en"
    concurrency: int = 4
    timeout: int = 60
    categories: dict[str, str] = field(default_factory=dict)
    display: Display = field(default_factory=Display)


def read_toml(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text())
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise CortexError(f"Cannot read {path}: {exc}") from exc


def load(paths: Paths) -> Config:
    try:
        paths.config.parent.mkdir(parents=True, exist_ok=True)
        try:
            with paths.config.open("x") as handle:
                handle.write(STARTER)
        except FileExistsError:
            pass
        raw = read_toml(paths.config)
        defaults = tomllib.loads(files("cortex").joinpath("sources.toml").read_text())
        general, sync = raw.get("general", {}), raw.get("sync", {})
        if general.get("platform", "linux") != "linux":
            raise CortexError("Only platform = 'linux' is supported.")
        if general.get("only_available", True) is not True:
            raise CortexError("Phase 1 requires only_available = true.")
        shell = general.get("shell", "bash")
        if shell not in {"bash", "zsh", "sh"}:
            raise CortexError("general.shell must be bash, zsh, or sh.")
        language = general.get("language", "en")
        if not isinstance(language, str) or not language:
            raise CortexError("general.language must be a nonempty string.")
        concurrency, timeout = sync.get("concurrency", 4), sync.get("timeout_seconds", 60)
        if type(concurrency) is not int or not 1 <= concurrency <= 32:
            raise CortexError("sync.concurrency must be an integer from 1 to 32.")
        if type(timeout) is not int or not 1 <= timeout <= 3600:
            raise CortexError("sync.timeout_seconds must be an integer from 1 to 3600.")
        merged = defaults["sources"]
        for key, override in raw.get("sources", {}).items():
            merged[key] = merged.get(key, {}) | override
        sources = []
        for key, entry in merged.items():
            if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", key):
                raise CortexError(f"Invalid source ID: {key!r}")
            source = Source(id=key, **entry)
            if type(source.enabled) is not bool:
                raise CortexError(f"{key}: enabled must be true or false.")
            if source.enabled:
                if source.adapter not in ADAPTERS:
                    raise CortexError(f"{key}: adapter {source.adapter!r} is not implemented yet.")
                if source.transport not in {"git", "local"}:
                    raise CortexError(f"{key}: transport must be git or local in Phase 1.")
                if not isinstance(source.url, str) or not source.url:
                    raise CortexError(f"{key}: url must be nonempty.")
                for name in ("include", "exclude", "license_files", "platforms"):
                    value = getattr(source, name)
                    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
                        raise CortexError(f"{key}: {name} must be an array of strings.")
                for pattern in source.include + source.exclude + source.license_files:
                    if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
                        raise CortexError(f"{key}: unsafe path pattern {pattern!r}")
                if type(source.priority) is not int:
                    raise CortexError(f"{key}: priority must be an integer.")
                if source.shell not in {"posix", "bash", "zsh", "sh"}:
                    raise CortexError(f"{key}: unsupported shell {source.shell!r}")
            sources.append(source)
        categories = raw.get("categories", {})
        if not isinstance(categories, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in categories.items()
        ):
            raise CortexError("categories must map command names to category strings.")
        display = Display(**raw.get("display", {}))
        if display.mode not in DISPLAY_MODES:
            raise CortexError("display.mode must be one of: " + ", ".join(DISPLAY_MODES))
        for name in ("highlighter", "pager", "split_args", "popup_args", "fzf_args"):
            value = getattr(display, name)
            if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
                raise CortexError(f"display.{name} must be an array of strings.")
        if not display.pager:
            raise CortexError("display.pager must name a command.")
        return Config(
            paths,
            sorted(sources, key=lambda s: (s.priority, s.id)),
            shell,
            language,
            concurrency,
            timeout,
            categories,
            display,
        )
    except (TypeError, AttributeError, ValueError) as exc:
        raise CortexError(f"Invalid configuration: {exc}") from exc
