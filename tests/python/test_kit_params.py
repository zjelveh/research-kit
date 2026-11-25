import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import kit_params
from build_fixture import write

READERS = Path(__file__).resolve().parents[2] / "plugins" / "kit" / "templates" / "params"

SAMPLE = """# Smallest group the tables report.
min_group_size: 20
# Tolerance for the solver.
tol: 1e-9
# Panel years.
panel_years: [1990, 2019]
# The cleaned analysis dataset.
analysis_data: 'data/analysis.parquet'
# Start of the paper window.
window_start: '2016-01-01'
# A label with a quote and a comma.
label: 'Women''s share, adults'
# Drop late adopters.
drop_late: true
# Cluster levels.
clusters: ['state_fips', 'region, district']
# A negative cutoff.
cutoff: -0.5
"""
EXPECTED = {"min_group_size": 20, "tol": 1e-9, "panel_years": [1990, 2019], "analysis_data": "data/analysis.parquet",
            "window_start": "2016-01-01", "label": "Women's share, adults", "drop_late": True,
            "clusters": ["state_fips", "region, district"], "cutoff": -0.5}


def test_the_format_reads_every_kind_of_value(tmp_path):
    entries, problems = kit_params.read_text(SAMPLE, "params.yml")
    assert problems == []
    assert {n: v for n, (v, _, _) in entries.items()} == EXPECTED
    assert entries["min_group_size"][1:] == (2, "Smallest group the tables report.")


@pytest.mark.parametrize("text, message", [
    ("min_group_size: 20\n", "needs a comment line"),
    ("# a\nstart: 2016-01-01\n", "single quotes"),
    ('# a\nname: "double"\n', "single quotes"),
    ("# a\nx: 3  # trailing\n", "single quotes"),
    ("# a\nx: 3\n# b\nx: 4\n", "already defined at line 2"),
    ("# a\nMin: 3\n", "expected `name: value`"),
    ("# a\n  x: 3\n", "expected `name: value`"),
    ("# a\nx: [1, [2]]\n", "numbers or single-quoted strings only"),
    ("# a\nx: [1, 2\n", "single quotes"),
    ("# a\nx: [true]\n", "numbers or single-quoted strings only"),
    ("# a\nx: [1, 'a']\n", "not both"),
    ("# a\n\nx: 3\n", "needs a comment line"),
])
def test_format_problems_are_named(text, message):
    _, problems = kit_params.read_text(text, "params.yml")
    assert problems and any(message in p for p in problems), problems


def test_a_name_lives_in_one_file_only(tmp_path):
    write(tmp_path / "analysis" / "params.yml", "# research-kit\n\n# a\nx: 1\n")
    write(tmp_path / "analysis" / "explore" / "params.yml", "# research-kit\n\n# b\nx: 2\n# c\ny: 3\n")
    pipe, expl, problems = kit_params.load(tmp_path)
    assert set(pipe) == {"x"} and set(expl) == {"x", "y"}
    assert problems == ["analysis/explore/params.yml:4: x is already a pipeline parameter (analysis/params.yml)"]


def test_load_takes_given_texts(tmp_path):
    write(tmp_path / "analysis" / "params.yml", "# research-kit\n\n# a\nx: 1\n")
    pipe, expl, _ = kit_params.load(tmp_path, {kit_params.PIPELINE: "# research-kit\n\n# a\nx: 5\n",
                                               kit_params.EXPLORE: None})
    assert pipe["x"][0] == 5 and expl == {}


def _project_with_sample(tmp_path):
    write(tmp_path / "analysis" / "params.yml", SAMPLE)
    write(tmp_path / "analysis" / "explore" / "params.yml", "# One-off.\nq_cutoff: 7\n")
    shutil.copy(READERS / "params.R", tmp_path / "analysis" / "params.R")
    shutil.copy(READERS / "params.py", tmp_path / "analysis" / "params.py")
    return tmp_path


