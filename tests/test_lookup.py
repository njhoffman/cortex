import json

import pytest

from cortex.cache import SourceResult
from cortex.cli import main
from cortex.config import Source
from cortex.lookup import (
    commands,
    find_by_id,
    load_snapshot,
    render,
    score,
    search,
    show,
    show_alias,
)
from cortex.model import CortexError, Example
from cortex.sync import merge_aliases, run

SHEET = (
    "# Print a greeting:\nprintf 'hello\\n'\n\n"
    "# Extract an archive listing:\nprintf 'archive\\n'\n\n"
    "# Change directory:\ncd /tmp\n"
)


@pytest.fixture
def published(config, local_source):
    local_source(text=SHEET)
    assert run(config)[0] == 0
    return load_snapshot(config)


@pytest.fixture
def cli(config, monkeypatch):
    monkeypatch.setattr("cortex.cli.load", lambda paths: config)
    return main


def test_lookup_requires_a_published_catalog(config):
    with pytest.raises(CortexError, match="run `cortex sync` first"):
        load_snapshot(config)


def test_list_show_and_categories(published):
    rows = commands(published.examples)
    assert rows == [
        {"command": "cd", "categories": ["files"], "examples": 1},
        {"command": "printf", "categories": ["shell"], "examples": 2},
    ]
    assert [row["command"] for row in commands(published.examples, "files")] == ["cd"]
    assert len(show(published.examples, "printf")) == 2
    assert show(published.examples, "printf", "nope") == []


def test_search_ranks_command_names_and_requires_every_term(published):
    assert [item.command for item in search(published.examples, ["printf"], 10)] == [
        "printf",
        "printf",
    ]
    found = search(published.examples, ["archive", "listing"], 10)
    assert [item.description for item in found] == ["Extract an archive listing"]
    assert search(published.examples, ["archive", "missing-term"], 10) == []
    assert len(search(published.examples, ["printf"], 1)) == 1
    with pytest.raises(CortexError):
        search(published.examples, ["  "], 10)


def test_score_weights():
    example = Example("Extract files", "tar -xf a.tar", [], command="tar", category="archives")
    assert score(example, ["tar"]) > score(example, ["ta"]) > score(example, ["extract"])
    assert score(example, ["archive"]) == 3
    assert score(example, ["zip"]) == 0


def test_find_by_id_prefixes(published):
    example = published.examples[0]
    assert find_by_id(example.id[:6].upper(), published.examples) is example
    with pytest.raises(CortexError, match="at least 6"):
        find_by_id(example.id[:5], published.examples)
    with pytest.raises(CortexError, match="--command"):
        find_by_id("printf", published.examples)
    twins = [Example("a", "a", [], id="abcdef01"), Example("b", "b", [], id="abcdef02")]
    with pytest.raises(CortexError, match="ambiguous"):
        find_by_id("abcdef", twins)


def test_render_keeps_templates_unstyled_and_shows_origins(published):
    text = render(show(published.examples, "printf"), colored=True, origins=True)
    assert "\n  printf 'hello\\n'\n" in text
    assert "from sample printf:" in text and "(test, " in text
    assert "[" + published.examples[0].id[:10] not in render(published.examples[:0], colored=False)


def test_lookup_cli(cli, published, capsys):
    assert cli(["list", "--json"]) == 0
    assert [row["command"] for row in json.loads(capsys.readouterr().out)] == ["cd", "printf"]
    assert cli(["show", "printf", "--color", "never", "--origins"]) == 0
    output = capsys.readouterr().out
    assert "# Print a greeting" in output and "from sample" in output
    assert cli(["show", "nope"]) == 1
    assert "cortex search nope" in capsys.readouterr().err
    assert cli(["search", "greeting", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["template"] == "printf 'hello\\n'"
    assert cli(["search", "zzz-no-match"]) == 1
    assert cli(["search", "x", "--limit", "0"]) == 1


@pytest.fixture
def aliased(config, local_source, tmp_path):
    local_source(text=SHEET)
    root = tmp_path / "upstream-eg"
    (root / "eg/examples").mkdir(parents=True)
    (root / "eg/examples/printf.md").write_text("# printf\n\nPrint:\n\n    printf ok\n")
    (root / "eg/examples/aliases.json").write_text(
        '{"pf": "print", "print": "printf", "cd": "printf", "ghost": "nowhere"}'
    )
    include = ["eg/examples/*.md", "eg/examples/aliases.json"]
    config.sources.append(Source("eg", str(root), "eg", transport="local", include=include))
    assert run(config)[0] == 0
    return load_snapshot(config)


def test_merge_aliases_priority_chains_and_cycles():
    def result(name, aliases):
        return SourceResult(Source(name, "x", "eg"), "local", aliases=aliases)

    merged = merge_aliases(
        [
            result("first", {"a": "b", "x": "y", "y": "x"}),
            result("second", {"a": "z", "b": "c"}),
        ]
    )
    assert merged == {"a": "c", "b": "c"}


def test_snapshot_aliases_and_show_fallback(aliased, config):
    assert aliased.aliases == {
        "cd": "printf",
        "ghost": "nowhere",
        "pf": "printf",
        "print": "printf",
    }
    examples, note = show_alias(aliased, "pf")
    assert {item.command for item in examples} == {"printf"}
    assert note == "pf is an alias of printf; showing printf examples"
    examples, note = show_alias(aliased, "cd")
    assert [item.command for item in examples] == ["cd"]
    assert note == "cd is an alias of printf; see also `cortex show printf`"
    assert show_alias(aliased, "ghost") == (
        [],
        "ghost is an alias of nowhere, which has no examples either",
    )
    assert show_alias(aliased, "printf")[1] == ""
    # Snapshots published before aliases existed still load.
    (aliased.path / "aliases.json").unlink()
    assert load_snapshot(config).aliases == {}


def test_show_cli_follows_aliases(cli, aliased, capsys):
    assert cli(["show", "pf", "--color", "never", "--display", "stdout"]) == 0
    captured = capsys.readouterr()
    assert "printf 'hello" in captured.out
    assert "cortex: pf is an alias of printf" in captured.err
    assert cli(["show", "ghost"]) == 1
    assert "which has no examples either" in capsys.readouterr().err
