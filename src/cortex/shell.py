"""Inspect shell syntax without invoking a shell or executing any input."""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import bashlex

from cortex.adapters import PLACEHOLDER
from cortex.model import Example

POSIX_BUILTINS = set(
    ": . alias bg break cd command continue eval exec exit export false fc fg getopts hash jobs kill pwd read readonly return set shift test times trap true type ulimit umask unalias unset wait printf echo".split()
)
BASH_BUILTINS = POSIX_BUILTINS | set(
    "bind builtin caller compgen complete compopt declare dirs disown enable help history let local logout mapfile popd pushd readarray shopt source suspend typeset".split()
)
ZSH_BUILTINS = POSIX_BUILTINS | set(
    "autoload bindkey builtin bye cap chdir clone comparguments compcall compctl compdescribe compfiles compgroups compquote comptags comptry compvalues declare dirs disable disown echotc echoti emulate enable functions getcap getln history integer let limit local log logout noglob popd print pushd pushln rehash sched setcap setopt source stat suspend ttyctl typeset unfunction unhash unlimit unsetopt vared whence where which zcompile zformat zle zmodload zparseopts zprof zpty zregexparse zsocket zstyle ztcp".split()
)
BUILTINS = {"sh": POSIX_BUILTINS, "bash": BASH_BUILTINS, "zsh": ZSH_BUILTINS}
FOREIGN_COMMANDS = {
    "pbcopy",
    "pbpaste",
    "launchctl",
    "sw_vers",
    "osascript",
    "diskutil",
    "defaults",
    "airport",
    "Get-ChildItem",
}
OPAQUE = {"eval", "source", ".", "xargs", "parallel", "watch"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "fish"}
SAFE_SUDO_FLAGS = {
    "-n",
    "-E",
    "-H",
    "-S",
    "-A",
    "-b",
    "--non-interactive",
    "--preserve-env",
    "--set-home",
    "--stdin",
    "--askpass",
    "--background",
}
SUDO_ARGUMENT_FLAGS = {
    "-u",
    "-g",
    "-h",
    "-p",
    "-C",
    "-T",
    "-r",
    "-t",
    "--user",
    "--group",
    "--host",
    "--prompt",
    "--close-from",
    "--command-timeout",
    "--role",
    "--type",
}


class Unsupported(ValueError):
    pass


@dataclass
class Inspection:
    command: str
    subcommand: str
    required: list[str]
    shell: str
    external: list[str]


def protected_template(template: str) -> str:
    return PLACEHOLDER.sub(lambda match: "CORTEX_ARGUMENT", template)


def _literal(node, text: str) -> str:
    original = text[node.pos[0] : node.pos[1]]
    if node.parts or re.search(r"[$`*?{}\[\]~]", original) or "CORTEX_ARGUMENT" in node.word:
        raise Unsupported("dynamic executable or wrapper argument")
    return node.word