def test_the_python_reader_matches_the_format(tmp_path):
    p = _project_with_sample(tmp_path)
    code = ("import json, sys; sys.path.insert(0, 'analysis'); from params import param\n"
            f"print(json.dumps({{n: param(n) for n in {sorted(EXPECTED) + ['q_cutoff']!r}}}))\n"
            "try:\n    param('nope')\nexcept KeyError as e:\n    print(e)\n")
    out = subprocess.run([sys.executable, "-c", code], cwd=p, capture_output=True, text=True, check=True).stdout
    values, error = out.splitlines()
    assert json.loads(values) == {**EXPECTED, "q_cutoff": 7}
    assert "no parameter 'nope'" in error


@pytest.mark.skipif(shutil.which("Rscript") is None, reason="R is not installed")
def test_the_r_reader_matches_the_format(tmp_path):
    p = _project_with_sample(tmp_path)
    names = sorted(EXPECTED) + ["q_cutoff"]
    code = ('source("analysis/params.R"); '
            f'for (n in c({", ".join(repr(n) for n in names)})) '
            'cat(n, "\\t", paste(param(n), collapse = "|"), "\\t", class(param(n)), "\\n", sep = ""); '
            'tryCatch(param("nope"), error = function(e) cat(conditionMessage(e), "\\n"))')
    out = subprocess.run(["Rscript", "--vanilla", "-e", code], cwd=p, capture_output=True, text=True,
                         check=True).stdout.splitlines()
    got = {line.split("\t")[0]: tuple(line.split("\t")[1:]) for line in out[:-1]}
    assert got["min_group_size"] == ("20", "numeric") and got["tol"] == ("1e-09", "numeric")
    assert got["panel_years"] == ("1990|2019", "numeric") and got["drop_late"] == ("TRUE", "logical")
    assert got["label"] == ("Women's share, adults", "character")
    assert got["clusters"] == ("state_fips|region, district", "character")
    assert got["cutoff"] == ("-0.5", "numeric") and got["q_cutoff"] == ("7", "numeric")
    assert "no parameter 'nope'" in out[-1]


def test_the_readers_refuse_a_name_defined_twice(tmp_path):
    p = _project_with_sample(tmp_path)
    write(p / "analysis" / "explore" / "params.yml", "# Again.\nmin_group_size: 7\n")
    py = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, 'analysis'); import params"],
                        cwd=p, capture_output=True, text=True)
    assert py.returncode != 0 and "defined twice" in py.stderr and "min_group_size" in py.stderr
    if shutil.which("Rscript"):
        r = subprocess.run(["Rscript", "--vanilla", "-e", 'source("analysis/params.R")'], cwd=p,
                           capture_output=True, text=True)
        assert r.returncode != 0 and "defined twice" in r.stderr and "min_group_size" in r.stderr


def test_the_templates_keep_their_header_out_of_the_first_entry():
    for rel in ("project/analysis/params.yml", "project/analysis/explore/params.yml"):
        template = (READERS.parent / rel).read_text()
        assert kit_params.kits(template) and template.endswith("\n\n")
        entries, problems = kit_params.read_text(template + "# Smallest group the tables report.\nn: 20\n", rel)
        assert problems == [] and entries["n"][2] == "Smallest group the tables report."
        _, problems = kit_params.read_text(template + "n: 20\n", rel)
        assert any("needs a comment line" in p for p in problems)


def test_foreign_files_are_named(tmp_path):
    write(tmp_path / "analysis" / "params.yml", "model:\n  lags: 3\n")
    assert kit_params.foreign(tmp_path)[0].startswith("analysis/params.yml is not the kit's parameter file")
    assert kit_params.load(tmp_path) == ({}, {}, [])


def _project_in_a_subfolder(tmp_path):
    """A project whose script runs from paper/, as a cascade that changes folder does."""
    p = _project_with_sample(tmp_path)
    write(p / ".claude" / "research.yml", "paper_dir: paper\n")
    (p / "paper").mkdir()
    return p


def test_the_python_reader_works_from_any_folder_and_needs_its_file(tmp_path):
    p = _project_in_a_subfolder(tmp_path)
    code = (f"import sys; sys.path.insert(0, {str(p / 'analysis')!r}); from params import param, param_path; "
            "print(param('tol')); print(param_path('analysis_data'))")
    run = subprocess.run([sys.executable, "-c", code], cwd=p / "paper", capture_output=True, text=True)
    assert run.returncode == 0 and run.stdout.split() == ["1e-09", str(p.resolve() / "data" / "analysis.parquet")]
    (p / "analysis" / "params.yml").unlink()
    run = subprocess.run([sys.executable, "-c", code], cwd=p / "paper", capture_output=True, text=True)
    assert run.returncode != 0 and "analysis/params.yml is missing" in run.stderr and "add-params" in run.stderr


