from pathlib import Path

import pytest

import lint_code
from build_fixture import CONFIG, git, minimal_project, write

HEADER = "# Parameters (research-kit).\n\n"
PARAMS = HEADER + """# Smallest group the tables report.
min_group_size: 20
# The cleaned panel.
analysis_data: 'data/clean/panel.csv'
"""
EXPLORE_PARAMS = HEADER + """# Start of the window, for one question.
q_start: '2016-01-01'
"""
OLD_R = """x <- read.csv(param("analysis_data"))
y <- x[x$cases > 30, ]
"""


@pytest.fixture
def project(tmp_path):
    p = minimal_project(tmp_path, CONFIG + "library: [analysis/R]\n")
    write(p / "analysis" / "params.yml", PARAMS)
    write(p / "analysis" / "explore" / "params.yml", EXPLORE_PARAMS)
    write(p / "analysis" / "R" / "lib.R", "load <- function() 1\n")
    write(p / "analysis" / "run.R", OLD_R)
    git(p, "init", "-q", "-b", "main")
    git(p, "add", "-A")
    git(p, "commit", "-q", "-m", "init")
    return p


def stage(p, rel, text):
    write(p / rel, text)
    git(p, "add", rel)


def gate(p, capsys):
    code = lint_code.main(["--project", str(p), "--precommit"])
    return code, capsys.readouterr().out


def test_added_lines_with_typed_values_block_the_commit(project, capsys):
    stage(project, "analysis/run.R", OLD_R + 'z <- subset(y, year >= 2019 & p < 0.05)\nw <- "2016-07-01"\n'
                                              'write.csv(w, "out/result.csv")\n')
    code, out = gate(project, capsys)
    assert code == 1
    assert "analysis/run.R:3: typed number 2019" in out and "analysis/run.R:3: typed number 0.05" in out
    assert "analysis/run.R:4: typed date '2016-07-01'" in out
    assert "analysis/run.R:5: typed path 'out/result.csv'" in out
    assert ":2:" not in out                                   # 30 is on an old line


def test_allowed_numbers_and_strings_pass(project, capsys):
    stage(project, "analysis/run.R", OLD_R + 'a <- 2 * x^2 / 100 - 1 + 0 - b[1]\nsource("analysis/R/lib.R")\n'
                                              'lab <- paste0(a, "/", b)\nmsg <- "a / b of 3 cases"\n')
    assert gate(project, capsys) == (0, "")


def test_typed_numbers_include_scientific_and_negative(project, capsys):
    stage(project, "analysis/run.py", "tol = 1e-9\nshift = -3\nhalf = x * 0.5\n")
    code, out = gate(project, capsys)
    assert code == 1 and "typed number 1e-09" in out
    assert "analysis/run.py:2: typed number -3" in out and "analysis/run.py:3: typed number 0.5" in out


def test_a_literal_comment_allows_the_line(project, capsys):
    stage(project, "analysis/run.R", OLD_R + "set.seed(20261124)  # literal: the seed of record for the draft\n"
                                              "k <- 7  # literal:\n")
    code, out = gate(project, capsys)
    assert code == 1 and ":3:" not in out and "analysis/run.R:4: typed number 7" in out


def test_a_value_that_is_a_parameter_is_named(project, capsys):
    stage(project, "analysis/run.py", 'df = load("data/clean/panel.csv")\nok = n >= 20\n')
    _, out = gate(project, capsys)
    assert "typed path 'data/clean/panel.csv' (it is param('analysis_data'))" in out
    assert "typed number 20 (it is param('min_group_size'))" in out


def test_parameter_names_are_checked(project, capsys):
    stage(project, "analysis/run.R", OLD_R + 'n <- param("min_case")\ns <- param("q_start")\nd <- param_path("nope")\n')
    stage(project, "analysis/explore/2026-11-24-q.R", 's <- param("q_start")\nm <- param("min_group_size")\n')
    code, out = gate(project, capsys)
    assert code == 1 and "analysis/run.R:3: param('min_case') is in neither parameter file" in out
    assert "analysis/run.R:4: param('q_start') is an explore parameter" in out
    assert "analysis/run.R:5: param('nope') is in neither parameter file" in out
    assert "explore/2026-11-24-q.R" not in out


