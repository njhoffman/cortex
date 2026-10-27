"""A small terminal dashboard with a gradient bar and plain-output fallback."""

from __future__ import annotations

import math
import os
import re
import sys
import threading
import time
from typing import TextIO

from cortex.events import SyncEvent

RESET = "\x1b[0m"
DIM = "\x1b[2m"
COLORS = {
    "accent": "\x1b[38;2;100;190;255m",
    "success": "\x1b[38;2;76;220;163m",
    "warning": "\x1b[38;2;244;191;85m",
    "error": "\x1b[38;2;248;112;125m",
    "dim": "\x1b[2m",
}
GRADIENT = ((126, 87, 255), (49, 181, 250), (76, 220, 163))
SPINNER = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
TERMINAL_CODES = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")


def clean(text: str) -> str:
    """Keep source error text from injecting terminal controls into the dashboard."""
    text = TERMINAL_CODES.sub("", str(text))
    return "".join(char if char.isprintable() else " " for char in text)


def use_color(stream: TextIO, mode: str = "auto", *, json_output: bool = False) -> bool:
    if (
        json_output
        or mode == "never"
        or "NO_COLOR" in os.environ
        or os.environ.get("TERM") == "dumb"
    ):
        return False
    return mode == "always" or stream.isatty()


def style(text: str, color: str, enabled: bool) -> str:
    return f"{COLORS[color]}{text}{RESET}" if enabled else text


def gradient_bar(fraction: float, width: int, *, colored: bool, unicode: bool = True) -> str:
    fraction = min(1.0, max(0.0, fraction))
    filled = min(width, math.floor(fraction * width + 1e-9))
    cell, empty = ("━", "━") if unicode else ("=", "-")
    if not colored:
        return cell * filled + empty * (width - filled)
    output = []
    for index in range(filled):
        position = index / max(1, width - 1) * (len(GRADIENT) - 1)
        left = min(int(position), len(GRADIENT) - 2)
        blend = position - left
        red, green, blue = (
            round(a + (b - a) * blend) for a, b in zip(GRADIENT[left], GRADIENT[left + 1])
        )
        output.append(f"\x1b[38;2;{red};{green};{blue}m{cell}")
    output.append(f"{RESET}{DIM}{empty * (width - filled)}{RESET}")
    return "".join(output)


