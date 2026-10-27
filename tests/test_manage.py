import json

import pytest

from cortex.cli import main
from cortex.lookup import load_snapshot
from cortex.manage import Exclusions, add
from cortex.model import CortexError
from cortex.sync import run


@pytest.fixture
def cli(config, local_source, monkeypatch):
    local_source()
    assert run(config)[0] == 0
    monkeypatch.setattr("cortex.cli.load", lambda paths: config)
    return main


def test_add_appends_without_rewriting(config):
    custom = config.paths.data / "custom"
    custom.mkdir(parents=True)
    (custom / "printf.cheat").write_text("# Mine:\nprintf mine")
    path, missing = add(config, "printf 'two\\n'", "  # Second   example ")
    assert path == custom / "printf.cheat" and missing == []
    assert path.read_text() == "# Mine:\nprintf mine\n\n# Second example\nprintf 'two\\n'\n"
    _, missing = add(config, "cortex-missing-tool | cat", "Missing")
    assert missing == ["cortex-missing-tool"]


@pytest.mark.parametrize(
    "template, description, message",
    [
        ("", "x", "required"),
        ("printf x", " ", "required"),
        ("printf a\nprintf b", "x", "backslash"),
        ('printf "open', "x", "Cannot add"),
    ],
)
def test_add_rejects_invalid_input(config, template, description, message):
    with pytest.raises(CortexError, match=message):
        add(config, template, description)


def test_exclusions_round_trip_keeps_top_comments(config):
    path = config.paths.data / "exclusions.toml"
    path.parent.mkdir(parents=True)
    path.write_text('# keep me\n\n# and me\nids = ["b", "a"]\n# lost\ncommands = []\n')
    exclusions = Exclusions.read(config)
    exclusions.commands.add('we"ird')
    exclusions.write()
    text = path.read_text()
    assert text.startswith("# keep me\n\n# and me\n\nids = [\n")
    assert "# lost" not in text
    again = Exclusions.read(config)
    assert again.ids == {"a", "b"} and again.commands == {'we"ird'}


def test_new_exclusions_file_gets_header(config):
    exclusions = Exclusions.read(config)
    exclusions.ids.add("abc")
    exclusions.write()
    assert exclusions.path.read_text().startswith("# Remembered removals.")


def test_remove_and_restore_by_id_and_command(cli, config, capsys):
    example = load_snapshot(config).examples[0]
    assert cli(["remove", example.id[:8], "--color", "never"]) == 0
    snapshot = load_snapshot(config)
    assert not snapshot.examples and [item.id for item in snapshot.excluded] == [example.id]
    assert cli(["remove", example.id[:8]]) == 0
    assert "already removed" in capsys.readouterr().out
    assert cli(["restore", "--color", "never"]) == 0
    assert f"{example.id[:10]}  printf: Print a greeting" in capsys.readouterr().out
    assert cli(["restore", example.id[:8], "--color", "never"]) == 0
    assert [item.id for item in load_snapshot(config).examples] == [example.id]

    assert cli(["remove", "--command", "printf", "--no-sync"]) == 0
    assert "sync --offline" in capsys.readouterr().out
    assert load_snapshot(config).examples
    assert cli(["restore", "--command", "nope"]) == 1
    assert cli(["restore", "--command", "printf"]) == 0
    assert load_snapshot(config).examples
    assert cli(["remove", "--command", "nope"]) == 1
    assert "No examples for nope" in capsys.readouterr().err


def test_add_cli_rebuilds_and_warns(cli, config, capsys):
    assert cli(["add", "printf added", "-d", "Added one", "--color", "never"]) == 0
    assert "Added one" in [item.description for item in load_snapshot(config).examples]
    assert cli(["add", "cortex-missing-tool", "-d", "Missing", "--no-sync"]) == 0
    assert "not installed" in capsys.readouterr().err
    assert cli(["list", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["examples"] == 2
