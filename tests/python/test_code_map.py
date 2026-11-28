import shutil

import pytest

import code_map
import code_scan
import lint_code
from build_fixture import CONFIG, git, minimal_project, write

LIB_CONFIG = CONFIG + "library: [analysis/R, analysis/paths.py]\n"

DATA_R = '''#' Load the cleaned panel.
#' @param path where it is
load_panel <- function(path = param("analysis_data")) {
  read.csv(path)
}

# Restrict to the paper's window.
# Uses the window parameters.
in_window <- function(d) d[d$date >= param("window_start"), ]

add_one <- function(x) x + 1  # adds one

.hidden <- function() NULL
'''

PATHS_PY = '''from params import param


def load(path=None):
    """Load the analysis dataset.

    More text."""
    return path or param("analysis_data")


class Panel:
    pass


def _private():
    pass
'''

HEADER = "# Parameters (research-kit).\n\n"
PARAMS = HEADER + """# The cleaned panel.
analysis_data: 'data/clean/panel.csv'
# Start of the paper's window.
window_start: '2016-01-01'
# Smallest group the tables report.
min_group_size: 20
"""

EXPLORE_PARAMS = HEADER + """# Start of the window for one quick question.
q_start: '2016-07-01'
"""

BLOCK = '''x1 <- load_panel()
x2 <- subset(x1, year > param("first_year"))
x3 <- merge(x2, controls, by = "state")
x4 <- aggregate(y ~ state, x3, mean)
x5 <- x4[order(x4$y), ]
x6 <- head(x5, param("top_n"))
x7 <- summary(x6)
'''

RUN_A = '''main <- function() NULL
fmt <- function(x) format(x, nsmall = 2)
d <- load_panel()
raw <- read.csv(param("analysis_data"))
''' + BLOCK + '''write_table(d, "tables/t1.tex")
'''

RUN_B = '''main <- function() NULL
fmt <- function(x) format(x, nsmall = 2)
''' + BLOCK + '''save(d, "t1.tex")
pdf("figures/f1.pdf")
'''

EXPLORE_PY = '''# Question: how many cases before the window?
from paths import load
from params import param

def helper():
    return load()

start = param("q_start")
'''


@pytest.fixture
def project(tmp_path):
    p = minimal_project(tmp_path, LIB_CONFIG)
    write(p / "analysis" / "R" / "data.R", DATA_R)
    write(p / "analysis" / "paths.py", PATHS_PY)
    write(p / "analysis" / "params.yml", PARAMS)
    write(p / "analysis" / "explore" / "params.yml", EXPLORE_PARAMS)
    write(p / "analysis" / "run_a.R", RUN_A)
    write(p / "analysis" / "run_b.R", RUN_B)
    write(p / "analysis" / "explore" / "2026-11-24-cases.py", EXPLORE_PY)
    write(p / "analysis" / "archive" / "old.R", BLOCK)
    write(p / "analysis" / "tests" / "test_paths.py", "from paths import load\n\ndef test_load():\n    load()\n")
    write(p / "paper" / "tables" / "t1.tex", "x\n")
    write(p / "paper" / "figures" / "f1.pdf", "x\n")
    write(p / ".gitignore", "paper/\n")
    git(p, "init", "-q", "-b", "main")
    git(p, "add", "-A")
    git(p, "commit", "-q", "-m", "init")
    return p


def out_of(capsys, project, *args):
    assert code_map.main(["--project", str(project), *args]) == 0
    return capsys.readouterr().out


def section(text, title):
    return text.split(f"## {title}")[1].split("\n## ")[0]


def test_map_mode_lists_the_library_and_the_parameters(project, capsys):
    out = out_of(capsys, project)
    first = out.splitlines()[0]
    assert first.startswith("code map: 5 library functions (3 with no callers), 4 parameters (1 unused)")
    assert first.endswith("library: analysis/R, analysis/paths.py")
    assert "## Library functions" in out and "## Parameters" in out
    assert "## Repeats" not in out and "## Code check" not in out and "--all" in out


