from pathlib import Path

import pytest

from cortex.config import Config, Paths, Source


@pytest.fixture
def config(tmp_path):
    return Config(Paths(tmp_path / "config.toml", tmp_path / "cache", tmp_path / "data"), [])


@pytest.fixture
def local_source(config, tmp_path):
    def create(name="sample", text="# Print a greeting:\nprintf 'hello\\n'\n"):
        root = tmp_path / f"upstream-{name}"
        root.mkdir(exist_ok=True)
        (root / "printf").write_text(text)
        source = Source(name, str(root), "cheat", transport="local", include=["*"], license="test")
        config.sources.append(source)
        return source, root

    return create


def write_executable(path: Path):
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(0o755)
