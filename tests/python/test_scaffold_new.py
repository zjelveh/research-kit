import os
import re
import subprocess

import pytest

import check_pointers
import scaffold
from build_fixture import write
from kitlib import KitError, load_config
from scaffold import R_PKG_RULE, cmd_new, main, package_name, parse_specs

COMMON = [
    ".claude/settings.json", ".claude/research.yml", "CLAUDE.md", ".gitignore", ".lint_baseline_slides",
    "state/CURRENT_STATE.md", "state/DECISIONS.md", "state/CLAIMS_LEDGER.md", "state/archive/.gitkeep",
    "notes/research_questions.md", "notes/notation.md", "notes/memos/.gitkeep", "notes/lit/map.md",
    "notes/lit/searches/.gitkeep", "analysis/sims/.gitkeep", "analysis/applications/.gitkeep", "slides/.gitkeep",
]
R_FILES = ["analysis/numbers/make_numbers.R", ".Rprofile", "renv/activate.R", "renv.lock"]
PY_FILES = ["analysis/numbers/make_numbers.py", "pyproject.toml", ".python-version", "uv.lock"]
R_PKG = ["pkg/r/DESCRIPTION", "pkg/r/NAMESPACE", "pkg/r/R/.gitkeep", "pkg/r/tests/testthat.R",
         "pkg/r/tests/testthat/.gitkeep"]


def tracked(p):
    return set(subprocess.run(["git", "-C", str(p), "ls-files"], capture_output=True, text=True,
                              check=True).stdout.splitlines())


def ignored(p, rel):
    return subprocess.run(["git", "-C", str(p), "check-ignore", "-q", rel]).returncode == 0


def test_r_project(tmp_path):
    p = cmd_new("my-paper", tmp_path, ["r"])
    assert set(COMMON + R_FILES) <= tracked(p)
    assert not (p / "pkg").exists() and not (p / "pyproject.toml").exists()
    cfg = load_config(p)
    assert cfg["languages"] == ["r"] and cfg["packages"] == {}
    log = subprocess.run(["git", "-C", str(p), "log", "--oneline"], capture_output=True, text=True).stdout
    assert len(log.splitlines()) == 1
    hook = p / ".git/hooks/pre-commit"
    assert os.access(hook, os.X_OK) and "--gate slides" in hook.read_text()
    assert p.stat().st_gid == tmp_path.stat().st_gid


def test_python_project(tmp_path):
    p = cmd_new("demo", tmp_path, ["python"])
    files = tracked(p)
    assert set(COMMON + PY_FILES) <= files
    assert "analysis/numbers/make_numbers.R" not in files and not (p / ".Rprofile").exists()
    assert (p / ".venv").is_dir() and ignored(p, ".venv/x")
    assert 'name = "demo-analysis"' in (p / "pyproject.toml").read_text()
    assert load_config(p)["languages"] == ["python"]


def test_both_languages_and_packages(tmp_path):
    p = cmd_new("my-paper", tmp_path, ["r"], {"r": None, "python": None})
    cfg = load_config(p)
    assert cfg["languages"] == ["r", "python"]
    assert cfg["packages"] == {"r": "mypaper", "python": "my_paper"}
    files = tracked(p)
    assert set(R_PKG) <= files
    assert {"pkg/python/pyproject.toml", "pkg/python/src/my_paper/__init__.py",
            "pkg/python/tests/.gitkeep"} <= files
    assert "Package: mypaper" in (p / "pkg/r/DESCRIPTION").read_text()
    assert 'name = "my_paper"' in (p / "pkg/python/pyproject.toml").read_text()
    assert R_PKG_RULE in (p / "CLAUDE.md").read_text()
    assert check_pointers.main(["--project", str(p)]) == 0
    assert "# stub: editable ./pkg/python" in (p / "pyproject.toml").read_text()
    assert '"mypaper"' in (p / "renv.lock").read_text()


def test_package_implies_language(tmp_path):
    p = cmd_new("demo", tmp_path, [], {"python": "colinf"})
    cfg = load_config(p)
    assert cfg["languages"] == ["python"] and cfg["packages"] == {"python": "colinf"}


def test_languages_implied_by_packages_come_last(tmp_path):
    p = cmd_new("demo", tmp_path, ["python"], {"r": None})
    assert load_config(p)["languages"] == ["python", "r"]


