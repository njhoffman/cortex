"""Source-specific extraction. Downloaded files are always treated as data."""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath

from cortex.config import Source
from cortex.model import Diagnostic, Example, Origin, Parsed

FOREIGN = re.compile(
    r"\b(?:macos|mac os(?: x)?|osx|darwin|windows|powershell|freebsd|openbsd|netbsd)\b", re.I
)
FOREIGN_PATH = re.compile(
    r"(?:^|[/_.-])(?:osx|macos|darwin|windows|powershell|bsd)(?:[/_.-]|$)", re.I
)
PLACEHOLDER = re.compile(r"\{\{([^{}\n]+)\}\}|(?<![<\w])<([A-Za-z_][\w .:/-]*)>(?!>)")
SHELL_FENCES = {"sh", "bash", "shell", "shell script", "shell-script", "console", "zsh"}
FENCE = re.compile(r"^\s*(`{3,}|~{3,})\s*([^`{]*?)\s*(?:\{.*\})?\s*$")
# Kramdown/Hexo attribute lists such as `{: .-prime}` or `{.cols-4}`.
ATTRIBUTES = re.compile(r"\s*\{[:.#][^}]*\}")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*$")
PROMPT = re.compile(r"^\s*\$ ")
COMMAND_COLUMNS = {"command", "commands", "example", "examples", "usage"}
DESCRIPTION_COLUMNS = {"description", "operation", "meaning", "explanation", "action", "purpose"}
# Paragraphs such as "or" between two blocks continue the previous description.
CONNECTIVES = {"or", "and", "also", "alternatively", "ok"}
LIST_MARKER = re.compile(r"^(?:[*+-]|\d+[.)])\s+")
TLDR_ALIAS = re.compile(r"^> (?:Note: )?This command is an alias of (?:GNU )?`([^`]+)`")
# Script banners: a rule of `#` (or `# ****`) above and below a section title.
RULE = re.compile(r"^#{10,}\s*$|^#\s*\*{10,}\s*$")


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
    if template.startswith("-"):
        parsed.diagnostics.append(Diagnostic(source.id, path, line, "flag-only fragment"))
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


def add_alias(name: str, target: str, parsed: Parsed) -> None:
    command = target.split()[0] if target.split() else ""
    # Subcommand pages such as `docker-stop` alias part of their own command.
    if command and name != command and not name.startswith(f"{command}-"):
        parsed.aliases.setdefault(name, command)


def tldr(text: str, source: Source, revision: str, path: str, parsed: Parsed) -> None:
    description = ""
    for number, line in enumerate(text.splitlines(), 1):
        alias = TLDR_ALIAS.match(line)
        if alias:
            add_alias(PurePosixPath(path).name.removesuffix(".md"), alias.group(1), parsed)
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


def eg_aliases(text: str, source: Source, path: str, parsed: Parsed) -> None:
    try:
        aliases = json.loads(text)
    except ValueError as exc:
        parsed.diagnostics.append(Diagnostic(source.id, path, 0, f"invalid aliases: {exc}"))
        return
    if not isinstance(aliases, dict):
        parsed.diagnostics.append(Diagnostic(source.id, path, 0, "invalid aliases: not an object"))
        return
    for name, target in sorted(aliases.items()):
        if isinstance(target, str):
            add_alias(name, target, parsed)