def test_descriptions_and_skipped_names(project, capsys):
    funcs = section(out_of(capsys, project), "Library functions")
    assert 'load_panel(path = param("analysis_data"))  analysis/R/data.R:3  callers: 2  Load the cleaned panel.' \
        in funcs
    assert "in_window(d)  analysis/R/data.R:9  callers: 0  Restrict to the paper's window." in funcs
    assert "add_one(x)  analysis/R/data.R:11  callers: 0  adds one" in funcs
    assert "load(path=None)  analysis/paths.py:4  callers: 1  Load the analysis dataset." in funcs
    assert "Panel()  analysis/paths.py:11  callers: 0  (no description)" in funcs
    assert ".hidden" not in funcs and "_private" not in funcs


def test_parameters_show_value_place_users_and_purpose(project, capsys):
    params = section(out_of(capsys, project), "Parameters")
    assert ("analysis_data = 'data/clean/panel.csv'  pipeline:4  used in 3: analysis/R/data.R, "
            "analysis/paths.py, analysis/run_a.R  The cleaned panel.") in params
    assert "min_group_size = 20  pipeline:8  used in 0  Smallest group the tables report." in params
    assert "q_start = '2016-07-01'  explore:4  used in 1: analysis/explore/2026-11-24-cases.py" in params


def test_files_mode_checks_only_the_given_files(project, capsys):
    out = out_of(capsys, project, "--files", "analysis/run_a.R")
    assert "## Library functions" not in out and "## Parameters" not in out
    assert section(out, "Code check").strip().splitlines()[-1] == "none"
    repeats = section(out, "Repeats")
    assert "fmt defined in analysis/run_a.R, analysis/run_b.R" in repeats and "main" not in repeats
    assert "7 lines: analysis/run_a.R:5-11, analysis/run_b.R:3-9" in repeats
    assert "tables/t1.tex: analysis/run_a.R, analysis/run_b.R" in section(out, "Paper outputs with several writers")
    assert "analysis/run_a.R:4  reads analysis_data" in section(out, "Direct reads")
    explore = out_of(capsys, project, "--files", "analysis/explore/2026-11-24-cases.py", "analysis/gone.R")
    assert "fmt defined" not in explore and "reads analysis_data" not in explore


def test_files_mode_reports_typed_values_in_changed_lines(project, capsys):
    write(project / "analysis" / "run_a.R", RUN_A + "late <- subset(d, year > 2019)\n")
    typed = section(out_of(capsys, project, "--files", "analysis/run_a.R"), "Code check")
    assert "analysis/run_a.R:13: typed number 2019" in typed


def test_all_mode_adds_functions_outside_and_the_backlog(project, capsys):
    out = out_of(capsys, project, "--all")
    assert "analysis/run_a.R: fmt" in section(out, "Functions outside the library")
    assert "analysis/explore/2026-11-24-cases.py: helper" in out
    assert "code gate backlog: " in section(out, "Code check")


def test_summary_counts(project, capsys):
    first = out_of(capsys, project, "--files", "analysis/run_a.R").splitlines()[0]
    assert "3 functions outside the library" in first
    assert "2 repeats in pipeline code (0 in explore, 1 with archive copies)" in first
    assert "1 output with several writers" in first and "1 direct read of library data" in first


def test_test_files_are_not_callers_or_reported(project, capsys):
    out = out_of(capsys, project, "--all")
    assert "test_paths" not in out and "test_load" not in out
    assert "load(path=None)  analysis/paths.py:4  callers: 1" in out   # the explore script, not the test


def test_classes():
    lib = ["analysis/R", "analysis/paths.py"]
    assert code_scan.classify("analysis/R/x.R", lib) == "library"
    assert code_scan.classify("analysis/paths.py", lib) == "library"
    assert code_scan.classify("analysis/paths_old.py", lib) == "pipeline"
    assert code_scan.classify("analysis/R/tests/test_x.R", lib) == "test"
    assert code_scan.classify("pkg/python/tests/conftest.py", lib) == "test"
    assert code_scan.classify("analysis/explore/archive/x.R", lib) == "archive"
    assert code_scan.classify("notes/lit/searches/s.py", lib) == "archive"
    assert code_scan.classify("analysis/scratch_work/x.py", lib) == "explore"
    assert code_scan.classify("analysis/scratch.R", lib) == "pipeline"


