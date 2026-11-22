import pytest
from build_fixture import git, init_repo, minimal_project, write
from lint_numbers import main

DOC = "\\documentclass{article}\n\\begin{document}\n{body}\n\\end{document}\n"


def paper_project(tmp_path, body="Hello.", baseline="0"):
    p = minimal_project(tmp_path)
    write(p / "paper" / "main.tex", DOC.replace("{body}", body))
    write(p / "paper" / ".lint_baseline", baseline + "\n")
    init_repo(p / "paper", "main")
    init_repo(p)  # code repo; paper/ would be gitignored by the scaffold
    return p


def run(p, *args):
    return main(["--project", str(p), *args])


def test_worktree_ok(tmp_path, capsys):
    p = paper_project(tmp_path, "We had 3 cases.", "1")
    assert run(p, "--gate", "paper") == 0
    assert "count=1 baseline=1 ok" in capsys.readouterr().out


def test_worktree_regression(tmp_path, capsys):
    p = paper_project(tmp_path, "We had 3 cases and 4 more.", "1")
    assert run(p, "--gate", "paper") == 1
    out = capsys.readouterr().out
    assert "REGRESSION" in out and "main.tex:3: 4" in out


def test_missing_baseline_is_error(tmp_path, capsys):
    p = paper_project(tmp_path)
    (p / "paper" / ".lint_baseline").unlink()
    assert run(p, "--gate", "paper") == 2
    assert "baseline file missing" in capsys.readouterr().err


def test_non_integer_baseline_is_error(tmp_path, capsys):
    p = paper_project(tmp_path, baseline="")
    assert run(p, "--gate", "paper") == 2
    assert "one non-negative integer" in capsys.readouterr().err


def test_git_ref_reads_files_and_baseline_at_ref(tmp_path):
    p = paper_project(tmp_path, "We had 3 cases.", "0")   # HEAD: 1 number, baseline 0
    write(p / "paper" / ".lint_baseline", "5\n")           # worktree baseline differs
    assert run(p, "--gate", "paper") == 0                  # worktree: 1 <= 5
    assert run(p, "--gate", "paper", "--git-ref", "HEAD") == 1  # ref: 1 > 0


def test_precommit_blocks_staged_regression(tmp_path):
    p = paper_project(tmp_path, "Hello.", "0")
    write(p / "paper" / "main.tex", DOC.replace("{body}", "We had 3 cases."))
    git(p / "paper", "add", "main.tex")
    assert run(p, "--gate", "paper", "--precommit") == 1


def test_precommit_lowers_and_stages_baseline(tmp_path):
    p = paper_project(tmp_path, "We had 3 cases.", "3")
    assert run(p, "--gate", "paper", "--precommit") == 0
    assert (p / "paper" / ".lint_baseline").read_text() == "1\n"
    assert ".lint_baseline" in git(p / "paper", "diff", "--cached", "--name-only")


def test_paper_gate_with_no_files_is_error(tmp_path, capsys):
    p = paper_project(tmp_path)
    (p / "paper" / "main.tex").unlink()
    assert run(p, "--gate", "paper") == 2
    assert "no files match lint.paper.globs" in capsys.readouterr().err


def test_slides_gate_with_no_files_is_zero(tmp_path, capsys):
    p = paper_project(tmp_path)
    assert run(p, "--gate", "slides") == 0
    assert "count=0 baseline=0 ok" in capsys.readouterr().out


def test_write_baseline(tmp_path):
    p = paper_project(tmp_path, "We had 3 cases and 4 more.", "0")
    assert run(p, "--gate", "paper", "--write-baseline") == 0
    assert (p / "paper" / ".lint_baseline").read_text() == "2\n"


def test_unreadable_file_is_named_error(tmp_path, capsys):
    p = paper_project(tmp_path)
    (p / "paper" / "main.tex").write_bytes(b"\xff\xfe bad bytes")
    assert run(p, "--gate", "paper") == 2
    assert "main.tex: cannot read" in capsys.readouterr().err


def test_precommit_reads_baseline_from_index(tmp_path):
    p = paper_project(tmp_path, "Hello.", "1")       # committed: 0 numbers, baseline 1
    write(p / "paper" / ".lint_baseline", "0\n")       # unstaged worktree edit
    assert run(p, "--gate", "paper", "--precommit") == 0
    assert git(p / "paper", "show", ":.lint_baseline").strip() == "0"   # lowered and staged


def test_precommit_non_utf8_staged_file_is_named_error(tmp_path, capsys):
    p = paper_project(tmp_path)
    (p / "paper" / "main.tex").write_bytes(b"\\begin{document}caf\xe9\\end{document}")
    git(p / "paper", "add", "main.tex")
    assert run(p, "--gate", "paper", "--precommit") == 2
    assert "not valid UTF-8" in capsys.readouterr().err


def test_precommit_non_ascii_filename_is_linted(tmp_path):
    p = paper_project(tmp_path, "Hello.", "0")
    write(p / "paper" / "sections" / "é.tex", "We had 3 cases.")
    git(p / "paper", "add", "-A")
    assert run(p, "--gate", "paper", "--precommit") == 1


def test_precommit_and_git_ref_are_exclusive(tmp_path):
    p = paper_project(tmp_path)
    with pytest.raises(SystemExit):
        run(p, "--gate", "paper", "--precommit", "--git-ref", "HEAD")
