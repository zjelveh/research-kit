"""The gate's archive check: a script may not leave while the pipeline reads a file only it writes (frozen
results spec)."""
import pytest

import frozen
import lint_code
from build_fixture import CONFIG, git, minimal_project, write

RUN_ALL = 'import subprocess\nsubprocess.run(["python", "analysis/make_fig.py"])\n'
FIG = 'CSV = "out/es.csv"\nes = pd.read_csv(CSV)\nother = pd.read_csv("out/other.csv")\n'


@pytest.fixture
def project(tmp_path):
    p = minimal_project(tmp_path, CONFIG.replace("languages: [r]", "languages: [python]"))
    write(p / "analysis" / "params.yml", "# Parameters (research-kit).\n")
    write(p / "run_all.py", RUN_ALL)
    write(p / "analysis" / "make_fig.py", FIG)
    write(p / "analysis" / "freeze_es.py", 'es.to_csv("out/es.csv")\n')
    write(p / "analysis" / "old_other.py", 'pd.DataFrame().to_csv("out/other.csv")\n')
    write(p / "analysis" / "make_other.py", 'pd.DataFrame().to_csv("out/other.csv")\n')
    write(p / "analysis" / "explore" / "look.py", 'es.to_csv("out/es.csv")\n')
    write(p / "out" / "es.csv", "a\n1\n")
    write(p / ".gitignore", "out/\n")
    git(p, "init", "-q", "-b", "main")
    git(p, "add", "-A")
    git(p, "commit", "-q", "-m", "init")
    return p


def gate(p, capsys):
    code = lint_code.main(["--project", str(p), "--precommit"])
    captured = capsys.readouterr()
    return code, [line for line in captured.out.splitlines() if lint_code.LEAVES in line or "frozen.yml" in line], \
        captured.err


def archive(p, rel):
    dest = rel.replace("analysis/", "analysis/_archive/")
    (p / dest).parent.mkdir(parents=True, exist_ok=True)
    git(p, "mv", rel, dest)


def make_run_all_run_make_other(p):
    write(p / "run_all.py", RUN_ALL + 'subprocess.run(["python", "analysis/make_other.py"])\n')
    git(p, "commit", "-q", "-am", "run make_other")


def test_archiving_the_only_writer_of_a_file_the_pipeline_reads_blocks(project, capsys):
    make_run_all_run_make_other(project)
    archive(project, "analysis/freeze_es.py")
    code, found, err = gate(project, capsys)
    assert code == 1
    assert found == ["analysis/freeze_es.py:1: leaves while analysis/make_fig.py:2 reads out/es.csv, which nothing "
                     "left in the pipeline writes; keep the script, move the writing into the pipeline, or declare "
                     "the file frozen: kit frozen.py add out/es.csv --made-by analysis/_archive/freeze_es.py "
                     "--why \"<reason>\""]
    assert "can't leave until the pipeline makes it or the file is declared frozen" in err


def test_the_printed_fix_runs_and_then_the_commit_passes(project, capsys):
    make_run_all_run_make_other(project)
    archive(project, "analysis/freeze_es.py")
    assert frozen.main(["add", "out/es.csv", "--made-by", "analysis/_archive/freeze_es.py", "--why",
                        "Its inputs are outside the repository.", "--project", str(project)]) == 0
    assert "git add -f -- out/es.csv" in capsys.readouterr().out
    git(project, "add", "analysis/frozen.yml")
    assert gate(project, capsys)[:2] == (0, [])


def test_a_plain_delete_blocks_with_the_old_path(project, capsys):
    make_run_all_run_make_other(project)
    git(project, "rm", "-q", "analysis/freeze_es.py")
    _, found, _ = gate(project, capsys)
    assert len(found) == 1 and found[0].endswith("--made-by analysis/freeze_es.py --why \"<reason>\"")


def test_a_move_outside_archived_code_is_not_a_leave(project, capsys):
    (project / "analysis" / "tables").mkdir()
    git(project, "mv", "analysis/freeze_es.py", "analysis/tables/freeze_es.py")
    assert gate(project, capsys)[1] == []