def script(text: str, source: Source, revision: str, path: str, parsed: Parsed) -> None:
    """Extract `command  # description` lines from a commented shell script.

    A blank line or banner ends a group, so a comment above a command only
    describes the commands that directly follow it. With a section allowlist
    for this file, commands outside the listed banner titles are skipped.
    """
    keep = {title.casefold() for title in source.sections.get(path, [])}
    group: list[str] = []
    first = 0
    title: list[str] | None = None
    section = ""
    reported: set[str] = set()

    def flush() -> None:
        nonlocal group
        if group:
            if not keep or section.casefold() in keep:
                code_block(group, first, "", source, revision, path, parsed)
            elif section not in reported and any(
                line.strip() and not line.lstrip().startswith("#") for line in group
            ):
                # One diagnostic per skipped section, not per command.
                reported.add(section)
                reason = f"unselected section: {section or 'preamble'}"
                parsed.diagnostics.append(Diagnostic(source.id, path, first, reason))
            group = []

    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if RULE.match(stripped):
            flush()
            if title is None:
                title = []
            else:
                # The first line names the section; later lines are notes such as URLs.
                section, title = next((line for line in title if line), ""), None
            continue
        if title is not None:
            title.append(stripped.lstrip("# "))
            continue
        if not stripped and not (group and group[-1].rstrip().endswith("\\")):
            flush()
            continue
        if not group:
            first = number
        group.append(line)
    flush()


def inline(text: str) -> str:
    """Reduce Markdown inline markup in a description to readable text."""
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.I)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\w)_(\S(?:.*?\S)?)_(?!\w)", r"\1", text)
    return " ".join(ATTRIBUTES.sub("", text).split())


def cell_text(cell: str) -> str:
    cell = cell.strip().replace("\\|", "|")
    code = re.fullmatch(r"(`+)\s*(.*?)\s*\1", cell)
    # Outside code spans, table cells escape Markdown punctuation such as `\*`.
    return code.group(2) if code else re.sub(r"\\([\\`*_{}\[\]()#+.!-])", r"\1", cell)


def trailing_comment(line: str) -> tuple[str, str] | None:
    """Split `command  # comment` at the first unquoted ` # `."""
    quote = ""
    escaped = False
    # An escaped space joins the word, so a `#` after it is not a comment.
    separator = False
    for index, char in enumerate(line):
        if escaped:
            escaped = separator = False
            continue
        if char == "\\" and quote != "'":
            escaped = True
        elif quote:
            quote = "" if char == quote else quote
        elif char in "'\"`":
            quote = char
        elif char == "#" and separator and line[index + 1 : index + 2].isspace():
            command, comment = line[:index].rstrip(), line[index + 1 :].strip()
            return (command, comment) if command and comment else None
        separator = not quote and char.isspace()
    return None


def code_block(
    lines: list[str],
    first: int,
    description: str,
    source: Source,
    revision: str,
    path: str,
    parsed: Parsed,
) -> None:
    """Extract commands from one shell code block.

    In a block with `$ ` prompts, unprompted lines are output. Otherwise every
    command line is an example. A `# comment` line describes the commands after
    it, and a trailing comment describes its own command.
    """
    prompted = any(PROMPT.match(line) for line in lines)
    comment = ""
    pending: list[str] = []
    own = ""
    start = 0

    def flush() -> None:
        nonlocal pending
        if pending:
            text = own or comment or description
            make_example(source, revision, path, start, text, "\n".join(pending), [], parsed)
            pending = []

    for offset, line in enumerate(lines):
        if pending and pending[-1].rstrip().endswith("\\"):
            pending.append(line)
            continue
        flush()
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            text = stripped.lstrip("# ")
            if text.strip(" .:,").lower() not in CONNECTIVES:
                comment = text
            continue
        if prompted and not PROMPT.match(line):
            continue
        text = PROMPT.sub("", line, count=1)
        own = ""
        trailing = trailing_comment(text.strip())
        if trailing and not text.rstrip().endswith("\\"):
            text, own = trailing
        start = first + offset
        pending = [text]
    flush()


