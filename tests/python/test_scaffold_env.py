import json
import sys

import pytest

import scaffold
from kit_env import needs_renv
from kitlib import KitError


def test_run_missing_tool(tmp_path, monkeypatch):
    monkeypatch.setattr(scaffold.shutil, "which", lambda name: None)
    with pytest.raises(KitError, match=r"uv is not on the PATH; install uv \(https://docs.astral.sh/uv"):
        scaffold.run(["uv", "lock"], tmp_path)


def test_require_renv_missing_rscript(tmp_path, monkeypatch):
    monkeypatch.setattr(scaffold.shutil, "which", lambda name: None)
    with pytest.raises(KitError, match="Rscript is not on the PATH; install R"):
        scaffold.require_renv(tmp_path)


def test_run_failure_strips_ansi(tmp_path):
    cmd = [sys.executable, "-c", "import sys; print('\\x1b[31mred\\x1b[0m'); sys.exit(2)"]
    with pytest.raises(KitError) as e:
        scaffold.run(cmd, tmp_path)
    assert "red" in str(e.value) and "\x1b" not in str(e.value)


def test_package_name_collides_with_analysis_env():
    with pytest.raises(KitError, match="collides"):
        scaffold.package_name("python", "demo", "demo_analysis", "--package python=NAME")
    assert scaffold.package_name("python", "demo", "demo_pkg", "--package python=NAME") == "demo_pkg"


def test_package_name_collision_with_repeated_underscores():
    with pytest.raises(KitError, match="collides"):
        scaffold.package_name("python", "demo", "demo__analysis", "--package python=NAME")


def _r_project(tmp_path, monkeypatch, own=True, imports=None):
    monkeypatch.setenv("RENV_CONFIG_REPOS_OVERRIDE", "http://127.0.0.1:9")
    d = tmp_path / "demo"
    d.mkdir()
    scaffold.copy_tree(scaffold.TEMPLATES / "lang" / "r", d, scaffold.base_values("demo"))
    if own:
        scaffold.copy_tree(scaffold.TEMPLATES / "pkg" / "r", d / "pkg" / "r", {**scaffold.base_values("demo"), **scaffold.pkg_values("r", "demo")})
        if imports:
            desc = d / "pkg" / "r" / "DESCRIPTION"
            desc.write_text(desc.read_text().rstrip("\n") + f"\nImports: {imports}\n")
    return d


def _lock_packages(d):
    return json.loads((d / "renv.lock").read_text())["Packages"]


@pytest.mark.real_env
@needs_renv
def test_r_sync_own_package(tmp_path, monkeypatch):
    d = _r_project(tmp_path, monkeypatch)
    scaffold.r_init(d)
    scaffold.r_sync(d, "demo")
    pk = _lock_packages(d)
    assert "demo" in pk and "testthat" in pk
    scaffold.r_check_synced(d)


@pytest.mark.real_env
@needs_renv
def test_r_sync_hydrates_own_package_imports(tmp_path, monkeypatch):
    d = _r_project(tmp_path, monkeypatch, imports="yaml")
    scaffold.r_init(d)
    scaffold.r_sync(d, "demo")
    assert "yaml" in _lock_packages(d)


@pytest.mark.real_env
@needs_renv
def test_r_check_synced_refuses_drift(tmp_path, monkeypatch):
    d = _r_project(tmp_path, monkeypatch)
    scaffold.r_init(d)
    scaffold.r_sync(d, "demo")
    lock = json.loads((d / "renv.lock").read_text())
    lock["Packages"]["testthat"]["Version"] = "0.0.1"
    (d / "renv.lock").write_text(json.dumps(lock))
    with pytest.raises(KitError, match="out of sync") as e:
        scaffold.r_check_synced(d)
    assert "testthat" in str(e.value)


@pytest.mark.real_env
@needs_renv
def test_r_sync_names_missing_package_and_file(tmp_path, monkeypatch):
    d = _r_project(tmp_path, monkeypatch, own=False)
    (d / "analysis").mkdir(exist_ok=True)
    (d / "analysis" / "x.R").write_text("library(notARealPkg123)\n")
    scaffold.r_init(d)
    with pytest.raises(KitError, match="notARealPkg123: ") as e:
        scaffold.r_sync(d, None)
    assert "x.R" in str(e.value)
