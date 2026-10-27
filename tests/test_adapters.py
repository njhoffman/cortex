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


def test_eg_prompts_output_and_platform_sections(tmp_path):
    (tmp_path / "eg/examples").mkdir(parents=True)
    (tmp_path / "eg/examples/du.md").write_text(
        "# du\n\nshow size in human readable units\n\n    du -h foo.txt\n\n\n"
        "# Basic Usage\n\nPrompted examples drop their output:\n\n"
        "    $ du -sh dir\n    4.0K    dir\n\n"
        "## OSX\n\nOSX-only flag:\n\n    du -A foo.txt\n\n"
        "## Linux\n\nApparent size:\n\n    du --apparent-size foo.txt\n"
    )
    (tmp_path / "eg/examples/aliases.json").write_text('{"link": "ln"}')
    result = parse(tmp_path, Source("eg", "test", "eg", include=["eg/examples/*.md"]), "rev")
    assert [(item.description, item.template) for item in result.examples] == [
        ("show size in human readable units", "du -h foo.txt"),
        ("Prompted examples drop their output", "du -sh dir"),
        ("Apparent size", "du --apparent-size foo.txt"),
    ]
    assert [item.reason for item in result.diagnostics] == ["non-Linux section"]
    assert result.examples[1].origins[0].line == 12


def test_markdown_fences_comments_and_flag_fragments(tmp_path):
    (tmp_path / "curl.md").write_text(
        "---\ntitle: cURL\ncategories:\n  - Linux Command\n---\n\n"
        "## Options {.cols-2}\n\n```bash\n-i  # --include: include headers\n-L\n```\n\n"
        "### Requests\n{: .-prime}\n\nFetch a page with **headers**\n\n"
        "```shell script {.wrap}\n$ curl -i https://example.com\nHTTP/2 200\n```\n\nor\n\n"
        "```shell script\n$ curl --include https://example.com\n```\n\n"
        "```bash\n# Follow redirects\ncurl -L https://example.com\n"
        "curl -sSL https://example.com | sh  # pipe to a shell\n"
        "curl -X POST \\\n  -d 'a=1' https://example.com\n```\n\n"
        "```js\nfetch('https://example.com')\n```\n"
    )
    source = Source("zip", "test", "cheatsheets-zip", include=["*.md"])
    result = parse(tmp_path, source, "rev")
    assert [(item.description, item.template) for item in result.examples] == [
        ("Fetch a page with headers", "curl -i https://example.com"),
        ("Fetch a page with headers", "curl --include https://example.com"),
        ("Follow redirects", "curl -L https://example.com"),
        ("pipe to a shell", "curl -sSL https://example.com | sh"),
        ("Follow redirects", "curl -X POST \\\n  -d 'a=1' https://example.com"),
    ]
    assert [item.reason for item in result.diagnostics] == ["flag-only fragment"] * 2


def test_markdown_tables_need_command_and_description_columns(tmp_path):
    (tmp_path / "grep.md").write_text(
        "## Options\n\n| Option | Example | Operation |\n| --- | --- | --- |\n"
        "| `-i` | grep -i ^DA demo.txt | Ignore _case_ |\n"
        "| `-l` | grep -l 'robot' /var/log/\\* | List [files](/x) |\n"
        "| `-E` | `grep -E 'a\\|b' file` | Extended regex |\n\n"
        "## Wildcards\n\n| - | - |\n| --- | --- |\n| `.` | Any character. |\n\n"
        "## Windows\n\n| Command | Description |\n| --- | --- |\n| `findstr x` | Search |\n"
    )
    source = Source("devhints", "test", "devhints", include=["*.md"])
    result = parse(tmp_path, source, "rev")
    assert [(item.description, item.template) for item in result.examples] == [
        ("Ignore case", "grep -i ^DA demo.txt"),
        ("List files", "grep -l 'robot' /var/log/*"),
        ("Extended regex", "grep -E 'a|b' file"),
    ]
    assert [item.reason for item in result.diagnostics] == ["non-Linux section"]


def test_flag_fragments_rejected_for_commented_sources(tmp_path):
    (tmp_path / "curl").write_text("# Include headers:\n-i\n\n# Fetch:\ncurl example.com\n")
    result = parse(tmp_path, Source("test", "test", "cheat", include=["*"]), "rev")
    assert [item.template for item in result.examples] == ["curl example.com"]
    assert [item.reason for item in result.diagnostics] == ["flag-only fragment"]


