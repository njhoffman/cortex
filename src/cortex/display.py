"""Presentation of lookup results: stdout, fzf selection, and tmux panes."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

from cortex.config import Config
from cortex.model import Example

# `M-{` closes the pane whose ID cortex keeps in this window option.
PANE_OPTION = "@cortex_pane"
CLOSE_KEY = "M-{"
CLOSE_COMMAND = (
    f"p=$(tmux show-options -wqv {PANE_OPTION}); "
    f'[ -n "$p" ] && tmux kill-pane -t "$p"; tmux set-option -wu {PANE_OPTION}; true'
)
STALE_SECONDS = 86_400


def notice(message: str) -> None:
    print(f"cortex: {message}", file=sys.stderr)


def available(argv: list[str]) -> bool:
    return bool(argv) and shutil.which(argv[0]) is not None


def resolve_mode(mode: str) -> str:
    """Degrade to a mode the environment supports, explaining why."""
    if mode.startswith("fzf") and not shutil.which("fzf"):
        notice("fzf is not installed; showing results on stdout")
        return "stdout"
    if mode in {"fzf-split", "fzf-popup", "split", "popup"}:
        if not os.environ.get("TMUX") or not shutil.which("tmux"):
            fallback = "fzf" if mode.startswith("fzf") else "stdout"
            notice(f"{mode} needs a tmux session; using {fallback}")
            return fallback
    return mode


def to_stdout(config: Config, plain: str, colored: str) -> None:
    highlighter = config.display.highlighter
    if sys.stdout.isatty() and available(highlighter):
        sys.stdout.flush()
        subprocess.run(highlighter, input=plain + "\n", text=True, check=False)
    else:
        print(colored)


def highlight(config: Config, text: str) -> str:
    """Highlighted text for a preview pane, or the text itself."""
    highlighter = config.display.highlighter
    if not available(highlighter):
        return text
    result = subprocess.run(highlighter, input=text, capture_output=True, text=True, check=False)
    return result.stdout if result.returncode == 0 else text


def select(config: Config, examples: list[Example], mode: str) -> tuple[int, str]:
    """Run fzf over examples; return its status and the chosen raw template."""
    if not examples:
        return 1, ""
    cortex = [sys.executable, "-m", "cortex", "--config", str(config.paths.config)]
    preview = shlex.join([*cortex, "_preview"]) + " {1}"
    options = [
        "--delimiter=\t",
        "--with-nth=2..",
        "--prompt=cortex> ",
        f"--preview={preview}",
        "--preview-window=down,40%,wrap",
        *config.display.fzf_args,
    ]
    if mode == "fzf-split" and shutil.which("fzf-tmux"):
        argv = ["fzf-tmux", "-d", "40%", "--", *options]
    elif mode == "fzf-split":
        argv = ["fzf", "--tmux=bottom,40%", *options]
    elif mode == "fzf-popup":
        argv = ["fzf", "--tmux=center,80%", *options]
    else:
        argv = ["fzf", *options]
    by_id = {example.id: example for example in examples}
    lines = "".join(
        f"{example.id}\t{example.command}\t{' '.join(example.description.split())}\n"
        for example in examples
    )
    result = subprocess.run(argv, input=lines, stdout=subprocess.PIPE, text=True, check=False)
    chosen = result.stdout.split("\t", 1)[0].strip()
    if result.returncode or chosen not in by_id:
        return result.returncode or 1, ""
    return 0, by_id[chosen].template


def tmux(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["tmux", *args], capture_output=True, text=True, check=False)


def page_file(config: Config, text: str) -> Path:
    directory = config.paths.cache / "display"
    directory.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - STALE_SECONDS
    for old in directory.glob("cortex-*.txt"):
        try:
            if old.stat().st_mtime < cutoff:
                old.unlink()
        except OSError:
            pass
    path = directory / f"cortex-{uuid.uuid4().hex}.txt"
    path.write_text(text + "\n")
    return path


def pane_command(config: Config, path: Path) -> str:
    file = shlex.quote(str(path))
    highlighter = config.display.highlighter
    source = f"{shlex.join(highlighter)} < {file}" if available(highlighter) else f"cat {file}"
    pager = shlex.join(config.display.pager)
    return f"{source} | {pager}; rm -f {file}"


def bind_close() -> None:
    current = tmux("list-keys", "-T", "root", CLOSE_KEY)
    if current.returncode == 0 and current.stdout.strip():
        if PANE_OPTION not in current.stdout:
            notice(f"{CLOSE_KEY} is already bound in tmux; close the pane with `tmux kill-pane`")
        return
    tmux("bind-key", "-n", CLOSE_KEY, "run-shell", CLOSE_COMMAND)
    notice(
        f"bound {CLOSE_KEY} to close the cheatsheet pane; to keep it, add to tmux.conf:\n"
        f"  bind-key -n {CLOSE_KEY} run-shell {shlex.quote(CLOSE_COMMAND)}"
    )


def open_pane(config: Config, text: str, mode: str) -> int:
    command = pane_command(config, page_file(config, text))
    if mode == "popup":
        result = tmux("display-popup", "-E", *config.display.popup_args, command)
        return result.returncode
    # Target the pane cortex runs in, not tmux's most recently active client.
    target = ["-t", os.environ["TMUX_PANE"]] if os.environ.get("TMUX_PANE") else []
    # One cheatsheet pane per window: replace a live one, otherwise split without focus.
    pane = tmux("show-options", "-wqv", *target, PANE_OPTION).stdout.strip()
    if pane and tmux("display-message", "-p", "-t", pane, "#{pane_id}").returncode == 0:
        result = tmux("respawn-pane", "-k", "-t", pane, command)
    else:
        result = tmux(
            "split-window",
            "-d",
            "-P",
            "-F",
            "#{pane_id}",
            *target,
            *config.display.split_args,
            command,
        )
        pane = result.stdout.strip()
        if result.returncode == 0 and pane:
            tmux("set-option", "-w", *target, PANE_OPTION, pane)
    if result.returncode:
        notice(f"tmux failed: {result.stderr.strip()}")
        return 1
    bind_close()
    return 0