@pytest.mark.skipif(shutil.which("Rscript") is None, reason="R is not installed")
def test_the_r_reader_works_from_any_folder_and_needs_its_file(tmp_path):
    p = _project_in_a_subfolder(tmp_path)
    sourced = 'source("../analysis/params.R"); cat(param("tol"), param_path("analysis_data"))'
    evaluated = (f'eval(parse({str(p / "analysis" / "params.R")!r})); '         # no file name: found by folder
                 'cat(param("tol"), param_path("analysis_data"))')
    for code in (sourced, evaluated):
        run = subprocess.run(["Rscript", "--vanilla", "-e", code], cwd=p / "paper", capture_output=True, text=True)
        assert run.returncode == 0, run.stderr
        tol, path = run.stdout.split()
        assert tol == "1e-09" and Path(path).resolve() == (p / "data" / "analysis.parquet").resolve()
    (p / "analysis" / "params.yml").unlink()
    run = subprocess.run(["Rscript", "--vanilla", "-e", sourced], cwd=p / "paper", capture_output=True, text=True)
    assert run.returncode != 0 and "analysis/params.yml is missing" in run.stderr


@pytest.mark.skipif(shutil.which("Rscript") is None, reason="R is not installed")
def test_the_r_reader_finds_its_files_when_sourced_from_sourced_scripts(tmp_path):
    p = _project_in_a_subfolder(tmp_path)
    write(p / "analysis" / "sims" / "run.R",
          'source("analysis/params.R")\ncat(param("tol"), param_path("analysis_data"), "\\n")\n')
    write(p / "run_all.R", 'source("analysis/sims/run.R")\n')
    write(p / "analysis" / "explore" / "2026-11-25-q.R", 'source("analysis/params.R")\ncat(param("tol"), "\\n")\n')
    for code in ('source("run_all.R")', 'source("analysis/sims/run.R")', 'source("analysis/explore/2026-11-25-q.R")',
                 'source("analysis/params.R", chdir = TRUE); cat(param("tol"), "\\n")'):
        run = subprocess.run(["Rscript", "--vanilla", "-e", code], cwd=p, capture_output=True, text=True)
        assert run.returncode == 0 and run.stdout.split()[0] == "1e-09", (code, run.stderr)
    run = subprocess.run(["Rscript", "--vanilla", "run_all.R"], cwd=p, capture_output=True, text=True)
    assert run.returncode == 0 and Path(run.stdout.split()[1]).resolve() == (p / "data" / "analysis.parquet").resolve()


def test_param_path_takes_absolute_and_home_paths_and_only_one_path(tmp_path):
    p = _project_in_a_subfolder(tmp_path)
    write(p / "analysis" / "explore" / "params.yml",
          "# research-kit\n\n# Mounted data.\nmounted: '/mnt/data/x.parquet'\n"
          "# Home data.\nhome: '~/data/x.csv'\n# Two files.\npair: ['a.csv', 'b.csv']\n")
    code = ("import sys, os; sys.path.insert(0, 'analysis'); from params import param_path\n"
            "from pathlib import Path\nprint(param_path('mounted'))\n"
            "print(param_path('home') == Path(os.path.expanduser('~/data/x.csv')))\n"
            "try:\n    param_path('pair')\nexcept TypeError as e:\n    print('refused')\n")
    out = subprocess.run([sys.executable, "-c", code], cwd=p, capture_output=True, text=True,
                         check=True).stdout.split()
    assert out == ["/mnt/data/x.parquet", "True", "refused"]
    if shutil.which("Rscript"):
        code = ('source("analysis/params.R"); cat(param_path("mounted"), '
                'param_path("home") == path.expand("~/data/x.csv"), '
                'tryCatch(param_path("pair"), error = function(e) "refused"), "\\n")')
        out = subprocess.run(["Rscript", "--vanilla", "-e", code], cwd=p, capture_output=True, text=True,
                             check=True).stdout.split()
        assert out == ["/mnt/data/x.parquet", "TRUE", "refused"]
