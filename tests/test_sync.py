import fcntl
import json
import os
import subprocess
from pathlib import Path

import pytest
from conftest import write_executable

from cortex.cache import SourceCache
from cortex.config import Source
from cortex.model import CortexError
from cortex.sync import run


def current(config):
    return config.paths.data / "current"


def records(config):
    return [
        json.loads(line) for line in (current(config) / "catalog.jsonl").read_text().splitlines()
    ]


def test_full_sync_unchanged_and_offline_determinism(config, local_source):
    local_source()
    status, report = run(config)
    assert status == 0 and report["published"]
    assert report["counts"]["retained"] == 1
    original = {
        name: (current(config) / name).read_bytes()
        for name in ["catalog.jsonl", "commands.md", "commands.json"]
    }
    assert run(config)[1]["sources"][0]["status"] == "unchanged"
    assert run(config, offline=True, force=True)[0] == 0
    for name, data in original.items():
        assert (current(config) / name).read_bytes() == data


def test_availability_recomputed_without_source_change(config, local_source, tmp_path, monkeypatch):
    local_source(text="# Example:\ncortex-test-program --hello\n")
    binary_directory = tmp_path / "bin"
    binary_directory.mkdir()
    monkeypatch.setenv("PATH", str(binary_directory))
    assert run(config)[1]["counts"]["retained"] == 0
    write_executable(binary_directory / "cortex-test-program")
    assert run(config, offline=True)[1]["counts"]["retained"] == 1
    (binary_directory / "cortex-test-program").unlink()
    assert run(config, offline=True)[1]["counts"]["retained"] == 0
    inventory = json.loads((config.paths.cache / "source-inventory.json").read_text())
    assert inventory["sample"] == ["cortex-test-program"]


def test_cross_source_dedup_and_custom_priority(config, local_source):
    local_source("one", "# Upstream one:\nprintf same\n")
    local_source("two", "# Upstream two:\nprintf same\n# Different:\nprintf other\n")
    custom = config.paths.data / "custom"
    custom.mkdir(parents=True)
    addition = custom / "printf.cheat"
    addition.write_text("# My preferred description:\nprintf same\n")
    original = addition.read_bytes()
    status, report = run(config)
    assert status == 0 and report["counts"]["duplicate"] == 2
    same = next(record for record in records(config) if record["template"] == "printf same")
    assert same["description"] == "My preferred description"
    assert len(same["origins"]) == 3
    assert addition.read_bytes() == original


def test_persistent_exclusion_survives_description_change(config, local_source):
    _, root = local_source(text="# Before:\nprintf same\n")
    run(config)
    stable_id = records(config)[0]["id"]
    (config.paths.data / "exclusions.toml").write_text(f'ids = ["{stable_id}"]\n')
    (root / "printf").write_text("# After:\nprintf same\n")
    status, report = run(config)
    assert status == 0 and report["counts"]["excluded"] == 1
    assert records(config) == []


def test_partial_failure_retains_stale_source(config, local_source):
    _, root = local_source("one")
    local_source("two", "# Other:\nprintf other\n")
    run(config)
    root.rename(root.with_name("moved"))
    status, report = run(config)
    assert status == 2
    assert report["sources"][0]["status"] == "stale"
    assert len(records(config)) == 2


def test_every_online_failure_does_not_replace_active_snapshot(config, local_source):
    _, root = local_source()
    run(config)
    previous = current(config).resolve()
    root.rename(root.with_name("moved"))
    status, report = run(config)
    assert status == 1 and not report["published"]
    assert current(config).resolve() == previous
    assert run(config, offline=True)[0] == 0


def test_invalid_empty_refresh_keeps_last_good_cache(config, local_source):
    source, root = local_source()
    run(config)
    revision = SourceCache(config, source).load()[0]["revision"]
    (root / "printf").write_text("not a valid described cheatsheet")
    assert run(config)[0] == 1
    assert SourceCache(config, source).load()[0]["revision"] == revision


