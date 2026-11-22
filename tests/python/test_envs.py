import json
import subprocess

import pytest

from build_fixture import write
from kit_env import needs_renv, needs_uv
from kitlib import KitError
from scaffold import cmd_add_language, cmd_add_package, cmd_new

pytestmark = pytest.mark.real_env


def out(p, *cmd):
    r = subprocess.run(list(cmd), cwd=p, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout


@needs_uv
def test_python_env(tmp_path):
    p = cmd_new("demo", tmp_path, ["python"])
    out(p, "uv", "lock", "--check")
    assert "(3, 12)" in out(p, "uv", "run", "--locked", "python", "-c", "import sys; print(sys.version_info[:2])")


@needs_uv
def test_python_package_editable(tmp_path):
    p = cmd_new("demo", tmp_path, ["python"], {"python": None})
    path = out(p, "uv", "run", "--locked", "python", "-c", "import demo; print(demo.__file__)")
    assert str(p / "pkg" / "python" / "src" / "demo") in path


@needs_renv
def test_r_env(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"])
    assert str(p) in out(p, "Rscript", "-e", "cat(.libPaths()[1])")
    out(p, "Rscript", "-e", "quit(status = !isTRUE(renv::status()$synchronized))")


@needs_renv
def test_r_package(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"], {"r": None})
    packages = json.loads((p / "renv.lock").read_text())["Packages"]
    assert "demo" in packages and "testthat" in packages
    assert "ok" in out(p, "Rscript", "-e", "library(demo); cat('ok')")


@needs_renv
@needs_uv
def test_r_missing_dependency_refused_and_rolled_back(tmp_path):
    p = cmd_new("demo", tmp_path, ["python"])
    write(p / "analysis" / "x.R", "library(notARealPkg123)\n")
    subprocess.run(["git", "-C", str(p), "add", "analysis/x.R"], check=True)
    subprocess.run(["git", "-C", str(p), "commit", "-qm", "x"], check=True)
    head = out(p, "git", "rev-parse", "HEAD")
    with pytest.raises(KitError, match="notARealPkg123"):
        cmd_add_language("r", p)
    assert not (p / ".Rprofile").exists() and not (p / "renv").exists()
    assert out(p, "git", "rev-parse", "HEAD") == head and not out(p, "git", "status", "--porcelain").strip()


@needs_renv
def test_project_library_only_dependency_accepted(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"])
    src = tmp_path / "onlyproj"
    write(src / "DESCRIPTION", "Package: onlyproj\nTitle: T\nVersion: 0.0.1\nAuthors@R: person(\"A\", email = \"a@b.c\", role = c(\"aut\", \"cre\"))\nDescription: T.\nLicense: GPL (>= 3)\nEncoding: UTF-8\n")
    write(src / "NAMESPACE", "")
    out(p, "Rscript", "-e", f"stopifnot(startsWith(.libPaths()[1], normalizePath(getwd()))); renv::install('{src}', prompt = FALSE); renv::snapshot(prompt = FALSE)")
    write(p / "analysis" / "uses.R", "library(onlyproj)\n")
    subprocess.run(["git", "-C", str(p), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(p), "commit", "-qm", "uses onlyproj"], check=True)
    out(p, "Rscript", "-e", "renv::snapshot(prompt = FALSE)")
    subprocess.run(["git", "-C", str(p), "commit", "-qam", "lock"], check=True)
    cmd_add_package("r", p)
    packages = json.loads((p / "renv.lock").read_text())["Packages"]
    assert "onlyproj" in packages and "demo" in packages


@needs_renv
@needs_uv
def test_add_language_r_hydrates_user_library_dependency(tmp_path):
    p = cmd_new("demo", tmp_path, ["python"])
    write(p / "analysis" / "x.R", "library(jsonlite)\n")
    subprocess.run(["git", "-C", str(p), "add", "analysis/x.R"], check=True)
    subprocess.run(["git", "-C", str(p), "commit", "-qm", "x"], check=True)
    head = out(p, "git", "rev-parse", "HEAD")
    cmd_add_language("r", p)
    assert "jsonlite" in json.loads((p / "renv.lock").read_text())["Packages"]
    out(p, "Rscript", "-e", "quit(status = !isTRUE(renv::status()$synchronized))")
    assert out(p, "git", "rev-parse", "HEAD~1").strip() == head.strip()
    assert not out(p, "git", "status", "--porcelain").strip()