def test_interrupt_removes_project(tmp_path, monkeypatch):
    monkeypatch.setattr(scaffold, "setup_language", lambda *a: (_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        cmd_new("demo", tmp_path, ["r"])
    assert not (tmp_path / "demo").exists()


@pytest.mark.parametrize("bad", ["a/b", "..", ".", ""])
def test_invalid_project_name_refused(tmp_path, bad):
    with pytest.raises(KitError, match="invalid project name"):
        cmd_new(bad, tmp_path, ["r"])
    assert list(tmp_path.iterdir()) == []


def test_missing_uv_refused_before_creating(tmp_path, monkeypatch):
    monkeypatch.setattr(scaffold.shutil, "which", lambda cmd: None)
    with pytest.raises(KitError, match="uv is not on the PATH"):
        cmd_new("demo", tmp_path, ["python"])
    assert not (tmp_path / "demo").exists()


def test_no_language_refused(tmp_path):
    with pytest.raises(KitError, match="at least one language"):
        cmd_new("demo", tmp_path, [])
    assert not (tmp_path / "demo").exists()


def test_invalid_default_package_name_refused(tmp_path):
    with pytest.raises(KitError, match=r"pass --package r=NAME"):
        cmd_new("2fast", tmp_path, [], {"r": None})
    assert not (tmp_path / "2fast").exists()


def test_no_unrendered_placeholders(tmp_path):
    p = cmd_new("demo", tmp_path, ["r", "python"], {"r": None, "python": None})
    for f in p.rglob("*"):
        if f.is_file() and ".git" not in f.parts and ".venv" not in f.parts:
            assert not re.search(r"\{\{[A-Z_]+\}\}", f.read_text()), f
            assert not re.search(r"\{\{[A-Z_]+\}\}", str(f)), f


def test_refuses_existing(tmp_path):
    (tmp_path / "demo").mkdir()
    with pytest.raises(KitError, match="already exists"):
        cmd_new("demo", tmp_path, ["r"])


def test_ignores(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"])
    assert (p / "notes/lit/pdfs").is_dir()
    for rel in ("notes/lit/pdfs/x.pdf", ".venv/x", "analysis/__pycache__/x.pyc", "state/.sessions/x.json"):
        assert ignored(p, rel), rel


def test_failed_scaffold_leaves_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(scaffold, "install_hook", lambda *a: (_ for _ in ()).throw(KitError("boom")))
    with pytest.raises(KitError, match="removed the partial project"):
        cmd_new("demo", tmp_path, ["r"])
    assert not (tmp_path / "demo").exists()


def test_failed_environment_leaves_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(scaffold, "py_init", lambda project: (_ for _ in ()).throw(KitError("uv boom")))
    with pytest.raises(KitError, match="uv boom"):
        cmd_new("demo", tmp_path, ["python"])
    assert not (tmp_path / "demo").exists()


def test_slides_gate_blocks_commit(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"])
    write(p / "slides" / "talk" / "talk.tex",
          "\\documentclass{beamer}\n\\begin{document}\nWe had 3 cases.\n\\end{document}\n")
    subprocess.run(["git", "-C", str(p), "add", "-A"], check=True)
    r = subprocess.run(["git", "-C", str(p), "commit", "-m", "talk"], capture_output=True, text=True)
    assert r.returncode != 0 and "REGRESSION" in r.stdout + r.stderr


def test_r_pkg_builds(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"], {"r": None})
    r = subprocess.run(["R", "CMD", "build", "--no-build-vignettes", str(p / "pkg" / "r")],
                       cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("lang,project,override,expected", [
    ("r", "my-paper", None, "mypaper"),
    ("r", "my_paper", None, "mypaper"),
    ("python", "my-paper", None, "my_paper"),
    ("python", "My-Paper", None, "my_paper"),
    ("r", "2fast", "colinf", "colinf"),
])
def test_package_name(lang, project, override, expected):
    assert package_name(lang, project, override, "--package x=NAME") == expected


def test_package_name_keyword_refused():
    with pytest.raises(KitError, match="not a valid Python import name"):
        package_name("python", "class", None, "--package python=NAME")


def test_parse_specs_package_before_lang():
    assert parse_specs([("package", "r"), ("lang", "python")]) == (["r", "python"], {"r": None})


def test_parse_specs_order_and_names():
    assert parse_specs([("lang", "python"), ("package", "r=foo"), ("lang", "r")]) == (
        ["python", "r"], {"r": "foo"})


@pytest.mark.parametrize("specs,msg", [
    ([("lang", "julia")], "unknown language"),
    ([("package", "r"), ("package", "r=x")], "given twice"),
    ([("package", "r=")], "needs a name"),
])
def test_parse_specs_errors(specs, msg):
    with pytest.raises(KitError, match=msg):
        parse_specs(specs)


def test_cli_requires_a_language(tmp_path, capsys):
    assert main(["new", "demo", "--root", str(tmp_path)]) == 2
    assert "at least one language" in capsys.readouterr().err


def test_cli_new(tmp_path):
    assert main(["new", "demo", "--root", str(tmp_path), "--lang", "r", "--package", "python=colinf"]) == 0
    cfg = load_config(tmp_path / "demo")
    assert cfg["packages"] == {"python": "colinf"} and cfg["languages"] == ["r", "python"]
