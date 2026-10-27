import io
import json
import os
import threading

import pytest

from cortex import cli
from cortex.cache import SourceCache
from cortex.events import SyncEvent
from cortex.progress import SyncDisplay, clean, use_color
from cortex.sync import run


class Terminal(io.StringIO):
    def isatty(self):
        return True

    def fileno(self):
        return 2


@pytest.fixture
def terminal(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    return Terminal()


def test_gradient_dashboard_completes_and_restores_cursor(terminal):
    with SyncDisplay(["tldr"], stream=terminal, interval=60) as display:
        display.update(SyncEvent("source", 1, 1, source="tldr", status="unchanged", examples=300))
        display.update(SyncEvent("done", 1, 1, message="Sync complete"))
        display.finish(0)
    output = terminal.getvalue()
    assert "\x1b[38;2;" in output
    assert "100%" in output and "Sync complete" in output
    assert "tldr" in output and "unchanged" in output
    assert output.count("\x1b[?25l") == output.count("\x1b[?25h") == 1
    assert output.endswith("\x1b[?25h")


def test_failed_sync_never_claims_completion_and_restores_cursor(terminal):
    with pytest.raises(RuntimeError, match="simulated"):
        with SyncDisplay([], stream=terminal, interval=60) as display:
            display.update(SyncEvent("filter", 2, 10, message="Checking installed commands"))
            raise RuntimeError("simulated publication error")
    output = terminal.getvalue()
    assert "Sync failed" in output
    assert "100%" not in output
    assert output.endswith("\x1b[?25h")


def test_interruption_restores_cursor_without_reporting_success(terminal):
    with pytest.raises(KeyboardInterrupt):
        with SyncDisplay([], stream=terminal, interval=60):
            raise KeyboardInterrupt
    assert "Sync interrupted" in terminal.getvalue()
    assert terminal.getvalue().endswith("\x1b[?25h")
    assert "Sync complete" not in terminal.getvalue()


def test_partial_source_failure_is_visibly_distinct(terminal):
    with SyncDisplay(["cheat"], stream=terminal, interval=60) as display:
        display.update(
            SyncEvent(
                "source",
                1,
                1,
                source="cheat",
                status="stale",
                examples=20,
                message="upstream unavailable",
            )
        )
        display.update(SyncEvent("done", 1, 1))
        display.finish(2)
    output = clean(terminal.getvalue())
    assert "stale" in output and "upstream unavailable" in output
    assert "Complete with unavailable or stale sources" in output


def test_source_events_keep_the_active_phase_caption(terminal):
    with SyncDisplay(["test"], stream=terminal, interval=60) as display:
        display.update(SyncEvent("sources", total=1, message="Reading cached sources"))
        display.update(SyncEvent("source", total=1, source="test", status="reading"))
        assert display.event.message == "Reading cached sources"
        assert display.event.total == 1
        display.update(SyncEvent("source", 1, 1, source="test", status="offline", examples=2))
        assert display.event.completed == 1
        assert display.event.message == "Reading cached sources"
        display.finish(0)


@pytest.mark.parametrize("setting", ["no-color", "dumb", "never", "json"])
def test_color_controls_disable_all_terminal_escapes(terminal, monkeypatch, setting):
    if setting == "no-color":
        monkeypatch.setenv("NO_COLOR", "")
    if setting == "dumb":
        monkeypatch.setenv("TERM", "dumb")
    with SyncDisplay(
        ["tldr"],
        stream=terminal,
        color="never" if setting == "never" else "always",
        json_output=setting == "json",
    ) as display:
        display.update(SyncEvent("sources", total=1, message="Refreshing sources"))
        display.update(SyncEvent("source", 1, 1, source="tldr", status="updated", examples=10))
        display.update(SyncEvent("done", 1, 1))
        display.finish(0)
    assert "\x1b" not in terminal.getvalue()


def test_redirected_output_is_static_and_can_explicitly_use_color(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    plain = io.StringIO()
    assert not use_color(plain)
    colored = io.StringIO()
    with SyncDisplay([], stream=colored, color="always") as display:
        assert not display.animated
        display.update(SyncEvent("filter", total=10, message="Checking installed commands"))
        display.update(SyncEvent("done", 1, 1))
        display.finish(0)
    output = colored.getvalue()
    assert "\x1b[38;2;" in output and "100%" in output
    assert "\x1b[?25" not in output and "\r" not in output


def test_narrow_terminal_does_not_wrap_dashboard_rows(terminal, monkeypatch):
    monkeypatch.setattr(os, "get_terminal_size", lambda *args: os.terminal_size((20, 24)))
    with SyncDisplay(["long-source-name"], stream=terminal, interval=60) as display:
        display.update(SyncEvent("done", 1, 1))
        display.finish(0)
    # Work from raw lines because clean() intentionally turns control newlines into spaces.
    from cortex.progress import TERMINAL_CODES

    assert all(len(TERMINAL_CODES.sub("", line)) <= 19 for line in terminal.getvalue().splitlines())


def test_short_split_pane_keeps_the_progress_bar_without_scrolling(terminal, monkeypatch):
    monkeypatch.setattr(os, "get_terminal_size", lambda *args: os.terminal_size((70, 6)))
    with SyncDisplay(["a", "b", "c", "d"], stream=terminal, interval=60) as display:
        display.update(SyncEvent("done", 1, 1))
        display.finish(0)
    final_frame = terminal.getvalue().split("\x1b[J")[-1]
    assert final_frame.count("\n") <= 5
    assert "100%" in final_frame and "Sync complete" in final_frame


def test_json_stays_parseable_even_with_forced_color_and_a_tty(
    config,
    local_source,
    terminal,
    monkeypatch,
    capsys,
):
    local_source()
    monkeypatch.setattr(cli, "load", lambda paths: config)
    monkeypatch.setattr(cli.sys, "stderr", terminal)
    assert cli.main(["sync", "--json", "--color", "always"]) == 0
    stdout = capsys.readouterr().out
    assert json.loads(stdout)["published"] is True
    assert "\x1b" not in stdout + terminal.getvalue()


def test_completion_feedback_is_prompt_but_merge_priority_is_preserved(
    config, local_source, monkeypatch
):
    local_source("first", "# Preferred description:\nprintf same\n")
    local_source("second", "# Second description:\nprintf same\n")
    gate = threading.Event()
    original = SourceCache.refresh
    finished = []

    def refresh(cache, **kwargs):
        result = original(cache, **kwargs)
        if cache.source.id == "first":
            assert gate.wait(10), (
                "the second source should report completion without waiting for first"
            )
        return result

    def progress(event):
        if event.phase == "source" and event.status == "updated":
            finished.append(event.source)
            if event.source == "second":
                gate.set()

    monkeypatch.setattr(SourceCache, "refresh", refresh)
    status, report = run(config, progress=progress)
    assert status == 0 and finished == ["second", "first"]
    assert [source["id"] for source in report["sources"]] == ["first", "second"]
    catalog = json.loads((config.paths.data / "current/catalog.jsonl").read_text())
    assert catalog["description"] == "Preferred description"


def test_progress_tracks_actual_examples_and_finishes_after_publication(config, local_source):
    local_source(text="".join(f"# Example {number}:\nprintf '{number}'\n" for number in range(300)))
    events = []

    def progress(event):
        events.append(event)
        if event.phase == "done":
            assert (config.paths.data / "current/catalog.jsonl").is_file()
            assert (config.paths.cache / "last-sync.json").is_file()

    status, report = run(config, progress=progress)
    assert status == 0 and report["counts"]["retained"] == 300
    filtering = [event for event in events if event.phase == "filter"]
    assert [event.completed for event in filtering] == [0, 128, 256, 300]
    assert all(event.total == 300 for event in filtering)
    assert events[-1].phase == "done" and events[-1].fraction == 1.0
    assert all(event.fraction < 1.0 for event in events[:-1])
    before = (config.paths.data / "current/catalog.jsonl").read_bytes()
    run(config, offline=True)
    assert (config.paths.data / "current/catalog.jsonl").read_bytes() == before


def test_source_errors_cannot_inject_terminal_controls(terminal):
    with SyncDisplay(["test"], stream=terminal, interval=60) as display:
        display.update(
            SyncEvent("source", 1, 1, source="test", status="failed", message="error\x1b[2J\ntext")
        )
        display.finish(1)
    assert "\x1b[2J" not in terminal.getvalue()
    assert "error text" in terminal.getvalue()


def test_plain_log_aligns_long_source_names():
    stream = io.StringIO()
    names = ["tldr", "awesome-cheatsheets"]
    with SyncDisplay(names, stream=stream, color="never", interval=60) as display:
        for name in names:
            display.update(SyncEvent("source", source=name, status="updated", examples=5))
    lines = stream.getvalue().splitlines()
    assert [line.index("updated") for line in lines] == [21, 21]