def test_parameter_file_problems_block_the_commit(project, capsys):
    stage(project, "analysis/params.yml", PARAMS + "start: 2016-01-01\n")
    code, out = gate(project, capsys)
    assert code == 1 and "analysis/params.yml:7: start:" in out and "single quotes" in out


def test_tests_archive_and_tooling_are_exempt(project, capsys):
    stage(project, "analysis/tests/test_run.py", "assert f(3) == 0.25\n")
    stage(project, "analysis/archive/old.R", "x <- 2019\n")
    stage(project, "renv/activate.R", "version <- '1.0.7'\nn <- 78\n")
    stage(project, ".claude/hooks/x.py", "n = 30\n")
    assert gate(project, capsys) == (0, "")


def test_package_numbers_may_be_defaults_or_named_constants(project, capsys):
    stage(project, "pkg/r/R/est.R", "MAX_ITER <- 500\nLEVELS <- c(0.9, 0.95)\nSETTINGS <- list(\n  tol = 1e-7,\n"
                                    "  draws = 999\n)\nest <- function(x, tol = 1e-9,\n"
                                    "                level = 0.95) {\n"
                                    "  x * 0.5\n}\n")
    stage(project, "pkg/python/src/m/core.py", "TOL = 1e-6\nLEVELS = (0.9, 0.95)\n\n"
                                               "def est(x, tol=1e-9, *, level=0.95):\n"
                                               "    return x * 0.5\n")
    code, out = gate(project, capsys)
    assert code == 1 and out.count("typed number 0.5") == 2
    for allowed in ("500", "1e-09", "0.95", "1e-06", "1e-07", "999", "0.9 "):
        assert allowed not in out


def test_package_strings_and_param_are_flagged(project, capsys):
    stage(project, "pkg/python/src/m/io.py", "DATA = 'data/raw/x.csv'\n\ndef save(p='out/t.csv'):\n    return p\n")
    stage(project, "pkg/r/R/io.R", 'load <- function(path = "data/raw/x.csv") read.csv(path)\n'
                                   'n <- function() param("min_group_size")\n')
    code, out = gate(project, capsys)
    assert code == 1 and "pkg/python/src/m/io.py:1: typed path 'data/raw/x.csv'" in out
    assert "pkg/python/src/m/io.py:3: typed path 'out/t.csv'" in out and "pkg/r/R/io.R:1: typed path" in out
    assert "pkg/r/R/io.R:2: param('min_group_size') in a package" in out


def test_python_docstrings_are_not_checked(project, capsys):
    stage(project, "analysis/R/run.py", '"""Reads data/raw/x.csv from 2016-01-01."""\n\ndef f():\n'
                                      '    """Uses 0.05."""\n    return 0\n')
    assert gate(project, capsys) == (0, "")


def test_python_that_does_not_parse_is_reported(project, capsys):
    stage(project, "analysis/run.py", "print 'old'\n")
    code, out = gate(project, capsys)
    assert code == 1 and "analysis/run.py:1: Python that does not parse" in out


def test_files_mode_checks_changed_lines_and_new_files(project, capsys):
    write(project / "analysis" / "run.R", OLD_R + "z <- 2019\n")
    write(project / "analysis" / "new.py", "a = 0.05\n")
    assert lint_code.main(["--project", str(project), "--files", "analysis/run.R", "analysis/new.py",
                           "analysis/gone.R"]) == 1
    out = capsys.readouterr().out
    assert "analysis/run.R:3: typed number 2019" in out and "analysis/new.py:1: typed number 0.05" in out
    assert ":2:" not in out
    assert lint_code.main(["--project", str(project), "--files", "analysis/R/lib.R"]) == 0
    assert "code gate: nothing found" in capsys.readouterr().out