def test_uncommitted_script_is_seen(project, capsys):
    write(project / "analysis" / "new.R", 'x <- read.csv("data/clean/panel.csv")\n')
    out = out_of(capsys, project, "--files", "analysis/new.R")
    assert "analysis/new.R:1: typed path 'data/clean/panel.csv' (it is param('analysis_data'))" in out
    assert "warning" not in out


def test_ignored_library_code_is_warned_about(project, capsys):
    write(project / ".gitignore", "paper/\nanalysis/R/secret.R\n")
    write(project / "analysis" / "R" / "secret.R", "s <- function() 1\n")
    out = out_of(capsys, project)
    assert "warning: git ignores 1 library code file: analysis/R/secret.R" in out
    assert "analysis/R/secret.R:" not in section(out, "Library functions")


def test_uncommitted_library_file_is_not_warned_about(project, capsys):
    write(project / "analysis" / "R" / "more.R", "#' More.\nmore <- function() 1\n")
    out = out_of(capsys, project)
    assert "warning" not in out and "more()  analysis/R/more.R:2  callers: 0  More." in out


def test_parameter_file_problems_are_warnings(project, capsys):
    write(project / "analysis" / "params.yml", PARAMS + "late: 2019-01-01\n")
    assert "warning: analysis/params.yml:9: late:" in out_of(capsys, project)


def test_paper_not_attached(project, capsys):
    shutil.rmtree(project / "paper")
    assert "paper not attached" in out_of(capsys, project, "--all").splitlines()[0]


def test_empty_library_means_none(tmp_path, capsys):
    p = minimal_project(tmp_path, CONFIG + "library: []\n")
    write(p / "analysis" / "a.R", "f <- function() 1\n")
    git(p, "init", "-q", "-b", "main")
    out = out_of(capsys, p)
    assert out.splitlines()[0].endswith("library: none") and "no library" in out and "none yet" in out


def test_default_library_is_the_package(tmp_path, capsys):
    cfg = CONFIG.replace("languages: [r]", "languages: [python]").replace("packages: {}", 'packages: {python: "mypkg"}')
    p = minimal_project(tmp_path, cfg)
    write(p / "pkg" / "python" / "src" / "mypkg" / "core.py", 'def f():\n    """Does f."""\n')
    git(p, "init", "-q", "-b", "main")
    out = out_of(capsys, p)
    assert "library: pkg/python/src/mypkg" in out and "f()  pkg/python/src/mypkg/core.py:1  callers: 0  Does f." in out


def test_unparsable_python_is_noted(project, capsys):
    write(project / "analysis" / "py2.py", "print 'old'\n")
    assert "note: 1 Python file could not be parsed: analysis/py2.py" in out_of(capsys, project)


def test_copies_group_into_one_block_ranked_before_explore(project, capsys):
    for i in range(4):
        write(project / "analysis" / f"copy{i}.R", BLOCK)
    write(project / "analysis" / "twice.R", BLOCK + "y <- 1\n" + BLOCK)
    other = "".join(f"e{i} <- step{i}(e{i - 1})\n" for i in range(1, 8))
    write(project / "analysis" / "explore" / "a.R", other)
    write(project / "analysis" / "explore" / "b.R", other)
    repeats = section(out_of(capsys, project, "--all"), "Repeats").strip().splitlines()
    blocks = [line for line in repeats if " lines: " in line]
    assert len(blocks) == 2
    assert blocks[0].startswith("7 lines: ") and blocks[0].count("analysis/") == 8
    assert "analysis/twice.R:1-7" in blocks[0] and "analysis/twice.R:9-15" in blocks[0]
    assert blocks[1].startswith("7 lines: analysis/explore/a.R:1-7, analysis/explore/b.R:1-7")


@pytest.mark.parametrize("library, message", [("[analysis/nope]", "does not exist"),
                                              ("[../elsewhere]", "outside the project")])