class SyncDisplay:
    def __init__(
        self,
        sources: list[str],
        *,
        stream: TextIO | None = None,
        color: str = "auto",
        json_output: bool = False,
        interval: float = 0.10,
    ):
        self.stream = stream if stream is not None else sys.stderr
        self.colored = use_color(self.stream, color, json_output=json_output)
        self.animated = self.colored and self.stream.isatty()
        self.interval = interval
        self.sources = {name: ("waiting", 0, "") for name in sources}
        self.name_width = max([15, *map(len, sources)])
        self.event = SyncEvent("prepare", message="Preparing sync")
        self.fraction = 0.0
        self.started = time.monotonic()
        self.outcome: int | None = None
        self._lines = 0
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._plain_phase = ""
        self._source_message = "Refreshing cheatsheet sources"
        try:
            "━✓⠋".encode(getattr(self.stream, "encoding", None) or "utf-8")
            self.unicode = True
        except (LookupError, UnicodeEncodeError):
            self.unicode = False

    def __enter__(self) -> SyncDisplay:
        if self.animated:
            with self._lock:
                self.stream.write("\x1b[?25l")
                self._render()
            self._thread = threading.Thread(target=self._tick, name="cortex-progress", daemon=True)
            self._thread.start()
        return self

    def __exit__(self, kind, value, traceback) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join()
        if self.animated:
            with self._lock:
                if self.outcome is None:
                    self.outcome = 130 if kind is KeyboardInterrupt else 1
                try:
                    self._render()
                    for name, (status, _, message) in self.sources.items():
                        if message:
                            self.stream.write(
                                style(
                                    f"  {name}: {clean(message)}",
                                    self._status_color(status),
                                    self.colored,
                                )
                                + "\n"
                            )
                finally:
                    self.stream.write("\x1b[?25h")
                    self.stream.flush()

    def _tick(self) -> None:
        while not self._stop.wait(self.interval):
            with self._lock:
                try:
                    self._render()
                except (OSError, ValueError):
                    return

    def update(self, event: SyncEvent) -> None:
        with self._lock:
            if event.phase == "sources":
                self._source_message = event.message
            self.event = event
            self.fraction = max(self.fraction, event.fraction)
            if event.source:
                self.sources[event.source] = (event.status, event.examples, event.message)
                self.event = SyncEvent(
                    "sources", event.completed, event.total, message=self._source_message
                )
            if not self.animated:
                self._log(event)

    def finish(self, status: int) -> None:
        with self._lock:
            self.outcome = status

    def _log(self, event: SyncEvent) -> None:
        if event.phase == "source":
            if event.status in {"refreshing", "reading", "waiting"}:
                return
            color = self._status_color(event.status)
            suffix = f" — {clean(event.message)}" if event.message else ""
            print(
                style(
                    f"{event.source:<{self.name_width + 1}} {event.status:<10} {event.examples:>6} examples{suffix}",
                    color,
                    self.colored,
                ),
                file=self.stream,
                flush=True,
            )
        elif event.phase == "done" and self.colored:
            self.stream.write(gradient_bar(1.0, 28, colored=True, unicode=self.unicode) + " 100%\n")
            self.stream.flush()
        elif event.phase != self._plain_phase and event.phase != "done":
            self._plain_phase = event.phase
            print(style(clean(event.message), "accent", self.colored), file=self.stream, flush=True)
            if self.colored:
                self.stream.write(
                    gradient_bar(self.fraction, 28, colored=True, unicode=self.unicode)
                    + f" {self.fraction:>4.0%}\n"
                )
                self.stream.flush()

    @staticmethod
    def _status_color(status: str) -> str:
        if status in {"failed", "missing"}:
            return "error"
        if status in {"stale", "waiting", "refreshing", "reading"}:
            return "warning"
        return "success"

    def _size(self) -> tuple[int, int]:
        try:
            size = os.get_terminal_size(self.stream.fileno())
            return max(1, size.columns - 1), max(2, size.lines)
        except (OSError, AttributeError, ValueError):
            return 79, 24

    def _render(self) -> None:
        width, height = self._size()
        elapsed = max(0, int(time.monotonic() - self.started))
        elapsed_text = f"{elapsed // 60:02d}:{elapsed % 60:02d}"
        spinner = (
            SPINNER[int((time.monotonic() - self.started) / self.interval) % len(SPINNER)]
            if self.unicode
            else "|/-\\"[elapsed % 4]
        )

        def line(text: str, color: str | None = None) -> str:
            text = clean(text)[:width]
            return style(text, color, self.colored) if color else text

        rows = [line("CORTEX  /  SYNC", "accent"), ""]
        for name, (status, examples, _) in self.sources.items():
            if status in {"refreshing", "reading"}:
                icon = spinner
            elif status in {"failed", "missing"}:
                icon = "✗" if self.unicode else "x"
            elif status == "stale":
                icon = "!"
            elif status == "waiting":
                icon = "·" if self.unicode else "."
            else:
                icon = "✓" if self.unicode else "+"
            count = (
                f"{examples:>7,} examples"
                if status not in {"waiting", "refreshing", "reading"}
                else ""
            )
            rows.append(
                line(
                    f"  {icon} {name:<{self.name_width}} {status:<10} {count}",
                    self._status_color(status),
                )
            )
        rows.append("")
        if width >= 24:
            bar_width = min(54, width - 16)
            rows.append(
                "  "
                + gradient_bar(self.fraction, bar_width, colored=True, unicode=self.unicode)
                + f" {self.fraction:>4.0%}  {elapsed_text}"
            )
        else:
            rows.append(line(f"{self.fraction:.0%}  {elapsed_text}", "accent"))
        if self.outcome == 0:
            detail, color = "✓ Sync complete" if self.unicode else "+ Sync complete", "success"
        elif self.outcome == 2:
            detail, color = "! Complete with unavailable or stale sources", "warning"
        elif self.outcome == 130:
            detail, color = "Sync interrupted", "warning"
        elif self.outcome is not None:
            detail, color = "Sync failed", "error"
        else:
            detail, color = f"{spinner} {self.event.message}", "accent"
            if self.event.total and self.event.phase in {"sources", "filter", "publish"}:
                unit = {"sources": "sources", "filter": "examples", "publish": "files"}[
                    self.event.phase
                ]
                detail += f"  {self.event.completed:,}/{self.event.total:,} {unit}"
        rows.append(line("  " + detail, color))
        if len(rows) >= height:
            # Compact split panes keep the bar and phase visible without scrolling
            # a dashboard taller than the terminal on each animation tick.
            heading = rows[:1] if height >= 5 else []
            slots = max(0, height - len(heading) - 3)
            rows = heading + rows[2 : 2 + min(slots, len(self.sources))] + rows[-2:]
            rows = rows[-(height - 1) :]
        if self._lines:
            self.stream.write(f"\x1b[{self._lines}F\x1b[J")
        self.stream.write("\n".join(rows) + "\n")
        self.stream.flush()
        self._lines = len(rows)


def summary(report: dict, *, colored: bool) -> str:
    counts = report["counts"]
    leading = style(f"Published {counts['retained']:,} examples", "success", colored)
    commands = style(f"{report['commands']:,} commands", "accent", colored)
    return (
        f"{leading} for {commands} "
        f"({counts['duplicate']:,} duplicates, {counts['unavailable']:,} unavailable, "
        f"{counts['unsupported']:,} unsupported, {counts['excluded']:,} excluded)."
    )
