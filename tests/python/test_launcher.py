import os
import subprocess
import sys
from pathlib import Path

from build_fixture import write
from kitlib import PLUGIN_ROOT, data_dir

KIT = PLUGIN_ROOT / "bin" / "kit"


def kit(*args, cwd=None, env=None, stdin=""):
    return subprocess.run([str(KIT), *args], cwd=cwd, env={**os.environ, **(env or {})}, input=stdin,
                          capture_output=True, text=True, timeout=120)


def kit_project(tmp_path):
    p = tmp_path / "proj"
    write(p / ".claude" / "research.yml", "venue: undecided\n")
    (p / "sub").mkdir()
    return p


def test_runs_a_script_with_the_kit_python(tmp_path):
    r = kit("personal.py", "where")
    assert r.returncode == 0 and r.stdout.strip() == os.environ["KIT_PERSONAL_DIR"]


def test_which_customize_where_and_python_pass_through():
    assert kit("which", "rules").stdout.strip().endswith("defaults/rules.md")
    assert kit("where").stdout.strip() == os.environ["KIT_PERSONAL_DIR"]
    assert kit("python", "-c", "import yaml, sys; print(sys.prefix)").stdout.strip() == sys.prefix


def test_refuses_paths_and_unknown_scripts():
    r = kit("../scripts/personal.py", "where")
    assert r.returncode == 2 and "not a path" in r.stderr
    r = kit("nope.py")
    assert r.returncode == 2 and "no script nope.py" in r.stderr
    assert kit("bogus").returncode == 2


def test_session_start_is_silent_outside_a_kit_project(tmp_path):
    link = data_dir() / "plugin"
    link.unlink()
    r = kit("session-start", cwd=tmp_path, env={"CLAUDE_PROJECT_DIR": str(tmp_path)}, stdin="{}")
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")
    assert not link.exists()                                # created nothing
    link.symlink_to(PLUGIN_ROOT)


def test_session_start_in_a_project_subfolder_runs_and_repoints(tmp_path):
    p = kit_project(tmp_path)
    link = data_dir() / "plugin"
    link.unlink()
    link.symlink_to(tmp_path)
    r = kit("session-start", cwd=p / "sub", env={"CLAUDE_PROJECT_DIR": str(tmp_path)}, stdin="{}")
    assert r.returncode == 0 and "=== research-kit session context ===" in r.stdout
    assert link.resolve() == PLUGIN_ROOT.resolve()


def test_session_start_without_an_environment_says_so_and_exits_0(tmp_path):
    p = kit_project(tmp_path)
    r = kit("session-start", cwd=p, env={"KIT_VENV": str(tmp_path / "none")}, stdin="{}")
    assert r.returncode == 0
    assert "ERROR research-kit: the kit's Python environment" in r.stdout and 'bin/kit" setup' in r.stdout


def test_setup_keeps_a_working_environment_and_makes_the_stable_path(tmp_path):
    link = data_dir() / "plugin"
    link.unlink()
    r = kit("setup")
    assert r.returncode == 0, r.stderr
    assert link.resolve() == PLUGIN_ROOT.resolve()


def test_setup_refuses_a_broken_environment(tmp_path):
    (tmp_path / "venv").mkdir()
    r = kit("setup", env={"KIT_VENV": str(tmp_path / "venv")})
    assert r.returncode == 2 and "cannot import yaml" in r.stderr


def test_setup_creates_an_environment_with_uv(tmp_path):
    """A fake uv: `uv venv P` links P to the test Python's venv; `uv pip install` records its arguments."""
    fake = tmp_path / "bin" / "uv"
    write(fake, "#!/bin/sh\n"
                f'echo "$@" >> "{tmp_path}/uv.log"\n'
                'if [ "$1" = venv ]; then for a; do last=$a; done; '
                f'ln -s "{sys.prefix}" "$last"; fi\n')
    fake.chmod(0o755)
    venv = tmp_path / "new" / "venv"
    r = kit("setup", env={"KIT_VENV": str(venv), "PATH": f"{fake.parent}:{os.environ['PATH']}"})
    assert r.returncode == 0, r.stderr
    log = (tmp_path / "uv.log").read_text()
    assert "venv --quiet --python >=3.12" in log and "pip install --quiet --python" in log
    assert str(PLUGIN_ROOT / "requirements.txt") in log


def test_setup_that_fails_removes_what_it_created(tmp_path):
    """A fake uv whose `pip install` fails after `uv venv` made the folder: a rerun must not find a half-made one."""
    fake = tmp_path / "bin" / "uv"
    write(fake, "#!/bin/sh\n"
                'if [ "$1" = venv ]; then for a; do last=$a; done; mkdir -p "$last/bin"; exit 0; fi\n'
                "exit 1\n")
    fake.chmod(0o755)
    venv = tmp_path / "new" / "venv"
    r = kit("setup", env={"KIT_VENV": str(venv), "PATH": f"{fake.parent}:{os.environ['PATH']}"})
    assert r.returncode == 2 and "creating" in r.stderr and "failed" in r.stderr
    assert not os.path.lexists(venv)


def test_setup_without_uv_says_how_to_get_it(tmp_path):
    r = kit("setup", env={"KIT_VENV": str(tmp_path / "venv"), "PATH": "/usr/bin:/bin"})
    assert r.returncode == 2 and "uv is not on the PATH" in r.stderr


def test_hooks_json_runs_the_launcher():
    import json
    hooks = json.loads((PLUGIN_ROOT / "hooks" / "hooks.json").read_text())["hooks"]["SessionStart"][0]["hooks"]
    assert hooks == [{"type": "command", "command": '"${CLAUDE_PLUGIN_ROOT}/bin/kit" session-start', "timeout": 30}]


def test_session_start_through_a_symlinked_folder_finds_the_project(tmp_path):
    p = kit_project(tmp_path)
    link = tmp_path / "ln"
    link.symlink_to(p / "sub")
    r = kit("session-start", cwd=link, env={"PWD": str(link), "CLAUDE_PROJECT_DIR": str(tmp_path)}, stdin="{}")
    assert "=== research-kit session context ===" in r.stdout


def test_works_without_home_when_the_data_folder_is_given(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "HOME"}
    r = subprocess.run([str(KIT), "where"], env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr


def test_relative_kit_folders_are_refused_and_create_nothing(tmp_path):
    for var in ("KIT_DATA_DIR", "KIT_VENV"):
        r = kit("setup", cwd=tmp_path, env={var: "rel"})
        assert r.returncode == 2 and f"{var} must be an absolute path" in r.stderr
        assert not (tmp_path / "rel").exists()
    p = kit_project(tmp_path)
    r = kit("session-start", cwd=p, env={"KIT_DATA_DIR": "rel"}, stdin="{}")
    assert r.returncode == 0 and "ERROR research-kit: KIT_DATA_DIR must be an absolute path" in r.stdout
