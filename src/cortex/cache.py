"""Per-source last-good caches and bounded Git/local transports."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from cortex.adapters import parse, selected_files
from cortex.config import Config, Source
from cortex.model import PARSER_VERSION, CortexError, Diagnostic, Example, json_text


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp.write_text(text)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


@dataclass
class SourceResult:
    source: Source
    status: str
    revision: str = ""
    examples: list[Example] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    licenses: dict[str, str] = field(default_factory=dict)
    message: str = ""
    failed: bool = False
    checked_at: str = ""

    def report(self) -> dict:
        return {
            "id": self.source.id,
            "status": self.status,
            "revision": self.revision,
            "parsed": len(self.examples),
            "rejected": len(self.diagnostics),
            "message": self.message,
            "failed": self.failed,
            "checked_at": self.checked_at,
        }


class SourceCache:
    def __init__(self, config: Config, source: Source):
        self.config, self.source = config, source
        self.directory = config.paths.cache / "sources" / source.id
        self.pointer = self.directory / "current.json"
        self.fingerprint = hashlib.sha256(
            json_text(
                {
                    "source": source.fingerprint_data(),
                    "parser_version": PARSER_VERSION,
                }
            ).encode()
        ).hexdigest()

    def git(self, *args: str, stdout=None) -> subprocess.CompletedProcess:
        git = shutil.which("git")
        if not git:
            raise CortexError("Git is required to refresh repository sources.")
        env = os.environ | {"GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1"}
        try:
            result = subprocess.run(
                [git, "-c", "core.hooksPath=/dev/null", *args],
                stdout=stdout if stdout is not None else subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.config.timeout,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise CortexError(f"Git timed out after {self.config.timeout}s") from exc
        if result.returncode:
            raise CortexError(result.stderr.decode(errors="replace").strip())
        return result

    def load(self) -> tuple[dict, SourceResult] | None:
        if not self.pointer.exists():
            return None
        try:
            meta = json.loads(self.pointer.read_text())
            if meta["url"] != self.source.url or meta["ref"] != self.source.ref:
                return None
            relative = Path(meta["parsed"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("unsafe parsed-cache path")
            data = json.loads((self.config.paths.cache / relative).read_text())
            result = SourceResult(
                self.source,
                "cached",
                meta["revision"],
                [Example.from_dict(item) for item in data["examples"]],
                [Diagnostic(**item) for item in data["diagnostics"]],
                data["licenses"],
                checked_at=meta.get("checked_at", ""),
            )
            return meta, result
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise CortexError(f"Corrupt {self.source.id} cache; run sync --force: {exc}") from exc

    def refresh(
        self, *, offline: bool = False, selected: bool = True, force: bool = False
    ) -> SourceResult:
        loaded = None
        try:
            try:
                loaded = self.load()
            except CortexError:
                if offline or not selected:
                    raise
            if offline or not selected:
                if loaded is None:
                    return SourceResult(
                        self.source, "missing", message="no usable cached source", failed=True
                    )
                meta, result = loaded
                if not force and meta["fingerprint"] == self.fingerprint:
                    result.status = "offline" if offline else "cached"
                    return result
                revision = meta["revision"]
            else:
                self.directory.mkdir(parents=True, exist_ok=True)
                if self.source.transport == "git":
                    repo = self.directory / "repo.git"
                    if not repo.exists():
                        self.git("init", "--bare", str(repo))
                    self.git(
                        "--git-dir",
                        str(repo),
                        "fetch",
                        "--no-tags",
                        "--depth=1",
                        "--",
                        self.source.url,
                        self.source.ref or "HEAD",
                    )
                    revision = (
                        self.git("--git-dir", str(repo), "rev-parse", "FETCH_HEAD^{commit}")
                        .stdout.decode()
                        .strip()
                    )
                else:
                    revision = ""  # computed from the staged local content below
                if (
                    loaded
                    and not force
                    and revision
                    and (
                        loaded[0]["fingerprint"] == self.fingerprint
                        and loaded[0]["revision"] == revision
                    )
                ):
                    meta, result = loaded
                    result.status, result.checked_at = "unchanged", now()
                    meta["checked_at"] = result.checked_at
                    atomic_text(self.pointer, json_text(meta))
                    return result

            self.directory.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="staging-", dir=self.directory) as temporary:
                staging = Path(temporary)
                tree = staging / "tree"
                tree.mkdir()
                if self.source.transport == "git":
                    archive = staging / "source.tar"
                    with archive.open("wb") as handle:
                        self.git(
                            "--git-dir",
                            str(self.directory / "repo.git"),
                            "archive",
                            "--format=tar",
                            revision,
                            stdout=handle,
                        )
                    self.extract(archive, tree)
                elif offline or not selected:
                    relative_tree = Path(loaded[0]["tree"])
                    if relative_tree.is_absolute() or ".." in relative_tree.parts:
                        raise CortexError("unsafe source-cache tree path")
                    previous_tree = self.directory / relative_tree
                    shutil.copytree(previous_tree, tree, dirs_exist_ok=True)
                else:
                    local = Path(self.source.url).expanduser()
                    if not local.is_absolute() or not local.is_dir():
                        raise CortexError("local source url must be an existing absolute directory")
                    for file in selected_files(local, self.source):
                        target = tree / file.relative_to(local)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(file, target)
                    for name in self.source.license_files:
                        file = local / name
                        if (
                            file.is_file()
                            and not file.is_symlink()
                            and file.resolve().is_relative_to(local.resolve())
                        ):
                            target = tree / name
                            target.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copyfile(file, target)
                    digest = hashlib.sha256()
                    for file in sorted(p for p in tree.rglob("*") if p.is_file()):
                        digest.update(file.relative_to(tree).as_posix().encode() + b"\0")
                        digest.update(file.read_bytes())
                    revision = digest.hexdigest()
                parsed = parse(tree, self.source, revision)
                if not parsed.files or not parsed.examples:
                    raise CortexError(
                        "source produced no described examples; last usable cache retained"
                    )
                licenses = {}
                for name in self.source.license_files:
                    file = tree / name
                    if not file.is_file():
                        raise CortexError(f"source is missing declared license file {name}")
                    licenses[name] = file.read_text()
                snapshot_id = uuid.uuid4().hex
                destination = self.directory / "snapshots" / snapshot_id
                destination.parent.mkdir(parents=True, exist_ok=True)
                tree.rename(destination)
                checked_at = now() if not offline and selected else loaded[0].get("checked_at", "")
                parsed_path = (
                    self.config.paths.cache / "parsed" / self.source.id / f"{snapshot_id}.json"
                )
                atomic_text(
                    parsed_path,
                    json_text(
                        {
                            "examples": [example.to_dict() for example in parsed.examples],
                            "diagnostics": [asdict(item) for item in parsed.diagnostics],
                            "licenses": licenses,
                            "parser_version": PARSER_VERSION,
                        }
                    ),
                )
                status = "updated"
                if offline or not selected:
                    status = "offline" if offline else "cached"
                elif loaded and loaded[0]["revision"] == revision:
                    status = "unchanged"
                atomic_text(
                    self.pointer,
                    json_text(
                        {
                            "url": self.source.url,
                            "ref": self.source.ref,
                            "fingerprint": self.fingerprint,
                            "revision": revision,
                            "tree": destination.relative_to(self.directory).as_posix(),
                            "parsed": parsed_path.relative_to(self.config.paths.cache).as_posix(),
                            "checked_at": checked_at,
                        }
                    ),
                )
                return SourceResult(
                    self.source,
                    status,
                    revision,
                    parsed.examples,
                    parsed.diagnostics,
                    licenses,
                    checked_at=checked_at,
                )
        except (CortexError, OSError, ValueError, tarfile.TarError) as exc:
            if loaded:
                result = loaded[1]
                result.status, result.message, result.failed = "stale", str(exc), True
                return result
            return SourceResult(self.source, "failed", message=str(exc), failed=True)

    def extract(self, archive: Path, tree: Path) -> None:
        total = 0
        with tarfile.open(archive) as tar:
            for member in tar:
                path = PurePosixPath(member.name)
                if path.is_absolute() or ".." in path.parts or not member.isfile():
                    continue
                wanted = member.name in self.source.license_files or any(
                    path.match(pattern) for pattern in self.source.include
                )
                if not wanted or (
                    member.name not in self.source.license_files
                    and any(path.match(pattern) for pattern in self.source.exclude)
                ):
                    continue
                total += member.size
                if member.size > 2_000_000 or total > 200_000_000:
                    raise CortexError("source exceeds configured import size limits")
                target = tree / member.name
                target.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as reader, target.open("wb") as writer:
                    shutil.copyfileobj(reader, writer)