def test_another_pipeline_writer_lets_the_old_one_leave(project, capsys):
    git(project, "rm", "-q", "analysis/old_other.py")
    _, found, _ = gate(project, capsys)
    assert any("reads out/other.csv" in line for line in found)       # make_other.py isn't run yet
    git(project, "reset", "-q", "--hard")
    make_run_all_run_make_other(project)
    git(project, "rm", "-q", "analysis/old_other.py")
    assert gate(project, capsys)[1] == []


def test_explore_scripts_may_leave_and_no_run_all_skips_the_check(project, capsys):
    make_run_all_run_make_other(project)
    git(project, "rm", "-q", "analysis/explore/look.py")
    assert gate(project, capsys)[1] == []
    git(project, "reset", "-q", "--hard")
    git(project, "rm", "-q", "run_all.py", "analysis/freeze_es.py")
    assert gate(project, capsys)[1] == []


def test_run_all_in_research_yml_names_the_pipeline(project, capsys):
    make_run_all_run_make_other(project)
    git(project, "mv", "run_all.py", "cascade.py")
    cfg = project / ".claude" / "research.yml"
    cfg.write_text(cfg.read_text() + "run_all: [cascade.py]\n")
    git(project, "add", ".claude/research.yml")
    git(project, "commit", "-q", "-m", "cascade")
    archive(project, "analysis/freeze_es.py")
    assert len(gate(project, capsys)[1]) == 1


def test_a_malformed_frozen_file_is_a_finding_when_a_script_leaves(project, capsys):
    make_run_all_run_make_other(project)
    write(project / "analysis" / "frozen.yml", "- path: out/es.csv\n")
    git(project, "add", "analysis/frozen.yml")
    archive(project, "analysis/freeze_es.py")
    _, found, _ = gate(project, capsys)
    assert found[0].startswith("analysis/frozen.yml:1: analysis/frozen.yml: entry 1 must have exactly")


def test_a_listed_run_all_may_keep_a_step_runner(project, capsys):
    cfg = project / ".claude" / "research.yml"
    cfg.write_text(cfg.read_text() + "run_all: [cascade.py]\n")
    write(project / "cascade.py", "def step(name):\n    return name\n")
    git(project, "add", ".claude/research.yml", "cascade.py")
    code = lint_code.main(["--project", str(project), "--precommit"])
    assert code == 0, capsys.readouterr()


def test_a_rename_with_an_edit_is_a_move_and_a_move_out_of_the_code_is_a_leave(project, capsys):
    make_run_all_run_make_other(project)
    (project / "analysis" / "builders").mkdir()
    git(project, "mv", "analysis/freeze_es.py", "analysis/builders/freeze_es.py")
    write(project / "analysis" / "builders" / "freeze_es.py", 'es.to_csv("out/es.csv")\nprint("done")\n')
    git(project, "add", "analysis/builders/freeze_es.py")
    assert gate(project, capsys)[1] == []
    git(project, "reset", "-q", "--hard")
    git(project, "mv", "analysis/freeze_es.py", "analysis/freeze_es.py.bak")
    assert len(gate(project, capsys)[1]) == 1


def test_the_printed_path_comes_from_the_leaving_script(project, capsys):
    make_run_all_run_make_other(project)
    write(project / "analysis" / "out" / "es.csv", "a\n1\n")
    git(project, "rm", "-q", "analysis/freeze_es.py")
    _, found, _ = gate(project, capsys)
    assert "kit frozen.py add analysis/out/es.csv --made-by analysis/freeze_es.py" in found[0]


def test_a_hand_written_frozen_path_must_be_the_file(project, capsys):
    make_run_all_run_make_other(project)
    write(project / "analysis" / "frozen.yml", "- {path: es.csv, made_by: a.py, why: x, sha256: y}\n")
    git(project, "add", "analysis/frozen.yml")
    git(project, "rm", "-q", "analysis/freeze_es.py")
    assert len(gate(project, capsys)[1]) == 1
