"""Source-specific extraction. Downloaded files are always treated as data."""

from __future__ import annotations

import re
from pathlib import Path

from cortex.config import Source
from cortex.model import Diagnostic, Example, Origin, Parsed

FOREIGN = re.compile(
    r"\b(?:macos|mac os(?: x)?|osx|darwin|windows|powershell|freebsd|openbsd|netbsd)\b", re.I
)
FOREIGN_PATH = re.compile(
    r"(?:^|[/_.-])(?:osx|macos|darwin|windows|powershell|bsd)(?:[/_.-]|$)", re.I
)
PLACEHOLDER = re.compile(r"\{\{([^{}\n]+)\}\}|(?<![<\w])<([A-Za-z_][\w .:/-]*)>(?!>)")


def platform_reason(path: str, text: str, tags: list[str]) -> str | None:
    if FOREIGN_PATH.search(path) or FOREIGN.search(" ".join(tags)):
        return "non-Linux platform metadata"
    if FOREIGN.search(text):
        return "non-Linux or mixed platform description"
    return None


def normalize_template(text: str) -> str:
    # Strip actual prompts, not parameter expansions. Leave command internals intact.
    lines = text.strip().splitlines()
    return "\n".join(re.sub(r"^\s*\$ ", "", line) for line in lines).strip()


def make_example(
    source: Source,
    revision: str,
    path: str,
    line: int,
    description: str,
    template: str,
    tags: list[str],
    parsed: Parsed,
) -> None:
    description = " ".join(description.strip(" #:>-\t").split())
    template = normalize_template(template)
    reason = platform_reason(path, description, tags)
    if reason or not template or not description:
        parsed.diagnostics.append(
            Diagnostic(source.id, path, line, reason or "missing description or command")
        )
        return
    # Markdown metadata, output, and flag-only fragments are not commands.
    if template.startswith(("%", "---", "```", "- ")):
        parsed.diagnostics.append(Diagnostic(source.id, path, line, "non-command fragment"))
        return
    origin = Origin(
        source.id, source.url, revision, path, line, source.license, description, template
    )
    placeholders = sorted({a or b for a, b in PLACEHOLDER.findall(template)})
    example = Example(
        description,
        template,
        [origin],
        sorted(set(tags)),
        source.shell,
        source.language,
        source.platforms,
        placeholders,
    )
    example.identify()
    parsed.examples.append(example)


def tldr(text: str, source: Source, revision: str, path: str, parsed: Parsed) -> None:
    description = ""
    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith("- "):
            description = line[2:].rstrip(":")
        elif line.startswith("`") and line.endswith("`") and description:
            make_example(source, revision, path, number, description, line[1:-1], [], parsed)
            description = ""


def commented(text: str, source: Source, revision: str, path: str, parsed: Parsed) -> None:
    lines = text.splitlines()
    description: list[str] = []
    pending: list[str] = []
    tags: list[str] = []
    start = 0
    front = False
    variable = False
    section_forbidden = False
    after_command = False

    def flush() -> None:
        nonlocal pending
        if pending:
            if section_forbidden:
                parsed.diagnostics.append(Diagnostic(source.id, path, start, "non-Linux section"))
            else:
                make_example(
                    source,
                    revision,
                    path,
                    start,
                    " ".join(description),
                    "\n".join(pending),
                    tags,
                    parsed,
                )
            pending = []

    for number, line in enumerate(lines, 1):
        stripped = line.strip()
        if number == 1 and stripped == "---":
            front = True
            continue
        if front:
            if stripped == "---":
                front = False
            elif stripped.startswith("tags:"):
                tags.extend(re.findall(r"[\w-]+", stripped.split(":", 1)[1]))
            continue
        if not stripped:
            # A blank after a continuation belongs to its command, not a new recipe.
            flush()
            variable = False
            continue
        if source.adapter == "navi" and stripped.startswith(("$ ", "; ")):
            flush()
            variable = True
            continue
        if variable:
            continue
        if stripped.startswith("%"):
            flush()
            tags = [tag.strip() for tag in stripped[1:].split(",") if tag.strip()]
            description = []
            section_forbidden = bool(FOREIGN.search(" ".join(tags)))
            continue
        if stripped.startswith("#"):
            flush()
            comment = stripped.lstrip("# ")
            if after_command:
                description = []
            after_command = False
            # Standalone platform headings set scope until another platform heading.
            if re.fullmatch(
                r"(?:for )?(?:macos|mac os x|osx|windows|linux)(?: only)?[:.]?", comment, re.I
            ):
                section_forbidden = "linux" not in comment.lower()
                description = []
            else:
                description.append(comment)
            continue
        # A continuation is a single recipe; ordinary consecutive invocations are
        # separate examples sharing their preceding description.
        if pending and not pending[-1].rstrip().endswith("\\"):
            flush()
        if not pending:
            start = number
        pending.append(line)
        after_command = True
    flush()


def selected_files(root: Path, source: Source) -> list[Path]:
    candidates: set[Path] = set()
    for pattern in source.include:
        candidates.update(root.glob(pattern))
    selected = []
    for path in sorted(candidates):
        if (
            not path.is_file()
            or path.is_symlink()
            or not path.resolve().is_relative_to(root.resolve())
        ):
            continue
        relative = path.relative_to(root)
        if any(relative.match(pattern) for pattern in source.exclude):
            continue
        if ".git" in relative.parts:
            continue
        if source.adapter in {"cheat", "cheat-sheets"} and path.suffix:
            continue
        selected.append(path)
    return selected


def parse(root: Path, source: Source, revision: str) -> Parsed:
    parsed = Parsed()
    for path in selected_files(root, source):
        relative = path.relative_to(root).as_posix()
        try:
            if path.stat().st_size > 2_000_000:
                raise ValueError("file exceeds 2 MB parsing limit")
            text = path.read_text(encoding="utf-8")
            if "\x00" in text:
                raise ValueError("binary file")
        except (OSError, UnicodeError, ValueError) as exc:
            parsed.diagnostics.append(Diagnostic(source.id, relative, 0, str(exc)))
            continue
        parsed.files += 1
        if source.adapter == "tldr":
            tldr(text, source, revision, relative, parsed)
        else:
            commented(text, source, revision, relative, parsed)
    return parsed
