import pytest

import pipeline
from build_fixture import CONFIG, git, minimal_project, write


def follow(files, starts, library=()):
    return pipeline.follow(files, list(starts), list(library))


# --- what the pipeline runs ------------------------------------------------------------------------------

def test_an_r_run_all_runs_the_scripts_it_names_in_strings():
    files = {"analysis/run_all.R": 'run("stage 1", rscript, "analysis/a.R")\n',
             "analysis/a.R": "x <- 1\n", "analysis/b.R": "y <- 2\n"}
    assert follow(files, ["analysis/run_all.R"]) == {"analysis/run_all.R", "analysis/a.R"}


def test_a_shell_run_all_names_scripts_by_path_or_bare_name():
    files = {"run.sh": 'cd "$PAPER"\npool_run py plots/ \\\n  make_fig \\\n  make_table\npython $DIR/est.py  # also x.py\n'
                       'echo "split core budget"\n',
             "a/plots/make_fig.py": "", "a/tables/make_table.py": "", "a/est.py": "", "a/core.py": "",
             "a/x.py": "", "a/_archive/make_table.py": ""}
    assert follow(files, ["run.sh"]) == {"run.sh", "a/plots/make_fig.py", "a/tables/make_table.py", "a/est.py"}


def test_a_comment_after_a_backtick_is_a_comment():
    files = {"run.sh": "pool_run py e/ \\\n  `# make_old RETIRED` \\\n  make_new\n", "e/make_old.py": "",
             "e/make_new.py": ""}
    assert follow(files, ["run.sh"]) == {"run.sh", "e/make_new.py"}


def test_a_path_matches_only_at_a_slash():
    files = {"analysis/run_all.R": 'source("analysis/attribution.R")\n', "analysis/attribution.R": "",
             "analysis/tests/test-attribution.R": ""}
    assert follow(files, ["analysis/run_all.R"]) == {"analysis/run_all.R", "analysis/attribution.R"}


def test_other_code_is_followed_only_through_invocations_and_imports():
    files = {"run_all.py": 'import subprocess\nsubprocess.run(["python", "fig.py"])\n',
             "fig.py": ('"""Reads out.csv (made by freeze.py)."""\n'
                        'import lib.helpers\nfrom tools.va import est\n'
                        'raise SystemExit("run r$run in check.py first")  # see old.py\n'
                        'built_by = "maker.py"\n'
                        'exec(open("step.py").read())\n'),
             "freeze.py": "", "check.py": "", "old.py": "", "maker.py": "", "step.py": "",
             "lib/helpers.py": "", "tools/va/est.py": "", "other/tools/va.py": "x = 1\n"}
    assert follow(files, ["run_all.py"]) == {"run_all.py", "fig.py", "step.py", "lib/helpers.py",
                                             "tools/va/est.py", "other/tools/va.py"}


def test_r_source_is_followed_and_the_library_and_numbers_count():
    files = {"analysis/run_all.R": 'source("analysis/01_prep.R")\n',
             "analysis/01_prep.R": 'source("analysis/helpers.R")\nx <- 1\n', "analysis/helpers.R": "",
             "analysis/R/lib.R": "f <- function() 1\n", "analysis/numbers/make_numbers.R": "",
             "analysis/unused.R": ""}
    run = pipeline.follow(files, ["analysis/run_all.R"], ["analysis/R"], ["analysis/numbers/make_numbers.R"])
    assert run == {"analysis/run_all.R", "analysis/01_prep.R", "analysis/helpers.R", "analysis/R/lib.R",
                   "analysis/numbers/make_numbers.R"}


def test_run_alls_from_the_key_or_by_name():
    files = ["analysis/run_all.R", "analysis/explore/run_all.R", "archive/run_all.py", "x/run_cascade.sh"]
    assert pipeline.run_alls({}, files, []) == ["analysis/run_all.R"]
    assert pipeline.run_alls({"run_all": ["x/run_cascade.sh"]}, files, []) == ["x/run_cascade.sh"]
    assert pipeline.run_alls({"run_all": []}, files, []) is None
    assert pipeline.run_alls({}, ["analysis/a.R"], []) is None


# --- reads and writes ------------------------------------------------------------------------------------

def uses(text, f="a.py", params=None, root=None):
    u = pipeline.uses(f, text, params or {}, root)
    return dict(u.reads), dict(u.writes), dict(u.loose)


def test_literals_and_held_names_on_read_and_write_calls():
    reads, writes, _ = uses('CSV = ROOT / "out/es.csv"\n'
                            'OUT = DIR / "es_rows.csv"\n'
                            'es = pd.read_csv(CSV)\n'
                            'es.assign(x=1).to_csv(OUT, index=False)\n')
    assert reads == {"out/es.csv": [3]} and writes == {"es_rows.csv": [4]}


