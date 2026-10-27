import json

import pytest

from cortex.cli import main
from cortex.config import load
from cortex.display import open_pane, pane_command, resolve_mode, select
from cortex.model import CortexError, Example
from cortex.sync import run

# Fakes use only shell builtins so PATH can hold nothing but these scripts.
FAKE_TMUX = """#!/bin/sh
echo "$*" >> "$LOG"
case "$1" in
  show-options) [ -s "$STATE" ] && read -r pane < "$STATE" && echo "$pane"; exit 0 ;;
  display-message) [ -s "$STATE" ] ;;
  split-window) echo "%7" ;;
  set-option) for last; do :; done; echo "$last" > "$STATE" ;;
  list-keys) [ -n "$BOUND" ] && echo "$BOUND" ;;
esac
"""
FAKE_FZF = """#!/bin/sh
echo "$*" >> "$LOG"
read -r first
read -r second
[ -n "$FZF_EXIT" ] && exit "$FZF_EXIT"
echo "${second:-$first}"
"""


@pytest.fixture
def fakes(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    def install(name, text):
        path = bin_dir / name
        path.write_text(text)
        path.chmod(0o755)

    install("tmux", FAKE_TMUX)
    install("fzf", FAKE_FZF)
    log = tmp_path / "calls.log"
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setenv("LOG", str(log))
    monkeypatch.setenv("STATE", str(tmp_path / "pane"))
    monkeypatch.setenv("TMUX", "/tmp/fake,1,0")
    monkeypatch.setenv("TMUX_PANE", "%1")
    monkeypatch.delenv("BOUND", raising=False)
    monkeypatch.delenv("FZF_EXIT", raising=False)

    def calls():
        return log.read_text().splitlines() if log.exists() else []

    return install, calls


def examples():
    return [
        Example("First", "printf one", [], command="printf", id="a" * 64),
        Example("Second", "printf 'two' \\\n  three", [], command="printf", id="b" * 64),
    ]


def test_modes_degrade_without_tools(fakes, monkeypatch, capsys):
    assert resolve_mode("split") == "split"
    monkeypatch.delenv("TMUX")
    assert resolve_mode("split") == "stdout"
    assert resolve_mode("fzf-popup") == "fzf"
    monkeypatch.setenv("PATH", "/nonexistent")
    assert resolve_mode("fzf") == "stdout"
    err = capsys.readouterr().err
    assert "split needs a tmux session; using stdout" in err
    assert "fzf is not installed" in err


def test_fzf_selection_prints_raw_template(fakes, config):
    _, calls = fakes
    assert select(config, examples(), "fzf") == (0, "printf 'two' \\\n  three")
    argv = calls()[-1]
    assert "--with-nth=2.." in argv and "_preview {1}" in argv and "--tmux" not in argv
    select(config, examples(), "fzf-popup")
    assert "--tmux=center,80%" in calls()[-1]
    select(config, examples(), "fzf-split")
    assert "--tmux=bottom,40%" in calls()[-1]


def test_fzf_split_prefers_fzf_tmux(fakes, config):
    install, calls = fakes
    install("fzf-tmux", FAKE_FZF)
    select(config, examples(), "fzf-split")
    assert calls()[-1].startswith("-d 40% -- --delimiter")


def test_fzf_cancel_returns_status_without_output(fakes, config, monkeypatch):
    monkeypatch.setenv("FZF_EXIT", "130")
    assert select(config, examples(), "fzf") == (130, "")
    assert select(config, [], "fzf") == (1, "")


def test_split_opens_without_focus_then_reuses_pane(fakes, config, capsys):
    _, calls = fakes
    assert open_pane(config, "tar\n  tar -xf a.tar", "split") == 0
    log = calls()
    split = next(line for line in log if line.startswith("split-window"))
    assert split.startswith("split-window -d -P -F #{pane_id} -t %1 -h -l 40% ")
    assert "set-option -w -t %1 @cortex_pane %7" in log
    assert any(line.startswith("bind-key -n M-{ run-shell") for line in log)
    assert "bound M-{" in capsys.readouterr().err
    assert open_pane(config, "git", "split") == 0
    assert any(line.startswith("respawn-pane -k -t %7 ") for line in calls())
    assert len([line for line in calls() if line.startswith("split-window")]) == 1


def test_existing_close_binding_is_respected(fakes, config, monkeypatch, capsys):
    _, calls = fakes
    monkeypatch.setenv("BOUND", "bind-key -T root M-{ select-pane -U")
    assert open_pane(config, "text", "split") == 0
    assert not any(line.startswith("bind-key") for line in calls())
    assert "already bound" in capsys.readouterr().err
    monkeypatch.setenv("BOUND", "bind-key -T root M-{ run-shell ... @cortex_pane ...")
    open_pane(config, "text", "split")
    assert "already bound" not in capsys.readouterr().err


def test_popup_and_pane_command(fakes, config):
    _, calls = fakes
    assert open_pane(config, "text", "popup") == 0
    assert calls()[-1].startswith("display-popup -E -w 80% -h 80% cat ")
    page = config.paths.cache / "display"
    [path] = list(page.glob("cortex-*.txt"))
    assert path.read_text() == "text\n"
    assert pane_command(config, path).endswith(f"| less -R; rm -f {path}")


def test_display_configuration_is_validated(config):
    for content in [
        '[display]\nmode = "pager"\n',
        '[display]\npager = "less"\n',
        "[display]\npager = []\n",
        "[display]\nunknown = 1\n",
    ]:
        config.paths.config.write_text(content)
        with pytest.raises(CortexError):
            load(config.paths)
    config.paths.config.write_text('[display]\nmode = "split"\nsplit_args = ["-v"]\n')
    assert load(config.paths).display.split_args == ["-v"]


def test_cli_display_modes(fakes, config, local_source, monkeypatch, capsys):
    local_source(text="# Print one:\nprintf one\n\n# Print two:\nprintf two\n")
    assert run(config)[0] == 0
    monkeypatch.setattr("cortex.cli.load", lambda paths: config)
    assert main(["show", "printf", "--display", "fzf"]) == 0
    assert capsys.readouterr().out == "printf two\n"
    assert main(["list", "--display", "fzf"]) == 0
    assert capsys.readouterr().out == "printf two\n"
    config.display.mode = "split"
    assert main(["search", "print"]) == 0
    assert capsys.readouterr().out == ""
    assert main(["show", "printf", "--display", "stdout", "--color", "never"]) == 0
    assert "# Print one" in capsys.readouterr().out
    assert main(["show", "printf", "--json"]) == 0
    first = json.loads(capsys.readouterr().out)[0]["id"]
    assert main(["_preview", first]) == 0
    assert capsys.readouterr().out == "# Print one\nprintf one\n"
    assert main(["_preview", "0" * 64]) == 1