def inspect(template: str, configured_shell: str) -> Inspection:
    text = protected_template(template)
    if text.lstrip().startswith("#"):
        raise Unsupported("comment-only or shebang fragment")
    # Known GNU/BSD option differences are checked before parsing, even when the
    # source does not label the platform. This is not a general option validator.
    if re.search(r"\bsed\s+[^\n]*-i\s+(?:''|\"\")", text):
        raise Unsupported("BSD sed in-place syntax")
    if re.search(r"\bdate\s+(?:-j|-v)", text) or re.search(r"\bstat\s+-f\b", text):
        raise Unsupported("BSD command syntax")
    dialect = "posix"
    if re.search(r"<\(|>\(|\[\[|&>|\$'|\$\{[^}]*[/^,]", text):
        if configured_shell == "sh":
            raise Unsupported("recipe requires bash or zsh syntax")
        dialect = configured_shell
    try:
        roots = bashlex.parse(text)
    except Exception as exc:
        # bashlex can raise internal errors for unsupported upstream syntax.
        # Keep that failure within this one recipe, never the entire catalog.
        raise Unsupported(f"unsupported shell syntax: {exc}") from exc
    required: set[str] = set()
    external: set[str] = set()
    primary: list[tuple[str, str]] = []

    def invocation(words) -> None:
        if not words:
            return
        index = 0
        external_target = False
        while index < len(words):
            name = _literal(words[index], text)
            base = Path(name).name
            if name.startswith("./") or ("/" in name and not name.startswith("/")):
                raise Unsupported("recipe requires a relative executable")
            if base in FOREIGN_COMMANDS:
                raise Unsupported("non-Linux command")
            if base in OPAQUE:
                raise Unsupported(f"opaque command launcher: {base}")
            required.add(name)
            if external_target or base in {"sudo", "env"} or name.startswith("/"):
                external.add(name)
            index += 1
            if base == "sudo":
                external_target = True
                while index < len(words) and words[index].word.startswith("-"):
                    flag = _literal(words[index], text)
                    index += 1
                    if flag == "--":
                        break
                    if flag in SUDO_ARGUMENT_FLAGS:
                        if index >= len(words):
                            raise Unsupported("missing sudo option argument")
                        _literal(words[index], text)
                        index += 1
                    elif flag not in SAFE_SUDO_FLAGS and not any(
                        flag.startswith(option + "=")
                        for option in SUDO_ARGUMENT_FLAGS
                        if option.startswith("--")
                    ):
                        raise Unsupported(f"unsupported sudo option: {flag}")
                continue
            if base == "env":
                external_target = True
                while index < len(words):
                    value = words[index].word
                    if re.match(r"\w+=", value):
                        if value.startswith("PATH="):
                            raise Unsupported("recipe changes executable search PATH")
                        index += 1
                    elif value in {"-i", "--ignore-environment", "--"}:
                        index += 1
                    elif value in {"-u", "--unset"}:
                        index += 2
                    elif value.startswith("--unset="):
                        index += 1
                    elif value.startswith("-"):
                        raise Unsupported(f"unsupported env option: {value}")
                    else:
                        break
                continue
            if base in {"command", "exec", "builtin"}:
                if base == "exec":
                    external_target = True
                if base == "builtin" and index < len(words):
                    target = _literal(words[index], text)
                    if target not in BUILTINS[configured_shell]:
                        raise Unsupported(f"{target} is not a configured-shell builtin")
                if index < len(words) and words[index].word in {"-v", "-V"} and base == "command":
                    primary.append((base, ""))
                    return
                if index < len(words) and words[index].word == "--":
                    index += 1
                elif index < len(words) and words[index].word.startswith("-"):
                    raise Unsupported(f"unsupported {base} option")
                continue
            rest = [word.word for word in words[index:]]
            if base in SHELLS:
                raise Unsupported("shell interpreter payload needs separate dependency analysis")
            if base in {"ssh", "mosh"}:
                # Only unambiguous connection-only forms are retained initially.
                if len(rest) != 1 or rest[0].startswith("-"):
                    raise Unsupported("remote shell payload or ambiguous ssh arguments")
            if base in {"docker", "podman", "kubectl"} and "exec" in rest:
                raise Unsupported("container executable availability is unknown")
            if base == "find":
                for marker in ("-exec", "-execdir", "-ok", "-okdir"):
                    if marker in rest:
                        raise Unsupported(
                            "find execution payload needs separate dependency analysis"
                        )
            if base == "sed" and any(re.search(r"(?:^|;)\s*e(?:\s|$)", arg) for arg in rest):
                raise Unsupported("sed execution payload")
            subcommand = ""
            if base in {"git", "docker", "podman", "kubectl", "systemctl", "apt", "apt-get", "ip"}:
                if rest and re.fullmatch(r"[a-z][a-z0-9_-]*", rest[0]):
                    subcommand = rest[0]
            primary.append((base, subcommand))
            return
        raise Unsupported("wrapper has no literal target command")

    def walk(node) -> None:
        nonlocal dialect
        if node.kind in {"compound", "function", "for", "while", "if", "case"}:
            raise Unsupported("compound shell script is outside initial recipe support")
        if node.kind == "redirect" and getattr(node, "heredoc", None):
            raise Unsupported("heredoc recipe is unsupported")
        if node.kind == "command":
            for part in node.parts:
                if part.kind == "assignment" and part.word.startswith("PATH="):
                    raise Unsupported("recipe changes executable search PATH")
            invocation([part for part in node.parts if part.kind == "word"])
        for value in vars(node).values():
            if hasattr(value, "kind"):
                walk(value)
            elif isinstance(value, list):
                for child in value:
                    if hasattr(child, "kind"):
                        walk(child)

    try:
        for root in roots:
            walk(root)
    except (AttributeError, RecursionError) as exc:
        raise Unsupported("unrecognized shell structure") from exc
    if not primary:
        raise Unsupported("no executable command found")
    return Inspection(primary[0][0], primary[0][1], sorted(required), dialect, sorted(external))


class Availability:
    def __init__(self, shell: str, path: str | None = None):
        self.shell = shell
        self.path = os.environ.get("PATH", "") if path is None else path
        self._cache: dict[str, bool] = {}

    def has(self, command: str) -> bool:
        if command not in self._cache:
            self._cache[command] = command in BUILTINS[self.shell] or bool(
                shutil.which(command, path=self.path)
            )
        return self._cache[command]

    def apply(self, example: Example) -> str | None:
        if example.shell not in {"posix", self.shell, "sh"}:
            return f"recipe requires {example.shell}, configured shell is {self.shell}"
        try:
            result = inspect(example.template, self.shell)
        except Unsupported as exc:
            return f"unsupported: {exc}"
        example.command, example.subcommand = result.command, result.subcommand
        example.required_commands = result.required
        if example.shell == "posix" and result.shell != "posix":
            example.shell = result.shell
        example.identify()
        missing = [
            command
            for command in result.required
            if not self.has(command)
            or (command in result.external and not shutil.which(command, path=self.path))
        ]
        if missing:
            return "unavailable: " + ", ".join(missing)
        return None
