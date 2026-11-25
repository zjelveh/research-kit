import os
import subprocess
from pathlib import Path

import pytest

from build_fixture import bare_overleaf
from kitlib import KitError, stable_kit
from scaffold import cmd_attach, cmd_install_hooks, cmd_new, hooks_dir, main

MAIN = "\\documentclass{article}\n\\begin{document}\nHello.\n\\end{document}\n"


def test_new_project_hook_calls_the_stable_launcher(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"])
    hook = (p / ".git" / "hooks" / "pre-commit").read_text()
    assert f'exec "{stable_kit()}" lint_numbers.py --project "{p}" --gate slides --precommit' in hook
    assert f'"{stable_kit()}" lint_code.py --project "{p}" --precommit || exit $?' in hook
    assert hook.index("lint_code.py") < hook.index("lint_numbers.py")
    assert ".venv/bin/python" not in hook


def test_install_hooks_rewrites_both_hooks(tmp_path, capsys):
    bare = bare_overleaf(tmp_path, {"main.tex": MAIN})
    p = cmd_new("demo", tmp_path, ["r"])
    cmd_attach(str(bare), p)
    for repo in (p, p / "paper"):
        (repo / ".git" / "hooks" / "pre-commit").write_text("#!/bin/sh\n# research-kit numbers gate (old)\n")
    done = cmd_install_hooks(p)
    assert done == [p / ".git/hooks/pre-commit", p / "paper/.git/hooks/pre-commit"]
    assert "--gate paper" in (p / "paper/.git/hooks/pre-commit").read_text()
    assert "lint_code.py" not in (p / "paper/.git/hooks/pre-commit").read_text()
    assert "lint_code.py" in (p / ".git/hooks/pre-commit").read_text()
    assert str(stable_kit()) in (p / ".git/hooks/pre-commit").read_text()


def test_install_hooks_refuses_to_overwrite_a_foreign_hook(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"])
    (p / ".git/hooks/pre-commit").write_text("#!/bin/sh\necho mine\n")
    with pytest.raises(KitError, match="not the kit's"):
        cmd_install_hooks(p)
    assert "mine" in (p / ".git/hooks/pre-commit").read_text()


def test_hooks_dir_of_a_worktree_is_the_main_repos(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"])
    wt = tmp_path / "wt"
    subprocess.run(["git", "-C", str(p), "worktree", "add", "-q", str(wt)], check=True)
    assert hooks_dir(wt) == (p / ".git" / "hooks").resolve()


def test_a_repo_with_core_hookspath_is_refused(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"])
    subprocess.run(["git", "-C", str(p), "config", "core.hooksPath", str(tmp_path / "shared")], check=True)
    with pytest.raises(KitError, match="core.hooksPath"):
        cmd_install_hooks(p)
    assert not (tmp_path / "shared").exists()


def test_projects_root_default_and_its_absence(tmp_path, capsys):
    assert main(["new", "demo", "--lang", "r"]) == 2
    assert "pass --root" in capsys.readouterr().err
    personal = Path(os.environ["KIT_PERSONAL_DIR"])
    personal.mkdir()
    (personal / "config.yml").write_text(f"projects_root: {tmp_path}\n")
    assert main(["new", "demo", "--lang", "r"]) == 0
    assert (tmp_path / "demo" / ".claude" / "research.yml").is_file()
    assert f"{stable_kit()} scaffold.py attach-paper" in capsys.readouterr().out


def test_new_needs_the_stable_launcher(tmp_path, monkeypatch):
    monkeypatch.setenv("KIT_DATA_DIR", str(tmp_path / "empty"))
    with pytest.raises(KitError, match="kit setup"):
        cmd_new("demo", tmp_path, ["r"])


def test_install_hooks_refuses_a_linked_worktree(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"])
    wt = tmp_path / "wt"
    subprocess.run(["git", "-C", str(p), "worktree", "add", "-q", str(wt)], check=True)
    before = (p / ".git/hooks/pre-commit").read_text()
    with pytest.raises(KitError, match="linked worktree"):
        cmd_install_hooks(wt)
    assert (p / ".git/hooks/pre-commit").read_text() == before


def test_install_hooks_checks_both_hooks_before_writing_either(tmp_path):
    bare = bare_overleaf(tmp_path, {"main.tex": MAIN})
    p = cmd_new("demo", tmp_path, ["r"])
    cmd_attach(str(bare), p)
    old = "#!/bin/sh\n# research-kit numbers gate (old)\n"
    (p / ".git/hooks/pre-commit").write_text(old)
    (p / "paper/.git/hooks/pre-commit").write_text("#!/bin/sh\necho mine\n")
    with pytest.raises(KitError, match="not the kit's"):
        cmd_install_hooks(p)
    assert (p / ".git/hooks/pre-commit").read_text() == old


def test_a_paper_clone_without_the_kit_hook_is_skipped_with_a_message(tmp_path, capsys):
    bare = bare_overleaf(tmp_path, {"main.tex": MAIN})
    p = cmd_new("demo", tmp_path, ["r"])
    cmd_attach(str(bare), p)
    (p / "paper/.git/hooks/pre-commit").unlink()
    capsys.readouterr()
    assert cmd_install_hooks(p) == [p / ".git/hooks/pre-commit"]
    out = capsys.readouterr().out
    assert "skipped" in out and "attach-paper" in out
    assert not (p / "paper/.git/hooks/pre-commit").exists()


def test_a_project_without_a_paper_gets_only_the_code_hook(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"])
    assert cmd_install_hooks(p) == [p / ".git/hooks/pre-commit"]


def test_a_bad_projects_root_is_named(tmp_path, capsys):
    personal = Path(os.environ["KIT_PERSONAL_DIR"])
    personal.mkdir()
    for value, words in (("rel", "must be an absolute path"), (str(tmp_path / "nope"), "is not a directory")):
        (personal / "config.yml").write_text(f"projects_root: {value}\n")
        assert main(["new", "demo", "--lang", "r"]) == 2
        err = capsys.readouterr().err
        assert "projects_root" in err and words in err


def test_the_printed_attach_command_is_quoted(tmp_path, capsys):
    import shlex
    root = tmp_path / "my projects"
    root.mkdir()
    assert main(["new", "demo", "--root", str(root), "--lang", "r"]) == 0
    assert f"--project {shlex.quote(str(root / 'demo'))}" in capsys.readouterr().out


def test_the_code_gate_blocks_a_typed_value(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"])
    (p / "analysis" / "run.R").write_text('x <- subset(d, year > 2019)\n')
    subprocess.run(["git", "-C", str(p), "add", "analysis/run.R"], check=True)
    proc = subprocess.run(["git", "-C", str(p), "commit", "-q", "-m", "typed"], capture_output=True, text=True)
    assert proc.returncode != 0 and "analysis/run.R:1: typed number 2019" in proc.stdout + proc.stderr


def test_install_hooks_notes_missing_parameter_files(tmp_path, capsys):
    p = cmd_new("demo", tmp_path, ["r"])
    subprocess.run(["git", "-C", str(p), "rm", "-q", "analysis/params.yml"], check=True)
    subprocess.run(["git", "-C", str(p), "commit", "-q", "-m", "no parameters"], check=True)
    cmd_install_hooks(p)
    assert "note: the code gate is on, but analysis/params.yml is missing" in capsys.readouterr().out