def test_a_frame_read_from_a_file_does_not_hold_the_file():
    reads, writes, _ = uses('r = pd.read_feather("data/big.feather")\n'
                            'x = r[r.a > 0].copy()\n'
                            'fr = pd.read_feather(r"data/big.feather"); fr = fr.copy()\n')
    assert reads == {"data/big.feather": [1, 3]} and writes == {}


def test_a_read_inside_a_write_statement_stays_a_read():
    reads, writes, _ = uses('write_csv(f(df, pd.read_csv(param_path("tests_file"))), param_path("out_file"))\n',
                            params={"tests_file": "res/tests.csv", "out_file": "res/abc.csv"})
    assert reads == {"res/tests.csv": [1]} and writes == {"res/abc.csv": [1]}


def test_r_writers_over_several_lines_and_cat_needs_a_file():
    reads, writes, _ = uses('writeLines(c("\\\\begin{table}",\n  "x",\n  "\\\\end{table}"),\n'
                            '           file.path(paths$tables, "table1.tex"))\n'
                            'cat("x.csv")\n'
                            'cat("done", file = "log.txt")\n'
                            'd <- readRDS(file.path("data", "clean.rds"))\n', f="a.R")
    assert writes == {"table1.tex": [1], "log.txt": [6]} and reads == {"clean.rds": [7]}


def test_open_modes():
    reads, writes, _ = uses('with open("a.json") as f: pass\nwith open("b.json", "w") as f: pass\n')
    assert reads == {"a.json": [1]} and writes == {"b.json": [2]}


def test_names_passed_to_helpers_are_loose_writes_only():
    _, writes, loose = uses('save_fig("fig2.pdf", 6, 4, g)\n'
                            'write_result_csv(res, sprintf("%s_%s.csv", a, b))\n'
                            'out = "res/x.csv"\n', f="a.R")
    assert writes == {} and loose == {"fig2.pdf": [1]}


def test_templates_are_globs_and_only_loose():
    _, writes, loose = uses('res.to_csv(Path(__file__).with_name(f"its_{variant}.csv"))\n'
                            'df.to_csv(".csv")\n')
    assert writes == {} and loose == {"its_*.csv": [1]}


def test_a_parameter_named_in_a_string_is_a_loose_write():
    _, writes, loose = uses('for key in ("est_file", "checks_file"):\n    write_csv(frame, param_path(key))\n',
                            params={"est_file": "res/est.csv", "checks_file": "res/checks.csv"})
    assert writes == {} and set(loose) == {"res/est.csv", "res/checks.csv"}


def test_data_names():
    assert pipeline.data_name("/proj/out/x.csv", "/proj") == "out/x.csv"
    assert pipeline.data_name("/elsewhere/x.csv", "/proj") is None
    assert pipeline.data_name("%s.csv") is None
    assert pipeline.data_name("res/%s_main.csv") == "res/*_main.csv"
    assert pipeline.data_name("x.R") is None


def test_comments_and_docstrings_are_not_read():
    reads, writes, _ = uses('"""Writes out.csv."""\n# df.to_csv("old.csv")\nx = 1\n')
    assert reads == {} and writes == {}


@pytest.mark.parametrize("a, b, same", [
    ("out/tables/es.csv", "es.csv", True), ("./es.csv", "es.csv", True), ("es.csv", "tables/es.csv", True),
    ("mes.csv", "es.csv", False), ("out/its_level.csv", "its_*.csv", True), ("a/es.csv", "b/es.csv", False),
])
def test_same_file(a, b, same):
    assert pipeline.same(a, b) is same


# --- files the pipeline reads but doesn't make -----------------------------------------------------------

FILES = {
    "run_all.py": 'import subprocess\nsubprocess.run(["python", "analysis/make_fig.py"])\n',
    "analysis/make_fig.py": 'CSV = "out/es.csv"\nes = pd.read_csv(CSV)\nraw = pd.read_csv("data/raw.csv")\n',
    "analysis/freeze_es.py": 'es.to_csv("out/es.csv")\n',
    "analysis/explore/look.py": 'pd.read_csv("out/other.csv")\n',
    "analysis/make_other.py": 'pd.DataFrame().to_csv("out/other.csv")\n',
}


def graph(files=FILES):
    return pipeline.graph(files, ["run_all.py"], [], {})


