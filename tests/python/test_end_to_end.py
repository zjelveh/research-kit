import subprocess

import pytest

import check_pointers
import lint_numbers
import numbers_build
from build_fixture import bare_overleaf, write
from kit_env import needs_latexmk, needs_renv, needs_uv
from scaffold import cmd_attach, cmd_new, cmd_new_talk

pytestmark = [pytest.mark.real_env, needs_renv, needs_uv, needs_latexmk]
MAIN = "\\documentclass{article}\n\\begin{document}\nHello.\n\\end{document}\n"


def test_numbers_from_both_languages_reach_the_slides(tmp_path, capsys):
    bare = bare_overleaf(tmp_path, {"main.tex": MAIN})
    p = cmd_new("demo", tmp_path, ["r", "python"], {"r": None, "python": None})
    cmd_attach(str(bare), p)
    write(p / "analysis" / "sims" / "summary.csv", "coverage,bias\n0.9412,0.0123\n")
    r_path, py_path = p / "analysis/numbers/make_numbers.R", p / "analysis/numbers/make_numbers.py"
    r_path.write_text(r_path.read_text().replace(
        "entries <- list(\n",
        'library(demo)  # only in the renv project library\nentries <- list(\n  list(name = "coverageMain", value = read.csv("analysis/sims/summary.csv")$coverage[1],\n'
        '       format = "%.2f", src = "analysis/sims/summary.csv")\n'))  # no trailing comma: R's list() rejects one
    py_path.write_text(py_path.read_text().replace(
        "entries = [\n",
        "import csv\nimport demo  # only in the uv environment\nrow = next(csv.DictReader(open('analysis/sims/summary.csv')))\n"
        "entries = [\n    dict(name='biasMain', value=float(row['bias']), format='%.3f',\n"
        "         src='analysis/sims/summary.csv'),\n"))
    subprocess.run(["git", "-C", str(p), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(p), "commit", "-qm", "numbers"], check=True)
    assert numbers_build.main(["--project", str(p)]) == 0
    tex = (p / "paper/generated/numbers.tex").read_text()
    assert "\\newcommand{\\coverageMain}{0.94}" in tex and "\\newcommand{\\biasMain}{0.012}" in tex
    assert check_pointers.main(["--project", str(p)]) == 0
    talk = cmd_new_talk("demo", p).parent
    template = (talk / "talk.tex").read_text()
    old = "\\item Every number is a macro from the paper's generated files."
    assert old in template
    write(talk / "talk.tex", template.replace(
        old,
        "\\item Coverage \\coverageMain{} and bias \\biasMain{}."))
    (p / "paper" / "generated" / "notation.tex").write_text("% generated\n")
    r = subprocess.run(["latexmk", "-pdf", "-interaction=nonstopmode", "talk.tex"], cwd=talk,
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout[-3000:]
    assert lint_numbers.main(["--project", str(p), "--gate", "slides"]) == 0
    pp = p / "pyproject.toml"  # a stale lock must stop the build: proves `uv run --locked` is used
    pp.write_text(pp.read_text().replace('version = "0"', 'version = "0.1"', 1))
    capsys.readouterr()
    assert numbers_build.main(["--project", str(p)]) == 2
    assert "lock" in capsys.readouterr().err.lower()
