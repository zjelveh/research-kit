import shutil
import subprocess

import pytest

from build_fixture import CONFIG, git, init_repo, minimal_project, write
from kitlib import KitError, PLUGIN_ROOT
from scaffold import cmd_add_loader, main

LIB = "code/src"


def project(tmp_path, config=CONFIG + f"library: [{LIB}]\n"):
    p = minimal_project(tmp_path, config)
    write(p / LIB / "samples.R", "post_sample <- function(d) state_code(d)\n")
    write(p / LIB / "state_data.R", 'state_code <- function(d) paste0("s", d)\n')
    write(p / LIB / "test_samples.R", 'stop("a test file must not be loaded")\n')
    init_repo(p)
    return p


def test_add_loader_writes_and_commits_only_the_loader(tmp_path, capsys):
    p = project(tmp_path)
    assert cmd_add_loader(LIB, p) == f"{LIB}/load.R"
    assert (p / LIB / "load.R").read_bytes() == (PLUGIN_ROOT / "templates" / "lib" / "load.R").read_bytes()
    assert git(p, "show", "--name-only", "--format=", "HEAD").split() == [f"{LIB}/load.R"]
    assert 'source("code/src/load.R")' in capsys.readouterr().out
    assert cmd_add_loader(LIB + "/", p) is None                      # already current


@pytest.mark.parametrize("folder,msg", [("code", "not a library folder"), ("elsewhere", "not a library folder")])
def test_add_loader_refuses_a_folder_outside_the_library(tmp_path, folder, msg):
    p = project(tmp_path)
    with pytest.raises(KitError, match=msg):
        cmd_add_loader(folder, p)


def test_add_loader_refuses_a_projects_own_load_r_and_a_python_project(tmp_path, capsys):
    p = project(tmp_path)
    write(p / LIB / "load.R", "# mine\n")
    git(p, "add", "-A")
    git(p, "commit", "-q", "-m", "own")
    assert main(["add-loader", LIB, "--project", str(p)]) == 2
    assert "is not the kit's" in capsys.readouterr().err
    q = project(tmp_path / "py", CONFIG.replace("[r]", "[python]") + f"library: [{LIB}]\n")
    with pytest.raises(KitError, match="no r"):
        cmd_add_loader(LIB, q)


@pytest.mark.skipif(shutil.which("Rscript") is None, reason="R is not installed")
def test_the_loader_loads_every_library_file_but_tests_from_any_folder(tmp_path):
    p = project(tmp_path)
    cmd_add_loader(LIB, p)
    write(p / "code" / "drivers" / "run.R", 'source("../src/load.R")\ncat(post_sample(1), "\\n")\n')
    out = subprocess.run(["Rscript", "--vanilla", "run.R"], cwd=p / "code" / "drivers", capture_output=True,
                         text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "s1"
