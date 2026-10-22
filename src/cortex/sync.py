"""Assemble a deterministic installed-command catalog and publish it atomically."""

from __future__ import annotations

import copy
import fcntl
import json
import os
import re
import shutil
import tempfile
import uuid
from collections import Counter, defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from urllib.parse import quote

from cortex import __version__
from cortex.adapters import parse
from cortex.cache import SourceCache, SourceResult, atomic_text, now
from cortex.config import Config, Source, read_toml
from cortex.model import SCHEMA_VERSION, CortexError, Diagnostic, Example, json_text
from cortex.shell import Availability

CATEGORIES = {
    "files": "ls cp mv rm find locate fd mkdir rmdir touch ln readlink realpath tree basename dirname file du df stat pwd cd",
    "text": "cat less more head tail grep rg ag awk sed cut sort uniq tr wc tee paste join comm diff cmp strings column",
    "archives": "tar zip unzip gzip gunzip bzip2 xz 7z zstd",
    "networking": "curl wget ssh scp sftp rsync ip ss netstat ping dig host nslookup nc ncat telnet traceroute mtr tcpdump",
    "processes": "ps top htop btop kill pkill pgrep killall nice renice nohup timeout time watch jobs bg fg wait",
    "system": "systemctl journalctl service dmesg uname hostname uptime date timedatectl loginctl sysctl shutdown reboot lscpu lsusb lspci",
    "storage": "lsblk blkid mount umount fdisk parted mkfs fsck dd free swapon swapoff sync",
    "packages": "apt apt-get apt-cache dpkg dnf yum rpm pacman apk snap flatpak pip pip3 uv cargo npm",
    "security": "chmod chown chgrp umask sudo su id whoami groups passwd gpg openssl chattr lsattr getfacl setfacl",
    "development": "git gh make just gcc clang cc cmake ninja python python3 node go rustc jq yq patch",
    "containers": "docker podman kubectl helm minikube kind compose",
    "media": "ffmpeg ffprobe convert magick identify sox mpv yt-dlp",
    "shell": "echo printf read export alias unalias set unset command type hash source bash zsh sh true false test",
}
COMMAND_CATEGORY = {
    command: category for category, commands in CATEGORIES.items() for command in commands.split()
}


