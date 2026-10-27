import json

import pytest

from cortex.cli import main
from cortex.model import CortexError
from cortex.status import collect, detail, table
from cortex.sync import run


def by_id(rows):
    return {row["id"]: row for row in rows}


def test_status_before_any_sync(config, local_source):
    local_source()
    rows = by_id(collect(config))
    assert rows["sample"]["status"] == "never synced"
    assert rows["sample"]["parsed"] is None and rows["sample"]["kept"] == 0
    assert rows["custom"]["status"] == "local"
    assert "never synced" in table(list(rows.values()), colored=False)


def test_status_counts_reasons_and_missing_commands(config, local_source):
    local_source(
        text="# Print a greeting:\nprintf 'hello\\n'\n\n# Include headers:\n-i\n\n"
        "# Missing tool:\ncortex-missing-tool --flag\n"
    )
    assert run(config)[0] == 0
    row = by_id(collect(config))["sample"]
    assert row["status"] == "updated" and len(row["revision"]) == 64
    assert (row["parsed"], row["rejected"], row["kept"]) == (2, 1, 1)
    reasons = {item["reason"]: item for item in row["reasons"]}
    assert reasons["flag-only fragment"]["sample"] == "printf:5"
    assert reasons["unavailable"]["count"] == 1
    assert row["missing_commands"] == [{"command": "cortex-missing-tool", "count": 1}]
    text = detail(row, colored=False)
    assert "2 parsed, 1 rejected, 1 kept" in text
    assert "cortex-missing-tool" in text and "\x1b" not in text


def test_unlicensed_sources_warn_during_sync(config, local_source):
    source, _ = local_source()
    assert run(config)[1]["warnings"] == []
    source.license = "none-declared"
    report = run(config)[1]
    assert report["warnings"] == [
        "sample: upstream declares no content license; do not redistribute its examples"
    ]


def test_sources_cli_is_offline_and_rejects_unknown_ids(tmp_path, monkeypatch, capsys):
    for variable, subdir in [
        ("XDG_CONFIG_HOME", "config"),
        ("XDG_CACHE_HOME", "cache"),
        ("XDG_DATA_HOME", "data"),
    ]:
        monkeypatch.setenv(variable, str(tmp_path / subdir))
    assert main(["sources", "--json"]) == 0
    rows = by_id(json.loads(capsys.readouterr().out))
    assert rows["eg"]["enabled"] and not rows["devhints"]["enabled"]
    assert rows["devhints"]["license"] == "none-declared"
    assert not (tmp_path / "cache/cortex/sources").exists()
    assert main(["sources", "tldr", "--color", "never"]) == 0
    assert "never synced" in capsys.readouterr().out
    assert main(["sources", "nope"]) == 1
    assert "Unknown source: nope" in capsys.readouterr().err


def test_corrupt_status_file_is_reported(config, local_source):
    local_source()
    config.paths.cache.mkdir(parents=True)
    (config.paths.cache / "last-sync.json").write_text("{")
    with pytest.raises(CortexError, match="last-sync.json"):
        collect(config)