def test_bad_library_entries_exit_2(tmp_path, capsys, library, message):
    p = minimal_project(tmp_path, CONFIG + f"library: {library}\n")
    git(p, "init", "-q", "-b", "main")
    assert code_map.main(["--project", str(p)]) == 2
    assert message in capsys.readouterr().err


def test_files_and_all_exclude_each_other(project):
    with pytest.raises(SystemExit) as e:
        code_map.main(["--project", str(project), "--all", "--files", "analysis/run_a.R"])
    assert e.value.code == 2


def test_not_a_git_repo_exits_2(tmp_path, capsys):
    p = minimal_project(tmp_path, LIB_CONFIG)
    write(p / "analysis" / "R" / "data.R", DATA_R)
    write(p / "analysis" / "paths.py", PATHS_PY)
    assert code_map.main(["--project", str(p)]) == 2


def test_review_section(project, tmp_path):
    text = code_map.review_section(project, ["analysis/run_a.R"])
    assert text.startswith("code map: ") and "\n### Code check" in text and "Library functions" not in text
    assert code_map.review_section(tmp_path / "elsewhere", ["a.R"]) == "not a kit project"
    p = minimal_project(tmp_path / "bad", CONFIG + "library: [analysis/nope]\n")
    assert code_map.review_section(p, ["a.R"]).startswith("code map unavailable: ")


def test_review_section_survives_any_error(project, monkeypatch):
    def broken(*_):
        raise OSError("unreadable file")
    monkeypatch.setattr(code_map, "build", broken)
    assert code_map.review_section(project, ["a.R"]) == "code map unavailable: unreadable file"


def test_writers_are_found_through_parameters(project, capsys):
    write(project / "analysis" / "params.yml", PARAMS + "# The headline table.\ntable_t2: 'paper/tables/t2.tex'\n")
    write(project / "paper" / "tables" / "t2.tex", "x\n")
    write(project / "analysis" / "t2_a.R", 'write(tab, param("table_t2"))\n')
    write(project / "analysis" / "t2_b.R", 'write(tab, param("table_t2"))\n')
    writers = section(out_of(capsys, project, "--all"), "Paper outputs with several writers")
    assert "tables/t2.tex: analysis/t2_a.R, analysis/t2_b.R" in writers


def test_review_section_counts_values_committed_since_the_start(project):
    start = git(project, "rev-parse", "HEAD").strip()
    write(project / "analysis" / "run_a.R", RUN_A + "late <- subset(d, year > 2019)\n")
    git(project, "commit", "-q", "-am", "committed without the hook")
    assert "typed number 2019" in code_map.review_section(project, ["analysis/run_a.R"], start)
    assert "typed number 2019" not in code_map.review_section(project, ["analysis/run_a.R"])


def test_a_result_file_read_through_a_parameter_is_not_a_direct_read(project, capsys):
    write(project / "analysis" / "params.yml", PARAMS + "# The simulation summary.\nsims_summary: 'out/summary.csv'\n")
    write(project / "analysis" / "numbers" / "make_numbers.R", 'x <- read.csv(param("sims_summary"))\n')
    reads = section(out_of(capsys, project, "--all"), "Direct reads")
    assert "make_numbers.R" not in reads and "analysis/run_a.R:4  reads analysis_data" in reads


def test_the_kits_reader_is_not_code_outside_the_library(project, capsys):
    write(project / "analysis" / "params.py", '"""The parameters, written by research-kit."""\n\n'
                                              "def param(name):\n    return name\n")
    write(project / "analysis" / "params.R", "settings <- function() list()\n")      # the project's own
    outside = section(out_of(capsys, project, "--all"), "Functions outside the library")
    assert "analysis/params.py" not in outside and "analysis/params.R: settings" in outside


def test_a_parameter_file_the_kit_did_not_write_is_a_warning(project, capsys):
    write(project / "analysis" / "params.yml", "model:\n  lags: 3\n")
    out = out_of(capsys, project)
    assert "warning: analysis/params.yml is not the kit's parameter file" in out and "lags" not in out


