import json

import pytest

from cortex import __version__
from cortex.cli import main
from cortex.config import load
from cortex.model import CortexError


def test_starter_preserves_user_configuration(config):
    first = load(config.paths)
    assert len([source for source in first.sources if source.enabled]) == 4
    content = config.paths.config.read_text() + '\n[categories]\nprintf = "my-shell"\n'
    config.paths.config.write_text(content)
    assert load(config.paths).categories["printf"] == "my-shell"
    assert config.paths.config.read_text() == content


@pytest.mark.parametrize(
    "content",
    [
        "[sources.devhints]\nenabled = true\n",
        "[sync]\nconcurrency = 0\n",
        '[general]\nplatform = "windows"\n',
        "[general]\nonly_available = false\n",
        '[sources."../escape"]\nurl = "x"\nadapter = "cheat"\n',
        '[sources.cheat]\ninclude = ["../escape"]\n',
    ],
)
def test_invalid_configuration_fails_before_fetch(config, content):
    config.paths.config.write_text(content)
    with pytest.raises(CortexError):
        load(config.paths)


def test_cli_json_and_xdg_isolation(tmp_path, monkeypatch, capsys):
    for variable, subdir in [
        ("XDG_CONFIG_HOME", "config"),
        ("XDG_CACHE_HOME", "cache"),
        ("XDG_DATA_HOME", "data"),
    ]:
        monkeypatch.setenv(variable, str(tmp_path / subdir))
    status = main(["sync", "--offline", "--json"])
    output = capsys.readouterr()
    assert status == 1
    assert json.loads(output.out)["published"] is False
    assert (tmp_path / "config/cortex/config.toml").is_file()
    assert "No usable inputs" in output.err


@pytest.mark.parametrize("prefix", [[], ["sync"]])
@pytest.mark.parametrize("flag", ["-v", "--version"])
def test_version_flags(prefix, flag, capsys):
    with pytest.raises(SystemExit) as result:
        main([*prefix, flag])
    assert result.value.code == 0
    assert capsys.readouterr().out.strip() == f"cortex {__version__}"


@pytest.mark.parametrize("prefix", [[], ["sync"]])
@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_help_flags(prefix, flag, capsys):
    with pytest.raises(SystemExit) as result:
        main([*prefix, flag])
    assert result.value.code == 0
    assert "usage: cortex" in capsys.readouterr().out
