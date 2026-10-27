import pytest
from conftest import write_executable

from cortex.model import Example
from cortex.shell import Availability, Unsupported, inspect


@pytest.mark.parametrize(
    ("template", "primary", "required"),
    [
        ("apt-get update", "apt-get", ["apt-get"]),
        ("git commit -m 'x'", "git", ["git"]),
        ("FOO=bar printf '%s' hello", "printf", ["printf"]),
        ("cat file | grep 'some text'", "cat", ["cat", "grep"]),
        ("sudo -u root env X=1 cat file", "cat", ["cat", "env", "sudo"]),
        ('echo "$(missing-command file)"', "echo", ["echo", "missing-command"]),
        ("cat <(sort file)", "cat", ["cat", "sort"]),
        ("printf ok && cat file", "printf", ["cat", "printf"]),
        ("ls {{[-a|--all]}} {{path/to/directory}}", "ls", ["ls"]),
        ("ffmpeg -i <video> <image.png>", "ffmpeg", ["ffmpeg"]),
        ("awk '{print $1}' file", "awk", ["awk"]),
        ("command -v not-installed", "command", ["command"]),
    ],
)
def test_structural_dependencies(template, primary, required):
    result = inspect(template, "bash")
    assert result.command == primary
    assert result.required == required


@pytest.mark.parametrize(
    "template",
    [
        "$PROGRAM arg",
        "<command> file",
        "sh -c 'missing-command'",
        "eval 'missing-command'",
        "xargs missing-command",
        "PATH=/other cat file",
        "env PATH=/other cat file",
        "sudo -i cat file",
        "ssh host 'missing-command'",
        "find . -exec missing-command '{}' ';'",
        "sed -i '' s/a/b/ file",
        "pbcopy file",
        "for x in *; do echo $x; done",
        "./local-script file",
        "builtin not-a-builtin",
        "cat <<EOF\nhello\nEOF",
        "#!/{{path/to/tcc}} -run",
        ". {{path/to/file}}",
        ".  end active edit",
        "sudo . file",
    ],
)
def test_unsupported_is_not_guessed(template):
    with pytest.raises(Unsupported):
        inspect(template, "bash")


def test_pipeline_requires_every_executable(tmp_path):
    write_executable(tmp_path / "cat")
    example = Example("Filter", "cat file | missing-command", [])
    assert Availability("bash", str(tmp_path)).apply(example) == "unavailable: missing-command"


def test_executable_permissions_and_builtins(tmp_path):
    (tmp_path / "not-executable").write_text("data")
    availability = Availability("bash", str(tmp_path))
    assert availability.has("cd")
    assert not availability.has("not-executable")
    assert not availability.has("missing-command")


def test_wrappers_cannot_launch_a_shell_only_builtin(tmp_path):
    write_executable(tmp_path / "env")
    example = Example("Change directory", "env cd /tmp", [])
    assert Availability("bash", str(tmp_path)).apply(example) == "unavailable: cd"


def test_builtin_dialect_and_process_substitution():
    assert Availability("bash", "").has("shopt")
    assert not Availability("zsh", "").has("shopt")
    with pytest.raises(Unsupported):
        inspect("cat <(sort file)", "sh")


def test_no_shell_input_is_executed(tmp_path):
    target = tmp_path / "must-not-exist"
    result = inspect(f"echo $(touch {target})", "bash")
    assert "touch" in result.required
    assert not target.exists()