def test_review_section_from_the_empty_tree(project):
    empty = git(project, "hash-object", "-t", "tree", "/dev/null").strip()
    write(project / "analysis" / "run_a.R", RUN_A + "late <- subset(d, year > 2019)\n")
    git(project, "commit", "-q", "-am", "committed without the hook")
    text = code_map.review_section(project, ["analysis/run_a.R"], empty)
    assert "unavailable" not in text and "typed number 2019" in text and "typed path 'tables/t1.tex'" in text


def test_direct_reads_in_a_project_whose_library_is_a_package(tmp_path, capsys):
    cfg = CONFIG.replace("languages: [r]", "languages: [python]").replace("packages: {}", 'packages: {python: "mypkg"}')
    p = minimal_project(tmp_path, cfg)
    write(p / "pkg" / "python" / "src" / "mypkg" / "io.py",
          'import pandas as pd\n\n\ndef load_panel(path):\n    """Load the panel."""\n    return pd.read_parquet(path)\n')
    write(p / "analysis" / "params.yml", HEADER + "# The cleaned panel.\npanel: 'data/panel.parquet'\n")
    write(p / "analysis" / "good.py", 'from mypkg.io import load_panel\nd = load_panel(param("panel"))\n')
    write(p / "analysis" / "bypass.py", 'import pandas as pd\nd = pd.read_parquet(param("panel"))\n')
    git(p, "init", "-q", "-b", "main")
    reads = section(out_of(capsys, p, "--all"), "Direct reads")
    assert "analysis/bypass.py:2  reads panel" in reads and "good.py" not in reads


def test_passing_a_result_to_a_library_writer_is_not_library_data(project, capsys):
    write(project / "analysis" / "R" / "save.R", "save_table <- function(x, path) write.csv(x, path)\n")
    write(project / "analysis" / "params.yml", PARAMS + "# The simulation summary.\nsims_summary: 'out/summary.csv'\n")
    write(project / "analysis" / "sims.R", 'save_table(res, param("sims_summary"))\n')
    write(project / "analysis" / "numbers" / "make_numbers.R", 'x <- read.csv(param("sims_summary"))\n')
    reads = section(out_of(capsys, project, "--all"), "Direct reads")
    assert "make_numbers.R" not in reads and "analysis/run_a.R:4  reads analysis_data" in reads


POOL = """{name} <- function(d, min_cases) {{
  keep <- table(d$charge)
  d[d$charge %in% names(keep[keep >= min_cases]), ]
}}
"""


def test_near_copies_are_listed_for_changed_files_and_grouped_in_all(project, capsys):
    write(project / "analysis" / "R" / "pool.R", POOL.format(name="pool"))
    write(project / "analysis" / "tables.R", POOL.format(name="pool_for_table") + "x <- pool_for_table(d, 3)\n")
    write(project / "analysis" / "figure.R", POOL.format(name="fig_pool"))
    write(project / "analysis" / "explore" / "2026-11-25-q.R", POOL.format(name="q_pool"))
    out = out_of(capsys, project, "--files", "analysis/explore/2026-11-25-q.R")
    near = section(out, "Near copies").strip().splitlines()[1:]
    assert near == ["q_pool() analysis/explore/2026-11-25-q.R:1 is 100% alike pool() analysis/R/pool.R:1",
                    "q_pool() analysis/explore/2026-11-25-q.R:1 is 100% alike fig_pool() analysis/figure.R:1",
                    "q_pool() analysis/explore/2026-11-25-q.R:1 is 100% alike pool_for_table() analysis/tables.R:1"]
    assert "of near copies" not in out.splitlines()[0]          # grouping compares every pair: --all only
    out = out_of(capsys, project, "--all")
    assert "2 groups of near copies" in out.splitlines()[0]     # with the fixture's two fmt()
    assert section(out, "Near copies").strip().splitlines()[1:] == [
        "pool() analysis/R/pool.R:1, fig_pool() analysis/figure.R:1, pool_for_table() analysis/tables.R:1",
        "fmt() analysis/run_a.R:2, fmt() analysis/run_b.R:2"]
    assert "Near copies" not in out_of(capsys, project)                  # the plain map stays short


