import importlib.util
import tomllib
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/release.py"
SPEC = importlib.util.spec_from_file_location("release", SCRIPT)
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


@pytest.fixture
def release_root(tmp_path, monkeypatch):
    monkeypatch.setattr(release, "ROOT", tmp_path)
    monkeypatch.setattr(release, "VERSION_FILE", tmp_path / "pyproject.toml")
    monkeypatch.setattr(release, "CHANGELOG", tmp_path / "CHANGELOG.md")
    release.VERSION_FILE.write_text('[project]\nversion = "1.2.3"\n')
    release.CHANGELOG.write_text("# Changelog\n\n## [1.2.3] - 2026-01-01\n\nOriginal notes.\n")
    (tmp_path / "uv.lock").write_text(
        '[[package]]\nname = "cortex-cheatsheets"\nversion = "1.2.3"\n'
    )
    return tmp_path


@pytest.mark.parametrize(
    ("part", "expected"), [("patch", "1.2.4"), ("minor", "1.3.0"), ("major", "2.0.0")]
)
def test_semver_bump_and_preserved_history(release_root, part, expected):
    notes = release_root / "notes.md"
    notes.write_text("### Fixed\n\n- A reviewed fix.\n")
    release.bump(part, notes)
    assert tomllib.loads(release.VERSION_FILE.read_text())["project"]["version"] == expected
    assert f"## [{expected}]" in release.CHANGELOG.read_text()
    assert "Original notes." in release.CHANGELOG.read_text()
    assert release.notes() == "### Fixed\n\n- A reviewed fix.\n"


def test_tag_version_and_lock_must_agree(release_root):
    release.verify("v1.2.3")
    with pytest.raises(ValueError, match="does not match"):
        release.verify("v1.2.4")
    (release_root / "uv.lock").write_text(
        '[[package]]\nname = "cortex-cheatsheets"\nversion = "1.2.2"\n'
    )
    with pytest.raises(ValueError, match="differs"):
        release.verify()
