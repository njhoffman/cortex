import hashlib
import json
import tomllib
from pathlib import Path

from cortex.adapters import parse
from cortex.config import Source

FIXTURES = Path(__file__).parent / "fixtures"


def test_revision_pinned_upstream_samples():
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    registry = tomllib.loads((Path(__file__).parents[1] / "src/cortex/sources.toml").read_text())[
        "sources"
    ]
    assert set(manifest) == {"tldr", "cheat", "navi", "cheat-sheets", "eg", "cheatsheets-zip"}
    for name, fixture in manifest.items():
        root = FIXTURES / name
        assert len(fixture["revision"]) == 40
        for relative, checksum in fixture["files"].items():
            assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == checksum
        source = Source(id=name, **registry[name])
        result = parse(root, source, fixture["revision"])
        assert len(result.examples) == fixture["expected_examples"]
        assert result.examples[0].template == fixture["first_template"]
        assert all(
            example.origins[0].revision == fixture["revision"] for example in result.examples
        )