def markdown_document(
    text: str,
    source: Source,
    revision: str,
    path: str,
    parsed: Parsed,
    *,
    indented: bool,
    bare: bool = False,
) -> None:
    """Extract shell examples from fenced (and optionally indented) blocks and tables.

    The paragraph just above a block describes it, falling back to the nearest
    heading. A heading naming another platform suppresses its whole section.
    With `bare`, fences without a language are shell too.
    """
    lines = text.splitlines()
    index = 0
    if lines and lines[0].strip() == "---":
        index = next(
            (number + 1 for number in range(1, len(lines)) if lines[number].strip() == "---"),
            len(lines),
        )
    paragraph: list[str] = []
    heading = ""
    previous = ""
    forbidden = 0
    blank = True

    def emit(body: list[str], first: int) -> None:
        nonlocal previous
        if forbidden:
            parsed.diagnostics.append(Diagnostic(source.id, path, first, "non-Linux section"))
            return
        description = inline(LIST_MARKER.sub("", " ".join(paragraph), count=1)) or heading
        if description.strip(" .:,").lower() in CONNECTIVES:
            description = previous
        previous = description
        code_block(body, first, description, source, revision, path, parsed)

    def table(rows: list[tuple[int, str]]) -> None:
        def cells(line: str) -> list[str]:
            return re.split(r"(?<!\\)\|", line.strip().strip("|"))

        if len(rows) < 3:
            return
        header = [cell_text(cell).lower() for cell in cells(rows[0][1])]
        command = next((k for k, name in enumerate(header) if name in COMMAND_COLUMNS), None)
        meaning = next((k for k, name in enumerate(header) if name in DESCRIPTION_COLUMNS), None)
        if command is None or meaning is None:
            return
        for number, line in rows[2:]:
            values = cells(line)
            if len(values) <= max(command, meaning):
                continue
            if forbidden:
                parsed.diagnostics.append(Diagnostic(source.id, path, number, "non-Linux section"))
                continue
            make_example(
                source,
                revision,
                path,
                number,
                inline(cell_text(values[meaning])),
                cell_text(values[command]),
                [],
                parsed,
            )

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        fence = FENCE.match(line) if stripped.startswith(("```", "~~~")) else None
        if fence:
            marker = fence.group(1)
            body: list[str] = []
            index += 1
            first = index + 1
            while index < len(lines):
                closing = lines[index].strip()
                if closing.startswith(marker) and not closing.strip(marker[0]):
                    break
                body.append(lines[index])
                index += 1
            language = fence.group(2).lower()
            if language in SHELL_FENCES or (bare and not language):
                emit(body, first)
            paragraph, blank = [], True
            index += 1
            continue
        if indented and blank and stripped and line.startswith(("    ", "\t")):
            body = []
            first = index + 1
            while index < len(lines) and (
                lines[index].startswith(("    ", "\t")) or not lines[index].strip()
            ):
                body.append(lines[index].removeprefix("    ").removeprefix("\t"))
                index += 1
            emit(body, first)
            paragraph, blank = [], True
            continue
        if stripped.startswith("|"):
            rows = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append((index + 1, lines[index]))
                index += 1
            table(rows)
            paragraph, blank = [], False
            continue
        title = HEADING.match(stripped)
        if title:
            level, heading = len(title.group(1)), inline(title.group(2))
            previous = ""
            if forbidden and level <= forbidden:
                forbidden = 0
            if FOREIGN.search(heading) and "linux" not in heading.lower():
                forbidden = level
            paragraph = []
        elif stripped and not ATTRIBUTES.fullmatch(stripped):
            if blank:
                paragraph = []
            paragraph.append(stripped)
        blank = not stripped or bool(title)
        index += 1


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
        elif source.adapter == "eg" and path.name == "aliases.json":
            eg_aliases(text, source, relative, parsed)
        elif source.adapter == "awesome-cheatsheets" and path.suffix == ".md":
            markdown_document(text, source, revision, relative, parsed, indented=False, bare=True)
        elif source.adapter == "awesome-cheatsheets":
            script(text, source, revision, relative, parsed)
        elif source.adapter in {"eg", "cheatsheets-zip", "devhints"}:
            markdown_document(
                text, source, revision, relative, parsed, indented=source.adapter == "eg"
            )
        else:
            commented(text, source, revision, relative, parsed)
    return parsed