# The pipeline section (frozen results spec).

def pipeline_project(tmp_path, extra=""):
    p = minimal_project(tmp_path, CONFIG.replace("languages: [r]", "languages: [python]") + extra)
    write(p / "run_all.py", 'import subprocess\nsubprocess.run(["python", "analysis/make_fig.py"])\n')
    write(p / "analysis" / "make_fig.py", 'CSV = "out/es.csv"\nes = pd.read_csv(CSV)\n')
    write(p / "analysis" / "freeze_es.py", 'es.to_csv("out/es.csv")\n')
    write(p / "out" / "es.csv", "a\n1\n")
    write(p / ".gitignore", "out/\n")
    git(p, "init", "-q", "-b", "main")
    git(p, "add", "-A")
    git(p, "commit", "-q", "-m", "init")
    return p


def test_the_map_lists_files_the_pipeline_reads_but_doesnt_make(tmp_path, capsys):
    import frozen
    p = pipeline_project(tmp_path)
    assert code_map.main(["--project", str(p)]) == 0
    out = capsys.readouterr().out
    assert "pipeline: 2 files run, 1 file read but not made" in out.splitlines()[0]
    assert "out/es.csv  read by analysis/make_fig.py:2; written only by analysis/freeze_es.py:1" in out
    frozen.main(["add", "out/es.csv", "--made-by", "analysis/freeze_es.py", "--why", "kept", "--project", str(p)])
    capsys.readouterr()
    code_map.main(["--project", str(p)])
    out = capsys.readouterr().out
    assert "0 files read but not made, frozen: 1 declared, 1 to check" in out.splitlines()[0]
    assert "to check: out/es.csv: frozen, but git doesn't track it" in out
    write(p / "out" / "es.csv", "a\n2\n")
    code_map.main(["--project", str(p)])
    assert "to check: out/es.csv: frozen, but the file has changed" in capsys.readouterr().out


def test_the_map_says_when_there_is_no_run_all_and_warns_about_missing_entries(tmp_path, capsys):
    p = pipeline_project(tmp_path, "run_all: [cascade.sh, run_all.py]\n")
    (p / "run_all.py").rename(p / "elsewhere.py")
    code_map.main(["--project", str(p)])
    out = capsys.readouterr().out
    assert "warning: run_all entry run_all.py does not exist" in out
    q = pipeline_project(tmp_path / "q", "run_all: []\n")
    code_map.main(["--project", str(q)])
    out = capsys.readouterr().out
    assert "pipeline: no run-all script (run_all.R, run_all.py, or run_all: in research.yml)" in out
    assert "no run-all script: name the scripts that run the pipeline" in out


# Parameters a file reads by name (table writer spec).

def test_a_file_that_reads_parameters_by_name_uses_the_names_it_quotes(project, capsys):
    write(project / "analysis" / "R" / "style.R",
          'SETTINGS <- c("min_group_size")\nstyle <- function(param) lapply(SETTINGS, function(n) param(n))\n')
    write(project / "analysis" / "R" / "cols.R", 'seed_col <- function(d) d[["analysis_data"]]\n'
          'x <- function() param("q_start")\n')
    params = section(out_of(capsys, project), "Parameters")
    assert "min_group_size = 20  pipeline:8  used in 1: analysis/R/style.R" in params
    assert "analysis/R/cols.R" not in params.split("analysis_data")[1].split("\n")[0]


def test_the_by_name_rule_in_python_and_r():
    assert lint_code.reads_params_by_name("a.py", "for n in NAMES:\n    param(n)\n")
    assert not lint_code.reads_params_by_name("a.py", 'param("x")\n# param(n)\n"param(n)"\n')
    assert lint_code.reads_params_by_name("a.R", "v <- lapply(names, function(n) param(n))\n")
    assert not lint_code.reads_params_by_name("a.R", 'param("x")  # param(n)\nparam_path( "y")\n')