def test_trailing_comments_respect_quotes():
    from cortex.adapters import trailing_comment

    assert trailing_comment("jq '.name' data.json  # Get one field") == (
        "jq '.name' data.json",
        "Get one field",
    )
    assert trailing_comment("echo 'a # b' \"c # d\"") is None
    assert trailing_comment("echo a\\ # b") is None
    assert trailing_comment("echo ${#array[@]} $#") is None
    assert trailing_comment("git push origin #  ") is None


def test_awesome_scripts_sections_and_comment_scope(tmp_path):
    (tmp_path / "tools").mkdir()
    rule = "#" * 30
    (tmp_path / "tools/jq.sh").write_text(
        f"#!/bin/bash\n{rule}\n# JQ\n# DOCUMENTATION: https://example.com\n{rule}\n\n"
        "jq '.' data.json          # Pretty-print JSON\n"
        "jq -r '.name' data.json\n\n"
        "# write raw output\njq -r '.a' f.json\njq --raw-output '.a' f.json\n\n"
        "jq -c '.[]' f.json \\\n  data.json  # not a description\n"
    )
    (tmp_path / "bash.sh").write_text(
        f"{rule}\n# SHORTCUTS\n{rule}\n\nCTRL+A  # move to beginning of line\n\n"
        "CTRL+E  # move to end of line\n\n"
        f"{rule}\n# FILE COMMANDS\n{rule}\n\nls -a  # lists all files\n"
        f"# {'*' * 20}\n# Settings\n# {'*' * 20}\n\nserver {{\n"
    )
    source = Source(
        "awesome",
        "test",
        "awesome-cheatsheets",
        include=["bash.sh", "tools/*.sh"],
        sections={"bash.sh": ["file commands"]},
    )
    result = parse(tmp_path, source, "rev")
    assert [(item.description, item.template) for item in result.examples] == [
        ("lists all files", "ls -a"),
        ("Pretty-print JSON", "jq '.' data.json"),
        ("write raw output", "jq -r '.a' f.json"),
        ("write raw output", "jq --raw-output '.a' f.json"),
    ]
    reasons = [(item.path, item.line, item.reason) for item in result.diagnostics]
    assert reasons == [
        ("bash.sh", 5, "unselected section: SHORTCUTS"),
        ("bash.sh", 18, "unselected section: Settings"),
        ("tools/jq.sh", 8, "missing description or command"),
        ("tools/jq.sh", 14, "missing description or command"),
    ]


def test_awesome_markdown_accepts_bare_fences_and_bullets(tmp_path):
    (tmp_path / "kubernetes.md").write_text(
        "# Kubernetes\n\n* View config\n```\nkubectl config view\n```\n\n"
        "1. Get pods\n```yaml\nkind: Pod\n```\n"
    )
    result = parse(tmp_path, Source("a", "test", "awesome-cheatsheets", include=["*.md"]), "rev")
    assert [(item.description, item.template) for item in result.examples] == [
        ("View config", "kubectl config view")
    ]
    # Other Markdown sources still ignore fences without a language.
    result = parse(tmp_path, Source("z", "test", "cheatsheets-zip", include=["*.md"]), "rev")
    assert not result.examples


def test_alias_metadata_from_tldr_and_eg(tmp_path):
    pages = tmp_path / "pages/common"
    pages.mkdir(parents=True)
    alias = "# {0}\n\n> This command is an alias of {1}`{2}`.\n\n- View docs:\n\n`tldr {2}`\n"
    (pages / "egrep.md").write_text(alias.format("egrep", "", "grep --extended-regexp"))
    (pages / "gls.md").write_text(alias.format("gls", "GNU ", "ls"))
    (pages / "docker-stop.md").write_text(alias.format("docker stop", "", "docker container stop"))
    (pages / "..md").write_text(alias.format(".", "", "source"))
    result = parse(tmp_path, Source("tldr", "test", "tldr", include=["pages/*/*.md"]), "rev")
    assert result.aliases == {"egrep": "grep", "gls": "ls", ".": "source"}

    examples = tmp_path / "eg/examples"
    examples.mkdir(parents=True)
    (examples / "aliases.json").write_text('{"netcat": "nc", "bad": 3, "nc": "nc"}')
    include = ["eg/examples/aliases.json"]
    result = parse(tmp_path, Source("eg", "test", "eg", include=include), "rev")
    assert result.aliases == {"netcat": "nc"}
    (examples / "aliases.json").write_text("[1]")
    result = parse(tmp_path, Source("eg", "test", "eg", include=include), "rev")
    assert [item.reason for item in result.diagnostics] == ["invalid aliases: not an object"]
