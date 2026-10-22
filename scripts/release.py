"""Version preparation and the approved-update release procedure."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "pyproject.toml"
CHANGELOG = ROOT / "CHANGELOG.md"


def version() -> str:
    return tomllib.loads(VERSION_FILE.read_text())["project"]["version"]


def command(*args: str, capture: bool = False) -> str:
    result = subprocess.run(
        args, cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE if capture else None
    )
    return result.stdout.strip() if capture else ""


def verify(tag: str | None = None) -> None:
    current = version()
    if tag and tag != f"v{current}":
        raise ValueError(f"Tag {tag!r} does not match package version {current}.")
    if not re.search(
        rf"^## \[{re.escape(current)}\] - \d{{4}}-\d{{2}}-\d{{2}}$", CHANGELOG.read_text(), re.M
    ):
        raise ValueError(f"CHANGELOG.md is missing a dated {current} entry.")
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    package = next(row for row in lock["package"] if row["name"] == "cortex-cheatsheets")
    if package["version"] != current:
        raise ValueError("uv.lock package version differs; run uv lock.")
    print(f"Release versions agree: v{current}")


def notes() -> str:
    text = CHANGELOG.read_text()
    match = re.search(
        rf"^## \[{re.escape(version())}\][^\n]*\n(.*?)(?=^## |^\[\d|\Z)", text, re.M | re.S
    )
    if not match:
        raise ValueError("Current changelog entry was not found.")
    return match.group(1).strip() + "\n"


def bump(part: str, notes_file: Path) -> None:
    previous = version()
    components = [int(item) for item in previous.split(".")]
    index = {"major": 0, "minor": 1, "patch": 2}[part]
    components[index] += 1
    for offset in range(index + 1, 3):
        components[offset] = 0
    current = ".".join(map(str, components))
    release_notes = notes_file.read_text().strip()
    if not release_notes:
        raise ValueError("Release notes must not be empty.")
    changelog = CHANGELOG.read_text()
    heading = re.search(r"^## \[", changelog, re.M)
    if not heading:
        raise ValueError("Changelog has no release entries.")
    entry = f"## [{current}] - {date.today().isoformat()}\n\n{release_notes}\n\n"
    CHANGELOG.write_text(
        changelog[: heading.start()]
        + entry
        + changelog[heading.start() :]
        + f"\n[{current}]: https://github.com/njhoffman/cortex/releases/tag/v{current}\n"
    )
    VERSION_FILE.write_text(
        VERSION_FILE.read_text().replace(f'version = "{previous}"', f'version = "{current}"', 1)
    )
    print(f"Prepared {previous} → {current}; update uv.lock before release.")


def publish() -> None:
    verify()
    current = version()
    tag = f"v{current}"
    branch = command("git", "symbolic-ref", "--short", "HEAD", capture=True)
    if command("git", "tag", "--list", tag, capture=True):
        raise ValueError(f"{tag} already exists. For a failed push, push the existing commit/tag.")
    if command("git", "diff", "--name-only", capture=True):
        raise ValueError("Unstaged tracked changes exist; review and stage the approved update.")
    if command("git", "ls-files", "--others", "--exclude-standard", capture=True):
        raise ValueError("Untracked files exist; review and stage approved files before release.")
    if not command("git", "diff", "--cached", "--name-only", capture=True):
        raise ValueError("No approved changes are staged.")
    command("just", "check")
    command("just", "build")
    command("git", "commit", "-m", f"Release {tag}")
    command("git", "tag", "-a", tag, "-m", f"Cortex {tag}")
    command(
        "git",
        "push",
        "--atomic",
        "--set-upstream",
        "origin",
        f"HEAD:refs/heads/{branch}",
        f"refs/tags/{tag}",
    )


def main() -> int:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    verification = commands.add_parser("verify")
    verification.add_argument("--tag")
    preparation = commands.add_parser("bump")
    preparation.add_argument("part", choices=["major", "minor", "patch"])
    preparation.add_argument("--notes-file", type=Path, required=True)
    commands.add_parser("publish")
    commands.add_parser("notes")
    args = root.parse_args()
    try:
        if args.command == "verify":
            verify(args.tag)
        elif args.command == "bump":
            bump(args.part, args.notes_file)
        elif args.command == "notes":
            print(notes(), end="")
        else:
            publish()
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"release: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