def test_all_counts_the_backlog_and_lists_files(project, capsys):
    assert lint_code.main(["--project", str(project), "--all"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("code gate backlog: 1 findings in 1 files (number 1)")
    assert "     1  analysis/run.R" in out
    assert lint_code.main(["--project", str(project), "--all", "analysis/run.R"]) == 0
    assert "analysis/run.R:2: typed number 30" in capsys.readouterr().out


def test_outside_a_project_exits_2(tmp_path, capsys):
    assert lint_code.main(["--project", str(tmp_path), "--all"]) == 2
    assert "lint_code: ERROR" in capsys.readouterr().err


def test_git_settings_cannot_switch_the_gate_off(project, capsys):
    for key, value in (("diff.external", "echo"), ("color.diff", "always"), ("diff.noprefix", "true"),
                       ("diff.mnemonicPrefix", "true"), ("diff.interHunkContext", "5")):
        git(project, "config", key, value)
    write(project / ".gitattributes", "*.R -diff\n")
    stage(project, "analysis/run.R", "z <- 2019\n" + OLD_R)
    code, out = gate(project, capsys)
    assert code == 1 and "analysis/run.R:1: typed number 2019" in out and "typed number 30" not in out


def test_a_moved_file_counts_only_its_changed_lines(project, capsys):
    git(project, "mv", "analysis/run.R", "analysis/R/run.R")
    assert gate(project, capsys) == (0, "")
    stage(project, "analysis/R/run.R", OLD_R + "z <- 2019\n")
    code, out = gate(project, capsys)
    assert code == 1 and "analysis/R/run.R:3: typed number 2019" in out and ":2:" not in out


def test_a_file_that_is_not_utf8_does_not_crash_the_gate(project, capsys):
    for rel in ("analysis/latin.R", "analysis/tests/test_latin.R"):
        (project / rel).parent.mkdir(parents=True, exist_ok=True)
        (project / rel).write_bytes("# caf\xe9\nx <- 2019\n".encode("latin-1"))
        git(project, "add", rel)
    code, out = gate(project, capsys)
    assert code == 1 and "analysis/latin.R:2: typed number 2019" in out and "test_latin" not in out


def test_a_byte_order_mark_is_fine(project, capsys):
    stage(project, "analysis/bom.py", "\ufeffx = 0\n")
    stage(project, "analysis/params.yml", "\ufeff" + PARAMS)
    assert gate(project, capsys) == (0, "")


def test_format_strings_are_not_paths_and_date_times_are_dates(project, capsys):
    stage(project, "analysis/run.R", OLD_R + 'd <- as.Date(x, format = "%m/%d/%Y")\nr <- sprintf("%d/%d", a, b)\n'
                                              't <- as.POSIXct("2016-01-01 00:00")\n')
    code, out = gate(project, capsys)
    assert code == 1 and "analysis/run.R:5: typed date '2016-01-01 00:00'" in out
    assert ":3:" not in out and ":4:" not in out


def test_whole_numbers_show_as_integers(project, capsys):
    stage(project, "analysis/run.R", OLD_R + "set.seed(20261124)\n")
    assert "analysis/run.R:3: typed number 20261124" in gate(project, capsys)[1]


def test_a_merge_counts_only_lines_new_to_both_parents(project, capsys):
    git(project, "checkout", "-q", "-b", "old")
    write(project / "analysis" / "old_branch.R", "k <- 2019\n")
    git(project, "add", "analysis/old_branch.R")
    git(project, "commit", "-q", "-m", "old work, from before the gate")
    git(project, "checkout", "-q", "main")
    write(project / "analysis" / "R" / "lib.R", "load <- function() 0\n")
    git(project, "commit", "-q", "-am", "main moves on")
    git(project, "merge", "-q", "--no-ff", "--no-commit", "old")
    assert gate(project, capsys) == (0, "")
    stage(project, "analysis/old_branch.R", "k <- 2019\nj <- 2020\n")
    code, out = gate(project, capsys)
    assert code == 1 and "analysis/old_branch.R:2: typed number 2020" in out and ":1:" not in out


def test_any_file_name_works(project, capsys):
    stage(project, "analysis/01 clean data.R", "x <- 2019\n")
    stage(project, 'analysis/say"hi.R', "y <- 2020\n")
    code, out = gate(project, capsys)
    assert code == 1 and "analysis/01 clean data.R:1: typed number 2019" in out
    assert 'analysis/say"hi.R:1: typed number 2020' in out
    git(project, "commit", "-q", "--no-verify", "-m", "names")
    write(project / "analysis" / "01 clean data.R", "x <- 2019\nz <- 2021\n")
    assert lint_code.main(["--project", str(project), "--files", "analysis/01 clean data.R"]) == 1
    out = capsys.readouterr().out
    assert "analysis/01 clean data.R:2: typed number 2021" in out and ":1:" not in out


def test_format_strings_still_name_files(project, capsys):
    stage(project, "analysis/run.R", OLD_R + 'p <- sprintf("%s/panel.csv", root)\n'
                                              'u <- "https://example.org/my%20data.csv"\n')
    stage(project, "analysis/run.py", 'p = "%s/panel.csv" % root\n')
    code, out = gate(project, capsys)
    assert code == 1 and "analysis/run.R:3: typed path '%s/panel.csv'" in out
    assert "analysis/run.R:4: typed path 'https://example.org/my%20data.csv'" in out
    assert "analysis/run.py:1: typed path '%s/panel.csv'" in out


def test_files_mode_follows_a_staged_move(project, capsys):
    git(project, "mv", "analysis/run.R", "analysis/R/run.R")
    write(project / "analysis" / "R" / "run.R", OLD_R + "z <- 2019\n")
    assert lint_code.main(["--project", str(project), "--files", "analysis/R/run.R"]) == 1
    out = capsys.readouterr().out
    assert "analysis/R/run.R:3: typed number 2019" in out and "typed number 30" not in out


def test_a_package_method_is_not_a_constant(project, capsys):
    stage(project, "pkg/r/R/model.R",
          'Model <- R6::R6Class("Model", list(\n  fit = function(x) {\n    x * 0.5\n  }\n))\n')
    code, out = gate(project, capsys)
    assert code == 1 and "pkg/r/R/model.R:3: typed number 0.5" in out


def test_files_mode_compares_with_a_given_base(project, capsys):
    start = git(project, "rev-parse", "HEAD").strip()
    write(project / "analysis" / "run.R", OLD_R + "z <- 2019\n")
    git(project, "commit", "-q", "-am", "committed without the hook")
    assert lint_code.main(["--project", str(project), "--files", "analysis/run.R"]) == 0
    capsys.readouterr()
    assert lint_code.main(["--project", str(project), "--files", "analysis/run.R", "--base", start]) == 1
    out = capsys.readouterr().out
    assert "analysis/run.R:3: typed number 2019" in out and "typed number 30" not in out
    assert lint_code.main(["--project", str(project), "--files", "analysis/run.R", "--base", "none"]) == 1
    assert "analysis/run.R:2: typed number 30" in capsys.readouterr().out
    assert lint_code.main(["--project", str(project), "--files", "analysis/run.R", "--base", "nosuch"]) == 2


def test_an_extension_alone_is_not_a_path(project, capsys):
    stage(project, "analysis/run.R", OLD_R + 'f <- paste0(name, ".csv")\ng <- Sys.glob("*.csv")\n'
                                              'h <- sprintf("%s.pdf", name)\nk <- sprintf("%s_panel.csv", x)\n')
    code, out = gate(project, capsys)
    assert code == 1 and "analysis/run.R:6: typed path '%s_panel.csv'" in out
    assert ":3:" not in out and ":4:" not in out and ":5:" not in out


def test_a_parameter_file_the_kit_did_not_write_is_left_out(project, capsys):
    stage(project, "analysis/params.yml", "model:\n  lags: 3\n")
    stage(project, "analysis/run.R", OLD_R + "n <- 0\n")
    assert lint_code.main(["--project", str(project), "--precommit"]) == 0
    assert "analysis/params.yml is not the kit's parameter file" in capsys.readouterr().err


def test_files_mode_reports_parameter_problems_once(project, capsys):
    write(project / "analysis" / "params.yml", PARAMS + "late: 2019-01-01\n")
    write(project / "analysis" / "run.R", OLD_R + "z <- 2019\n")
    assert lint_code.main(["--project", str(project), "--files", "analysis/run.R"]) == 1
    captured = capsys.readouterr()
    assert captured.out.count("late: needs a comment line") == 1 and "typed number 2019" in captured.out


def test_a_pipeline_script_defines_no_functions(project, capsys):
    stage(project, "analysis/run.R", OLD_R + "fmt <- function(x) format(x, nsmall = 2)\n.helper <- \\(x) x\n"
                                              "y <- sapply(seq_len(n), function(i) i + 1)\n")
    stage(project, "analysis/fit.py", "class Spec:\n    pass\n\n\ndef estimate(d):\n    return d\n\n\n"
                                      "def main():\n    estimate(0)\n")
    assert lint_code.main(["--project", str(project), "--precommit"]) == 1
    out, err = capsys.readouterr()
    assert "analysis/run.R:3: defines fmt() in a pipeline script" in out
    assert "analysis/run.R:4: defines .helper() in a pipeline script" in out and "analysis/run.R:5:" not in out
    assert "analysis/fit.py:1: defines Spec()" in out and "analysis/fit.py:5: defines estimate()" in out
    assert "main()" not in out and "Move each function into the library" in err


def test_functions_are_fine_in_the_library_explore_tests_packages_and_the_readers(project, capsys):
    stage(project, "analysis/R/fit.R", "estimate <- function(d) d\n")
    stage(project, "analysis/explore/2026-11-25-q.R", "helper <- function(d) d\n")
    stage(project, "analysis/tests/test_fit.R", "check <- function() TRUE\n")
    stage(project, "pkg/r/R/core.R", "core <- function(x) x\n")
    reader = (Path(lint_code.__file__).parents[1] / "templates" / "params" / "params.py").read_text()
    stage(project, "analysis/params.py", reader)
    assert gate(project, capsys) == (0, "")


def test_editing_an_old_function_in_a_pipeline_script_passes(project, capsys):
    write(project / "analysis" / "old.R", "fmt <- function(x) {\n  format(x)\n}\n")
    git(project, "add", "analysis/old.R")
    git(project, "commit", "-q", "-m", "before the rule")
    stage(project, "analysis/old.R", "fmt <- function(x) {\n  format(x, big.mark = ',')\n}\n")
    assert gate(project, capsys) == (0, "")


def test_an_old_functions_def_line_may_change_and_its_file_may_move(project, capsys):
    body = "".join(f"    step{i} = x  # step {i}\n" for i in range(8)) + "    return x\n"
    write(project / "analysis" / "old.py", "def fmt(x):\n" + body)
    git(project, "add", "analysis/old.py")
    git(project, "commit", "-q", "-m", "before the rule")
    stage(project, "analysis/old.py", "def fmt(x, digits=None):\n" + body)
    assert gate(project, capsys) == (0, "")
    git(project, "commit", "-q", "--no-verify", "-m", "an argument")
    git(project, "mv", "analysis/old.py", "analysis/older.py")
    stage(project, "analysis/older.py", "def fmt(x, digits=None):\n" + body + "\n\ndef pct(x):\n    return x\n")
    code, out = gate(project, capsys)
    assert code == 1 and "defines pct()" in out and "fmt" not in out
    stage(project, "analysis/older.py", "def fmt(x, digits=0):\n" + body)
    assert lint_code.main(["--project", str(project), "--files", "analysis/older.py"]) == 0


def test_named_lambdas_count_and_the_run_all_script_may_keep_a_helper(project, capsys):
    stage(project, "analysis/run.py", "fmt = lambda x: x\n")
    stage(project, "analysis/run_all.R", 'run_step <- function(f) source(f)\nrun_step("analysis/sims/run.R")\n')
    code, out = gate(project, capsys)
    assert code == 1 and "analysis/run.py:1: defines fmt()" in out and "run_all" not in out


def test_without_a_library_the_remedy_says_to_name_one(tmp_path, capsys):
    p = minimal_project(tmp_path, CONFIG + "library: []\n")
    write(p / "analysis" / "params.yml", PARAMS)
    git(p, "init", "-q", "-b", "main")
    stage(p, "analysis/run.R", "fmt <- function(x) x\n")
    assert lint_code.main(["--project", str(p), "--precommit"]) == 1
    assert "The project has no library yet" in capsys.readouterr().err
