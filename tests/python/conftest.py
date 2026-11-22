import os
import sys
from pathlib import Path

import pytest

KIT = Path(__file__).resolve().parents[2]
PLUGIN = KIT / "plugins" / "kit"
sys.path.insert(0, str(KIT / "plugins" / "kit" / "scripts"))
sys.path.insert(0, str(KIT / "tests"))


@pytest.fixture(autouse=True)
def git_identity(monkeypatch):
    """Commits made by scripts under test need an identity; never use the user's."""
    for var, val in {"GIT_AUTHOR_NAME": "kit-test", "GIT_AUTHOR_EMAIL": "kit-test@example.invalid",
                     "GIT_COMMITTER_NAME": "kit-test", "GIT_COMMITTER_EMAIL": "kit-test@example.invalid"}.items():
        monkeypatch.setenv(var, val)


@pytest.fixture(autouse=True)
def kit_home(tmp_path_factory, monkeypatch):
    """No test reads the user's personal layer or touches the real stable path (shareable-kit spec §6).
    The stable path points at this checkout's plugin; KIT_VENV is the Python running the tests."""
    home = tmp_path_factory.mktemp("kit-home")
    data = home / "data"
    data.mkdir()
    (data / "plugin").symlink_to(PLUGIN, target_is_directory=True)
    monkeypatch.setenv("KIT_PERSONAL_DIR", str(home / "personal"))
    monkeypatch.setenv("KIT_DATA_DIR", str(data))
    monkeypatch.setenv("KIT_VENV", sys.prefix)
    return home


def _touch(path, text=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _stub_r_init(project):
    for rel in (".Rprofile", "renv/activate.R", "renv/settings.json"):
        _touch(project / rel, "# stub\n")
    _touch(project / "renv" / ".gitignore", "library/\n")


def _stub_r_sync(project, own):
    _touch(project / "renv.lock", '{"Packages": {%s}}\n' % (f'"{own}": {{}}' if own else ""))


def _stub_r_check_synced(project):
    pass


def _stub_py_init(project):
    _touch(project / "uv.lock", "version = 1\n")
    (project / ".venv").mkdir(exist_ok=True)


def _stub_py_install_pkg(project):
    pp = project / "pyproject.toml"
    pp.write_text(pp.read_text() + "\n# stub: editable ./pkg/python\n")
    _touch(project / "uv.lock", "version = 1\n# stub: pkg\n")


def pytest_configure(config):
    for name in ("needs_renv", "needs_uv", "needs_latexmk"):
        config.addinivalue_line("markers", f"{name}: skipped (lazily) when the tool is missing")


@pytest.fixture(autouse=True)
def real_env_guard(request, monkeypatch):
    """For real_env tests: skip when a needed tool is missing (a failure under KIT_REQUIRE_REAL_ENV=1,
    e.g. `KIT_REQUIRE_REAL_ENV=1 pytest -m real_env`), go offline, and refuse a polluted user R library."""
    if not request.node.get_closest_marker("real_env"):
        return
    import kit_env
    import os
    for name, (ok, why) in kit_env.CHECKS.items():
        if request.node.get_closest_marker(name) and not ok():
            (pytest.fail if os.environ.get("KIT_REQUIRE_REAL_ENV") else pytest.skip)(why)
    monkeypatch.setenv("RENV_CONFIG_REPOS_OVERRIDE", "http://127.0.0.1:9")
    monkeypatch.setenv("UV_OFFLINE", "1")
    stray = kit_env.stray_user_packages()
    assert not stray, f"{stray} installed in the user R library; remove them so tests cannot pass vacuously"


@pytest.fixture(autouse=True)
def stub_envs(request, monkeypatch):
    """Replace the uv/renv calls in scaffold.py with stubs that write the files they would write.
    Tests marked real_env use the real tools."""
    if request.node.get_closest_marker("real_env"):
        return
    import scaffold
    monkeypatch.setattr(scaffold, "r_init", _stub_r_init)
    monkeypatch.setattr(scaffold, "r_sync", _stub_r_sync)
    monkeypatch.setattr(scaffold, "r_check_synced", _stub_r_check_synced)
    monkeypatch.setattr(scaffold, "py_init", _stub_py_init)
    monkeypatch.setattr(scaffold, "py_install_pkg", _stub_py_install_pkg)