def test_the_frozen_case_is_listed_with_its_reader_and_writer():
    [x] = pipeline.unmade(graph(), [])
    assert (x.name, x.readers, x.writers) == ("out/es.csv", [("analysis/make_fig.py", 2)],
                                               [("analysis/freeze_es.py", 1)])
    assert pipeline.unmade(graph(), ["out/es.csv"]) == []


def test_a_pipeline_writer_or_no_writer_at_all_is_not_listed():
    files = dict(FILES)
    files["run_all.py"] += 'subprocess.run(["python", "analysis/freeze_es.py"])\n'
    assert pipeline.unmade(graph(files), []) == []


def test_resolve_tries_the_readers_folder_and_up(tmp_path):
    write(tmp_path / "a" / "out" / "es.csv", "x\n")
    write(tmp_path / "top.csv", "x\n")
    assert pipeline.resolve(tmp_path, "a/plots/fig.py", "out/es.csv") == "a/out/es.csv"
    assert pipeline.resolve(tmp_path, "a/plots/fig.py", "top.csv") == "top.csv"
    assert pipeline.resolve(tmp_path, "a/plots/fig.py", "none.csv") == "none.csv"


def test_paper_files_count_only_when_the_manuscript_names_them(tmp_path):
    p = minimal_project(tmp_path, CONFIG)
    write(p / "paper" / "main.tex", "\\includegraphics{figures/fig_used}\n\\input{tables/t_used}\n")
    for name in ("figures/fig_used.pdf", "figures/fig_old.pdf", "tables/t_used.tex", "figures/fig_made.pdf"):
        write(p / "paper" / name, "x\n")
    write(p / "paper" / "sections" / "s.tex", "\\includegraphics{figures/fig_made}\n")
    files = {"run_all.py": 'import subprocess\nsubprocess.run(["python", "make.py"])\n',
             "make.py": 'save_fig("fig_made", 6, 4)\n', "old.py": 'plt.savefig("paper/figures/fig_used.pdf")\n'}
    g = pipeline.graph(files, ["run_all.py"], [], {})
    found = {x.name: x.writers for x in pipeline.paper_unmade(p, pipeline_cfg(), files, g)}
    assert found == {"paper/figures/fig_used.pdf": [("old.py", 1)], "paper/tables/t_used.tex": []}


def pipeline_cfg():
    import yaml
    return yaml.safe_load(CONFIG)


def test_a_reader_that_builds_checks_or_shows_its_path_does_not_make_it():
    _, _, loose = uses('CSV = Path("out/es.csv")\n'
                       'path = param_path("es_file")\n'
                       'assert os.path.exists(CSV)\n'
                       'print(f"read {CSV}")\n'
                       'es = pd.read_csv(path)\n'
                       'cmp = pd.read_csv(CSV)\n'
                       'check(CSV)\n', params={"es_file": "out/es2.csv"})
    assert loose == {}                       # check(CSV) would count, but the file reads out/es.csv itself


def test_the_source_of_a_copy_is_read_and_annotated_assignments_hold_names():
    reads, writes, _ = uses('SRC: Path = ROOT / "raw/in.csv"\nshutil.copy(SRC, "out/copy.csv")\n')
    assert reads == {"raw/in.csv": [2]} and writes == {"out/copy.csv": [2]}


def test_a_make_variable_folder_is_any_folder():
    files = {"Makefile": "all:\n\tpython $(SRC)/make_fig.py\n", "code/make_fig.py": ""}
    assert follow(files, ["Makefile"]) == {"Makefile", "code/make_fig.py"}


def test_many_held_variables_stay_fast():
    import time
    text = "".join(f'V{i} = "out/f{i}.csv"\n' for i in range(1500)) + "pd.read_csv(V7)\n"
    start = time.time()
    reads, _, _ = uses(text)
    assert reads == {"out/f7.csv": [1501]} and time.time() - start < 5


def test_a_paper_table_written_through_a_path_parameter_is_made_by_the_pipeline(tmp_path):
    p = minimal_project(tmp_path, CONFIG)
    write(p / "paper" / "main.tex", "\\input{tables/balance}\n\\input{tables/other}\n")
    for name in ("tables/balance.tex", "tables/other.tex"):
        write(p / "paper" / name, "x\n")
    files = {"run_all.py": 'import subprocess\nsubprocess.run(["python", "make_tab.py"])\n',
             "make_tab.py": 'write_tex(tex_table("lc", rows, style), param_path("balance_tex"))\n'}
    g = pipeline.graph(files, ["run_all.py"], [], {"balance_tex": "paper/tables/balance.tex"})
    found = {x.name for x in pipeline.paper_unmade(p, pipeline_cfg(), files, g)}
    assert found == {"paper/tables/other.tex"}