@contextmanager
def sync_lock(data: Path):
    data.mkdir(parents=True, exist_ok=True)
    with (data / ".sync.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise CortexError("Another sync is already running for this data directory.") from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def read_exclusions(path: Path) -> tuple[set[str], set[str]]:
    raw = read_toml(path) if path.exists() else {}
    for key in raw:
        if key not in {"ids", "commands"}:
            raise CortexError(f"Unknown exclusions key: {key}")
    for key in ("ids", "commands"):
        if not isinstance(raw.get(key, []), list) or not all(
            isinstance(item, str) for item in raw.get(key, [])
        ):
            raise CortexError(f"exclusions.{key} must be an array of strings")
    return set(raw.get("ids", [])), set(raw.get("commands", []))


def personal(config: Config) -> SourceResult:
    directory = config.paths.data / "custom"
    directory.mkdir(parents=True, exist_ok=True)
    source = Source(
        "custom",
        str(directory),
        "custom",
        transport="local",
        include=["**/*.cheat", "**/*.md"],
        license="personal",
        priority=0,
        language=config.language,
    )
    parsed = parse(directory, source, "local")
    return SourceResult(source, "local", "local", parsed.examples, parsed.diagnostics)


def assemble(config: Config, results: list[SourceResult]) -> tuple[list[Example], dict, list, dict]:
    availability = Availability(config.shell)
    excluded_ids, excluded_commands = read_exclusions(config.paths.data / "exclusions.toml")
    unique: dict[str, Example] = {}
    counts = Counter(
        parsed=0,
        extraction_rejected=0,
        unsupported=0,
        unavailable=0,
        duplicate=0,
        excluded=0,
        retained=0,
    )
    diagnostics = []
    inventories: dict[str, set[str]] = defaultdict(set)
    for result in results:
        diagnostics.extend(asdict(item) for item in result.diagnostics)
        counts["extraction_rejected"] += len(result.diagnostics)
        for raw in result.examples:
            counts["parsed"] += 1
            example = copy.deepcopy(raw)
            origin = example.origins[0]
            if "linux" not in example.platforms or example.language != config.language:
                reason = "platform or language does not match configuration"
            else:
                reason = availability.apply(example)
            if example.command:
                inventories[result.source.id].add(example.command)
            if reason:
                counts["unavailable" if reason.startswith("unavailable:") else "unsupported"] += 1
                diagnostics.append(
                    asdict(Diagnostic(origin.source, origin.path, origin.line, reason))
                )
                continue
            example.category = config.categories.get(
                f"{example.command} {example.subcommand}".strip(),
                config.categories.get(
                    example.command, COMMAND_CATEGORY.get(example.command, "other")
                ),
            )
            if example.id in unique:
                previous = unique[example.id]
                previous.origins.extend(example.origins)
                previous.tags = sorted(set(previous.tags) | set(example.tags))
                counts["duplicate"] += 1
            else:
                unique[example.id] = example
    catalog = []
    for example in unique.values():
        if example.id in excluded_ids or example.command in excluded_commands:
            counts["excluded"] += 1
            continue
        example.origins.sort(key=lambda origin: (origin.source, origin.path, origin.line))
        catalog.append(example)
    catalog.sort(key=lambda item: (item.command, item.category, item.template, item.id))
    counts["retained"] = len(catalog)
    return (
        catalog,
        dict(counts),
        diagnostics,
        {key: sorted(value) for key, value in sorted(inventories.items())},
    )


def fenced(text: str) -> str:
    longest = max((len(match.group()) for match in re.finditer(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}sh\n{text}\n{fence}\n"


def markdown(command: str, examples: list[Example], level: int = 1) -> str:
    output = [f"{'#' * level} {command}\n"]
    category = None
    for example in examples:
        if category != example.category:
            category = example.category
            output.append(f"\n{'#' * (level + 1)} {category}\n")
        output.append("\n" + fenced(f"# {example.description}\n{example.template}"))
    return "".join(output)


def publish(
    config: Config, catalog: list[Example], report: dict, results: list[SourceResult]
) -> Path:
    root = config.paths.data / "snapshots"
    root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".staging-", dir=root))
    link = config.paths.data / f".current-{uuid.uuid4().hex}"
    try:
        commands = temporary / "commands"
        commands.mkdir()
        groups: dict[str, list[Example]] = defaultdict(list)
        for example in catalog:
            groups[example.command].append(example)
        (temporary / "catalog.jsonl").write_text(
            "".join(
                json.dumps(example.to_dict(), ensure_ascii=False, sort_keys=True) + "\n"
                for example in catalog
            )
        )
        (temporary / "commands.json").write_text(
            json_text(
                [
                    {
                        "command": command,
                        "examples": len(examples),
                        "file": f"commands/{quote(command, safe='')}.md",
                    }
                    for command, examples in sorted(groups.items())
                ]
            )
        )
        combined = ["# Cortex command collection\n"]
        for command, examples in sorted(groups.items()):
            (commands / f"{quote(command, safe='')}.md").write_text(markdown(command, examples))
            combined.append("\n" + markdown(command, examples, level=2))
        (temporary / "commands.md").write_text("".join(combined))
        (temporary / "manifest.json").write_text(
            json_text(
                {
                    "schema_version": SCHEMA_VERSION,
                    "cortex_version": __version__,
                    "created_at": now(),
                    "platform": "linux",
                    "shell": config.shell,
                    "language": config.language,
                    "path": os.environ.get("PATH", ""),
                    **report,
                }
            )
        )
        attribution = [
            "# Attribution\n\nExamples were extracted, filtered, and reformatted by Cortex. "
            "Original text and source locations are preserved in catalog.jsonl. "
            "Content retains its upstream license.\n"
        ]
        for result in results:
            if not result.examples and not result.licenses:
                continue
            source = result.source
            attribution.append(
                f"\n## {source.id}\n\nSource: {source.url}\n\n"
                f"Revision: `{result.revision}`\n\nLicense: {source.license}\n"
            )
            for name, content in sorted(result.licenses.items()):
                file = temporary / "licenses" / source.id / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(content)
        (temporary / "ATTRIBUTION.md").write_text("".join(attribution))
        (temporary / "licenses").mkdir(exist_ok=True)
        # Read back the machine-readable artifacts before changing the active pointer.
        rows = [json.loads(line) for line in (temporary / "catalog.jsonl").read_text().splitlines()]
        if len(rows) != len(catalog) or any(not row["required_commands"] for row in rows):
            raise CortexError("Generated catalog failed validation.")
        json.loads((temporary / "commands.json").read_text())
        destination = root / uuid.uuid4().hex
        temporary.rename(destination)
        link.symlink_to(destination.relative_to(config.paths.data), target_is_directory=True)
        os.replace(link, config.paths.data / "current")
        return destination
    finally:
        link.unlink(missing_ok=True)
        if temporary.exists():
            shutil.rmtree(temporary)


def run(
    config: Config,
    *,
    source_ids: list[str] | None = None,
    offline: bool = False,
    force: bool = False,
    progress: Callable[[str], None] | None = None,
) -> tuple[int, dict]:
    sources = [source for source in config.sources if source.enabled]
    if source_ids:
        unknown = set(source_ids) - {source.id for source in sources}
        if unknown:
            raise CortexError("Unknown or disabled source(s): " + ", ".join(sorted(unknown)))
    with sync_lock(config.paths.data):
        config.paths.cache.mkdir(parents=True, exist_ok=True)
        if progress:
            progress(
                f"{'Reading cached' if offline else 'Refreshing'} sources: "
                + ", ".join(source.id for source in sources)
            )

        def refresh(source: Source) -> SourceResult:
            return SourceCache(config, source).refresh(
                offline=offline,
                selected=not source_ids or source.id in source_ids,
                force=force,
            )

        with ThreadPoolExecutor(max_workers=config.concurrency) as pool:
            results = list(pool.map(refresh, sources))
        requested = [
            result for result in results if not source_ids or result.source.id in source_ids
        ]
        report = {
            "offline": offline,
            "sources": [result.report() for result in results],
            "published": False,
        }
        if requested and not offline and all(result.failed for result in requested):
            report["error"] = "Every requested source refresh failed; active snapshot retained."
            atomic_text(config.paths.cache / "last-sync.json", json_text(report))
            return 1, report
        custom = personal(config)
        inputs = [custom, *results]
        if not any(result.examples for result in inputs):
            report["error"] = "No usable inputs; active snapshot retained."
            atomic_text(config.paths.cache / "last-sync.json", json_text(report))
            return 1, report
        if progress:
            progress("Filtering local command dependencies and assembling the collection…")
        catalog, counts, diagnostics, inventories = assemble(config, inputs)
        report["counts"] = counts
        report["commands"] = len({example.command for example in catalog})
        atomic_text(config.paths.cache / "diagnostics.json", json_text(diagnostics))
        atomic_text(config.paths.cache / "source-inventory.json", json_text(inventories))
        report["published"] = True
        destination = publish(config, catalog, report, inputs)
        report["snapshot"] = str(destination)
        atomic_text(config.paths.cache / "last-sync.json", json_text(report))
        return (2 if any(result.failed for result in results) else 0), report
