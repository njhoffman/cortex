from cortex.adapters import parse
from cortex.config import Source


def test_tldr_platform_paths_and_placeholders(tmp_path):
    for platform in ("common", "linux", "osx", "windows"):
        directory = tmp_path / "pages" / platform
        directory.mkdir(parents=True)
        (directory / "git-commit.md").write_text(
            "# git commit\n\n> Commit changes.\n\n- Make a commit:\n\n`git commit -m {{message}}`\n"
        )
    source = Source("tldr", "test", "tldr", include=["pages/common/*.md", "pages/linux/*.md"])
    result = parse(tmp_path, source, "fixture-revision")
    assert len(result.examples) == 2
    assert result.examples[0].template == "git commit -m {{message}}"
    assert result.examples[0].placeholders == ["message"]
    assert result.examples[0].origins[0].revision == "fixture-revision"


def test_commented_descriptions_do_not_bleed_between_examples(tmp_path):
    (tmp_path / "printf").write_text(
        "---\ntags: [shell]\n---\n# First:\nprintf first\n\n"
        "# Second\n# with more context:\nprintf second\n"
    )
    result = parse(tmp_path, Source("cheat", "test", "cheat", include=["*"]), "rev")
    assert [item.description for item in result.examples] == ["First", "Second with more context"]
    assert result.examples[0].tags == ["shell"]


def test_navi_variables_are_data_and_foreign_tags_are_rejected(tmp_path):
    sentinel = tmp_path / "sentinel"
    (tmp_path / "tools.cheat").write_text(
        "% files, linux\n# Find files:\nfind <directory> -name <pattern>\n\n"
        f"$ directory: touch {sentinel}\n  echo another line\n\n"
        "% macos\n# Copy:\npbcopy file\n"
    )
    source = Source("navi", "test", "navi", include=["**/*.cheat"])
    result = parse(tmp_path, source, "rev")
    assert len(result.examples) == 1
    assert result.examples[0].template == "find <directory> -name <pattern>"
    assert result.diagnostics
    assert not sentinel.exists()


def test_source_paths_and_language_namespaces(tmp_path):
    (tmp_path / "sheets/_python").mkdir(parents=True)
    (tmp_path / "sheets/_python/intro").write_text("# Skip:\nprint('x')\n")
    (tmp_path / "sheets/printf").write_text("# Print:\nprintf hello\n")
    source = Source("sheets", "test", "cheat-sheets", include=["sheets/*"], exclude=["sheets/_*"])
    result = parse(tmp_path, source, "rev")
    assert len(result.examples) == 1
    assert result.examples[0].origins[0].path == "sheets/printf"


def test_continuations_preserved_and_prompts_removed(tmp_path):
    (tmp_path / "printf").write_text("# Print:\n$ printf '%s' \\\n  hello\n")
    result = parse(tmp_path, Source("test", "test", "cheat", include=["*"]), "rev")
    assert result.examples[0].template == "printf '%s' \\\n  hello"


def test_symlink_outside_source_is_not_read(tmp_path):
    outside = tmp_path / "outside"
    outside.write_text("# Print:\nprintf should-not-appear\n")
    root = tmp_path / "source"
    root.mkdir()
    (root / "printf").symlink_to(outside)
    result = parse(root, Source("test", "test", "cheat", include=["*"]), "rev")
    assert not result.examples