def test_upstream_delete_and_disabled_source_prune(config, local_source):
    source, root = local_source("one", "# First:\nprintf first\n# Deleted:\nprintf deleted\n")
    local_source("two", "# Second:\nprintf second\n")
    run(config)
    (root / "printf").write_text("# First:\nprintf first\n")
    assert run(config)[1]["counts"]["retained"] == 2
    source.enabled = False
    assert run(config)[1]["counts"]["retained"] == 1
    assert records(config)[0]["template"] == "printf second"


def test_missing_caches_and_selected_source(config, local_source):
    local_source("one")
    local_source("two")
    status, report = run(config, source_ids=["one"])
    assert status == 2
    assert report["sources"][1]["status"] == "missing"
    assert run(config, offline=True)[0] == 2
    with pytest.raises(CortexError, match="Unknown or disabled"):
        run(config, source_ids=["unknown"])


def test_offline_first_run_no_publication(config, local_source):
    local_source()
    assert run(config, offline=True)[0] == 1
    assert not current(config).exists()


def test_lock_and_failed_publication_preserve_snapshot(config, local_source, monkeypatch):
    local_source()
    run(config)
    previous = current(config).resolve()
    with (config.paths.data / ".sync.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(CortexError, match="already running"):
            run(config)
    original_replace = os.replace

    def fail_publication(source, destination):
        if Path(destination).name == "current":
            raise OSError("simulated publication failure")
        return original_replace(source, destination)

    monkeypatch.setattr(os, "replace", fail_publication)
    with pytest.raises(OSError, match="simulated"):
        run(config, offline=True)
    assert current(config).resolve() == previous


def test_parser_configuration_change_reparses_cached_source(config, local_source):
    source, _ = local_source()
    run(config)
    source.priority = 5
    status, report = run(config, offline=True)
    assert status == 0 and report["counts"]["retained"] == 1
    assert (
        SourceCache(config, source).load()[0]["fingerprint"]
        == SourceCache(config, source).fingerprint
    )


def test_git_refresh_uses_pinned_commits_and_prunes_deleted_examples(config, tmp_path):
    root = tmp_path / "git-upstream"
    root.mkdir()

    def git(*args):
        return (
            subprocess.check_output(
                [
                    "git",
                    "-c",
                    "user.name=Cortex Tests",
                    "-c",
                    "user.email=tests@example.invalid",
                    *args,
                ],
                cwd=root,
                stderr=subprocess.PIPE,
            )
            .decode()
            .strip()
        )

    git("init", "-q", "--initial-branch=main")
    (root / "printf").write_text("# First:\nprintf first\n# Second:\nprintf second\n")
    (root / ".github").mkdir()
    (root / ".github/LICENSE.txt").write_text("Fixture license notice\n")
    git("add", "printf")
    git("add", ".github/LICENSE.txt")
    git("commit", "-qm", "Initial fixture")
    first = git("rev-parse", "HEAD")
    source = Source(
        "git-test",
        str(root),
        "cheat",
        include=["*"],
        license="test",
        exclude=[".*", "LICENSE*"],
        license_files=[".github/LICENSE.txt"],
    )
    config.sources.append(source)
    status, report = run(config)
    assert status == 0 and report["sources"][0]["revision"] == first
    assert (
        current(config) / "licenses/git-test/.github/LICENSE.txt"
    ).read_text() == "Fixture license notice\n"
    assert run(config)[1]["sources"][0]["status"] == "unchanged"
    (root / "printf").write_text("# First:\nprintf first\n")
    git("commit", "-qam", "Delete second example")
    second = git("rev-parse", "HEAD")
    assert run(config)[1]["sources"][0]["revision"] == second
    assert len(records(config)) == 1
    source.ref = first
    assert run(config)[1]["sources"][0]["revision"] == first
    assert len(records(config)) == 2
