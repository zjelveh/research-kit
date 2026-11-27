import hashlib

import pytest
import yaml

import frozen
from build_fixture import CONFIG, git, minimal_project, write


@pytest.fixture
def project(tmp_path):
    p = minimal_project(tmp_path, CONFIG)
    write(p / "analysis" / "freeze_es.py", "es.to_csv('out/es.csv')\n")
    write(p / "out" / "es.csv", "a,b\n1,2\n")
    git(p, "init", "-q", "-b", "main")
    git(p, "add", ".claude", "state", "analysis")
    git(p, "commit", "-q", "-m", "init")
    return p


def run(p, *args):
    return frozen.main([*args, "--project", str(p)])


def test_add_records_the_file_with_its_hash(project, capsys):
    assert run(project, "add", "out/es.csv", "--made-by", "analysis/freeze_es.py",
               "--why", "Its inputs are\n  outside the repository.") == 0
    assert "out/es.csv recorded in analysis/frozen.yml" in capsys.readouterr().out
    text = (project / "analysis" / "frozen.yml").read_text()
    assert text.startswith("# Results the pipeline reads but doesn't remake")
    assert yaml.safe_load(text) == [{"path": "out/es.csv", "made_by": "analysis/freeze_es.py",
                                     "why": "Its inputs are outside the repository.",
                                     "sha256": hashlib.sha256(b"a,b\n1,2\n").hexdigest()}]
    assert git(project, "status", "--porcelain", "--", "analysis/frozen.yml").startswith("??")


def test_add_replaces_an_entry_and_keeps_paths_in_order(project):
    write(project / "out" / "a.csv", "x\n")
    run(project, "add", "out/es.csv", "--made-by", "analysis/freeze_es.py", "--why", "first")
    run(project, "add", "out/a.csv", "--made-by", "analysis/freeze_es.py", "--why", "other")
    run(project, "add", "./out/es.csv", "--made-by", "analysis/freeze_es.py", "--why", "second")
    entries = frozen.load(project)
    assert [(e["path"], e["why"]) for e in entries] == [("out/a.csv", "other"), ("out/es.csv", "second")]


@pytest.mark.parametrize("args, message", [
    (["out/none.csv", "--made-by", "analysis/freeze_es.py", "--why", "x"], "does not exist"),
    (["out/es.csv", "--made-by", "analysis/other.py", "--why", "x"], "not a file git has"),
    (["out/es.csv", "--made-by", "analysis/freeze_es.py", "--why", "  "], "--why is empty"),
    (["../es.csv", "--made-by", "analysis/freeze_es.py", "--why", "x"], "outside the project"),
    (["out/es.csv", "--made-by", "analysis/freeze_es.py", "--why", "<reason>"], "the placeholder"),
    (["out/es.csv", "--made-by", ".claude/research.yml", "--why", "x"], "not an R, Python or shell script"),
])
def test_add_refuses(project, capsys, args, message):
    assert run(project, "add", *args) == 2
    assert message in capsys.readouterr().err
    assert not (project / "analysis" / "frozen.yml").exists()


def test_problems_lists_a_changed_missing_or_untracked_file(project):
    write(project / "out" / "b.csv", "y\n")
    run(project, "add", "out/es.csv", "--made-by", "analysis/freeze_es.py", "--why", "x")
    run(project, "add", "out/b.csv", "--made-by", "analysis/freeze_es.py", "--why", "x")
    git(project, "add", "-f", "out/es.csv", "out/b.csv")
    assert frozen.problems(project, frozen.load(project)) == []
    write(project / "out" / "es.csv", "a,b\n1,3\n")
    git(project, "rm", "-q", "--cached", "out/b.csv")
    found = frozen.problems(project, frozen.load(project))
    assert found[0].startswith("out/b.csv: frozen, but git doesn't track it")
    assert found[1].startswith("out/es.csv: frozen, but the file has changed since it was frozen")
    (project / "out" / "b.csv").unlink()
    assert frozen.problems(project, frozen.load(project))[0] == "out/b.csv: frozen, but the file is missing"


def test_made_by_may_be_a_script_just_archived_or_deleted(project, capsys):
    (project / "analysis" / "_archive").mkdir()
    git(project, "mv", "analysis/freeze_es.py", "analysis/_archive/freeze_es.py")
    assert run(project, "add", "out/es.csv", "--made-by", "analysis/_archive/freeze_es.py", "--why", "x") == 0
    out = capsys.readouterr().out
    assert "git doesn't track out/es.csv, so a fresh clone won't have it: git add -f -- out/es.csv" in out
    git(project, "commit", "-q", "-m", "archive")
    git(project, "rm", "-q", "analysis/_archive/freeze_es.py")
    assert run(project, "add", "out/es.csv", "--made-by", "analysis/_archive/freeze_es.py", "--why", "x") == 0


@pytest.mark.parametrize("text", ["- path: a\n", "path: a\n", "- [1, 2]\n", ":\n  - x: [\n",
                                  "- {path: a, made_by: b, why: c, sha256: d, extra: e}\n",
                                  "- {path: /abs/a.csv, made_by: b.py, why: c, sha256: d}\n",
                                  "- {path: ./a.csv, made_by: b.py, why: c, sha256: d}\n",
                                  "- {path: out//a.csv, made_by: b.py, why: c, sha256: d}\n",
                                  "- {path: a.csv, made_by: ../b.py, why: c, sha256: d}\n"])
def test_a_malformed_file_is_an_error(project, capsys, text):
    write(project / "analysis" / "frozen.yml", text)
    assert run(project, "add", "out/es.csv", "--made-by", "analysis/freeze_es.py", "--why", "x") == 2
    assert "frozen: ERROR: analysis/frozen.yml" in capsys.readouterr().err


def test_an_empty_or_missing_file_has_no_entries(project):
    assert frozen.load(project) == []
    write(project / "analysis" / "frozen.yml", frozen.HEADER)
    assert frozen.load(project) == []
