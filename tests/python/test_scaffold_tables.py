"""scaffold.py add-tables (table writer spec): where the writer goes, the settings it appends, its refusals, the
commit, and the writer passing the code gate where it lands."""
import pytest

import code_map
import kit_params
import lint_code
from build_fixture import CONFIG, git, init_repo, minimal_project, write
from kitlib import PLUGIN_ROOT, KitError, personal_dir
from scaffold import main
from tables_add import TABLE_SETTINGS, cmd_add_tables

TEMPLATES = PLUGIN_ROOT / "templates" / "tables"
HEADER = "# The pipeline's parameters (research-kit).\n\n"
PARAMS = HEADER + "# The cleaned panel.\nanalysis_data: 'data/clean/panel.csv'\n"
ECON = "*:0.1,**:0.05,***:0.01"


def project(tmp_path, config=CONFIG + "library: [analysis/R]\n", files=None):
    p = minimal_project(tmp_path, config)
    write(p / "analysis" / "params.yml", PARAMS)
    for rel, text in (files if files is not None else {"analysis/R/lib.R": "load <- function() 1\n"}).items():
        write(p / rel, text)
    init_repo(p)
    return p


def entries(p):
    found, problems = kit_params.read_file(p / "analysis" / "params.yml")
    assert not problems, problems
    return {n: v for n, (v, _, _) in found.items()}


def committed(p):
    return sorted(git(p, "show", "--name-only", "--format=", "HEAD").split())


def clean(p):
    return git(p, "status", "--porcelain").strip() == ""


# --- what it writes ---------------------------------------------------------------------------------------------------
def test_an_r_folder_gets_the_writer_and_every_setting_in_one_commit(tmp_path, capsys):
    p = project(tmp_path)
    assert cmd_add_tables("r", p, stars=ECON) == ["analysis/R/tex_tables.R", "analysis/params.yml"]
    assert (p / "analysis/R/tex_tables.R").read_bytes() == (TEMPLATES / "tex_tables.R").read_bytes()
    assert committed(p) == ["analysis/R/tex_tables.R", "analysis/params.yml"] and clean(p)
    e = entries(p)
    assert set(TABLE_SETTINGS) <= set(e) and e["analysis_data"] == "data/clean/panel.csv"
    assert e["table_star_thresholds"] == [0.1, 0.05, 0.01] and e["table_star_markers"] == ["*", "**", "***"]
    assert e["table_notes_lead"] == "\\textit{Notes:}" and e["table_se_brackets"] == ["(", ")"]
    text = (p / "analysis" / "params.yml").read_text()
    assert "\n\n# The paper's table style, read by the table writer" in text
    assert "# p-value thresholds for the table stars, any order; [] for no stars\ntable_star_thresholds: " in text
    out = capsys.readouterr().out
    assert "analysis/R has no load.R: run scaffold.py add-loader analysis/R" in out
    assert "added 20 table settings" in out


def test_no_stars_and_markers_with_a_dagger(tmp_path):
    p = project(tmp_path)
    cmd_add_tables("r", p, no_stars=True)
    assert entries(p)["table_star_thresholds"] == [] and entries(p)["table_star_markers"] == []
    q = project(tmp_path / "q")
    cmd_add_tables("r", q, stars="\\dagger:0.1,*:0.05,**:0.01,***:0.001")
    assert entries(q)["table_star_markers"] == ["\\dagger", "*", "**", "***"]


def test_a_star_rule_must_be_chosen_and_nothing_changes_until_then(tmp_path, capsys):
    p = project(tmp_path)
    assert main(["add-tables", "r", "--project", str(p)]) == 2
    assert "choose a star rule: --stars" in capsys.readouterr().err
    assert clean(p) and not (p / "analysis/R/tex_tables.R").exists()
    for bad, msg in [("*:0.1,**:1.5", "between 0 and 1"), ("*:x", "is not a number"), ("0.1", "marker:threshold"),
                     ("+:0.1", "is not one of"), ("*:0.1,*:0.05", "given twice")]:
        with pytest.raises(KitError, match=msg):
            cmd_add_tables("r", p, stars=bad)
    assert clean(p)


def test_the_personal_file_is_read_entry_by_entry(tmp_path):
    write(personal_dir() / "table-style.yml", "# Mine (research-kit table style).\n\n# Two decimals.\n"
          "table_decimals: 2\n# My stars.\ntable_star_thresholds: [0.05, 0.01]\n# Their markers.\n"
          "table_star_markers: ['*', '**']\n")
    p = project(tmp_path)
    cmd_add_tables("r", p)
    e = entries(p)
    assert e["table_decimals"] == 2 and e["table_star_thresholds"] == [0.05, 0.01] and e["table_missing"] == "---"
    assert "# Two decimals.\ntable_decimals: 2" in (p / "analysis" / "params.yml").read_text()
    q = project(tmp_path / "q")
    cmd_add_tables("r", q, stars="*:0.1")                          # the flag replaces the file's rule
    assert entries(q)["table_star_thresholds"] == [0.1]


def test_a_typo_or_a_lone_star_entry_in_the_personal_file_is_refused(tmp_path):
    write(personal_dir() / "table-style.yml", "# Typo.\ntable_decimal: 2\n")
    p = project(tmp_path)
    with pytest.raises(KitError, match="table_decimal is not a table setting"):
        cmd_add_tables("r", p, stars=ECON)
    write(personal_dir() / "table-style.yml", "# Only one.\ntable_star_thresholds: [0.05]\n")
    with pytest.raises(KitError, match="sets only one of"):
        cmd_add_tables("r", p)
    assert clean(p)


def test_settings_already_there_are_kept_and_the_writer_rerun_is_current(tmp_path, capsys):
    p = project(tmp_path)
    cmd_add_tables("r", p, stars=ECON)
    capsys.readouterr()
    assert cmd_add_tables("r", p) == []
    out = capsys.readouterr().out
    assert "analysis/R/tex_tables.R is current" in out and "the writer and its settings are all there" in out
    text = (p / "analysis" / "params.yml").read_text()
    write(p / "analysis" / "params.yml", text.replace("# Row spacing", "# gone").replace("table_arraystretch: ''\n", "")
          .replace("table_decimals: 3", "table_decimals: 4"))
    write(p / "analysis/R/tex_tables.R", (TEMPLATES / "tex_tables.R").read_text() + "# our edit\n")
    git(p, "commit", "-q", "-am", "edit")
    assert cmd_add_tables("r", p) == ["analysis/params.yml"]          # the edited writer is kept
    assert "kept analysis/R/tex_tables.R: it differs" in capsys.readouterr().out
    assert entries(p)["table_decimals"] == 4 and entries(p)["table_arraystretch"] == ""
    assert (p / "analysis/R/tex_tables.R").read_text().endswith("# our edit\n")


# --- refusals ---------------------------------------------------------------------------------------------------------
def test_star_flags_and_existing_star_settings(tmp_path):
    p = project(tmp_path)
    cmd_add_tables("r", p, stars=ECON)
    with pytest.raises(KitError, match="already sets the star rule"):
        cmd_add_tables("r", p, no_stars=True)
    text = (p / "analysis" / "params.yml").read_text()
    write(p / "analysis" / "params.yml", text.replace("table_star_markers: ['*', '**', '***']\n", ""))
    git(p, "commit", "-q", "-am", "one star entry")
    with pytest.raises(KitError, match="has table_star_thresholds but not table_star_markers"):
        cmd_add_tables("r", p)


@pytest.mark.parametrize("setup,msg", [
    (lambda p: write(p / "analysis/R/tex_tables.R", "# mine\n"), "is not the kit's writer"),
    (lambda p: write(p / "analysis" / "explore" / "params.yml", HEADER + "# A try.\ntable_decimals: 2\n"),
     "table_decimals is in analysis/explore/params.yml"),
    (lambda p: write(p / "analysis" / "params.yml", "# mine\nx: 1\n"), "is not the kit's parameter file"),
    (lambda p: write(p / "analysis" / "params.yml", PARAMS + "bad line\n"), "fix the parameter files first"),
    (lambda p: (p / "analysis" / "params.yml").unlink(), "run scaffold.py add-params first"),
    (lambda p: write(p / "analysis/R/old.R", "tex_number <- function(x) x\n.tex_tables_fixed <- 1\n"),
     "analysis/R/old.R: .tex_tables_fixed; analysis/R/old.R: tex_number"),
])
def test_refusals_change_nothing(tmp_path, setup, msg):
    p = project(tmp_path)
    setup(p)
    git(p, "add", "-A")
    git(p, "commit", "-q", "-m", "setup")
    with pytest.raises(KitError, match=msg):
        cmd_add_tables("r", p, stars=ECON)
    assert clean(p) and git(p, "log", "-1", "--format=%s").strip() == "setup"


def test_uncommitted_params_and_a_language_not_in_the_project_are_refused(tmp_path):
    p = project(tmp_path)
    write(p / "analysis" / "params.yml", PARAMS + "# More.\ny: 2\n")
    with pytest.raises(KitError, match="analysis/params.yml has uncommitted changes"):
        cmd_add_tables("r", p, stars=ECON)
    with pytest.raises(KitError, match="languages in .claude/research.yml has no python"):
        cmd_add_tables("python", p, stars=ECON)


def test_a_failed_commit_is_rolled_back(tmp_path):
    p = project(tmp_path)
    hook = p / ".git" / "hooks" / "pre-commit"
    write(hook, "#!/bin/sh\necho 'code gate: 1 finding: a near copy' >&2\nexit 1\n")
    hook.chmod(0o755)
    with pytest.raises(KitError, match="(?s)a near copy.*rolled back; nothing was changed.*merge the two"):
        cmd_add_tables("r", p, stars=ECON)
    assert clean(p) and not (p / "analysis/R/tex_tables.R").exists()
    assert (p / "analysis" / "params.yml").read_text() == PARAMS


# --- where it goes ----------------------------------------------------------------------------------------------------
def test_several_folders_need_into_and_into_must_be_one_of_them(tmp_path):
    config = CONFIG + "library: [analysis/R, analysis/lib2, analysis/py, analysis/one.R]\n"
    files = {"analysis/R/a.R": "a <- function() 1\n", "analysis/lib2/README": "notes\n",
             "analysis/py/x.py": "def x():\n    return 1\n", "analysis/one.R": "b <- function() 2\n"}
    p = project(tmp_path, config, files)
    with pytest.raises(KitError, match=r"several library folders could hold the writer \(analysis/R, analysis/lib2\)"):
        cmd_add_tables("r", p, stars=ECON)
    with pytest.raises(KitError, match="analysis/py is not a library folder for R code"):
        cmd_add_tables("r", p, into="analysis/py", stars=ECON)
    assert cmd_add_tables("r", p, into="analysis/lib2/", stars=ECON)[0] == "analysis/lib2/tex_tables.R"


def test_a_library_of_files_only_is_refused(tmp_path):
    p = project(tmp_path, CONFIG + "library: [analysis/one.R]\n", {"analysis/one.R": "b <- 2\n"})
    with pytest.raises(KitError, match="no library folder for R code: add a folder to library:"):
        cmd_add_tables("r", p, stars=ECON)


NS = "# Generated by roxygen2: do not edit by hand\n\nexport(load_panel)\nexport(tex_number)\nimportFrom(stats,sd)\n"


def r_package(tmp_path, namespace=NS):
    config = CONFIG.replace("packages: {}", 'packages: {r: "mypkg"}')
    return project(tmp_path, config, {"pkg/r/R/data.R": "load_panel <- function() 1\n", "pkg/r/NAMESPACE": namespace,
                                      "pkg/r/DESCRIPTION": "Package: mypkg\n"})


def test_an_r_package_gets_exports_in_roxygens_layout(tmp_path, capsys):
    p = r_package(tmp_path)
    assert cmd_add_tables("r", p, stars=ECON) == ["pkg/r/R/tex_tables.R", "analysis/params.yml", "pkg/r/NAMESPACE"]
    ns = (p / "pkg/r/NAMESPACE").read_text()
    assert ns == ("# Generated by roxygen2: do not edit by hand\n\nexport(header_band)\nexport(interval_cell)\n"
                  "export(load_panel)\nexport(p_cell)\nexport(se_cell)\nexport(star_legend)\nexport(star_marker)\n"
                  "export(table_row)\nexport(table_style)\nexport(tex_number)\nexport(tex_table)\nexport(write_tex)\n"
                  "importFrom(stats,sd)\n")
    assert 'renv::install("./pkg/r")' in capsys.readouterr().out
    q = r_package(tmp_path / "q", "# Generated by roxygen2: do not edit by hand\n\nexportPattern(\"^[^.]\")\n")
    assert "pkg/r/NAMESPACE" not in cmd_add_tables("r", q, stars=ECON)


def test_a_hand_written_namespace_gets_the_lines_at_its_end(tmp_path):
    ns = "export(load_panel,\n       tex_number)\nif (getRversion() >= \"4.0\") {\n  S3method(print, x)\n}\n"
    p = r_package(tmp_path, ns)
    cmd_add_tables("r", p, stars=ECON)
    text = (p / "pkg/r/NAMESPACE").read_text()
    assert text.startswith(ns) and "export(tex_number)" not in text and text.endswith("export(write_tex)\n")
    assert text[len(ns):].splitlines()[0] == "export(header_band)"


def test_windows_line_endings_are_kept(tmp_path):
    p = project(tmp_path)
    write(p / "analysis" / "params.yml", "")
    (p / "analysis" / "params.yml").write_bytes(PARAMS.rstrip("\n").replace("\n", "\r\n").encode())
    git(p, "commit", "-q", "-am", "crlf")
    cmd_add_tables("r", p, stars=ECON)
    data = (p / "analysis" / "params.yml").read_bytes()
    assert data.startswith(PARAMS.rstrip("\n").replace("\n", "\r\n").encode() + b"\r\n\r\n# The paper's")
    assert b"\n" not in data.replace(b"\r\n", b"") and data.endswith(b"\r\n")
    assert git(p, "diff", "--numstat", "HEAD~1", "--", "analysis/params.yml").split()[1] == "1"


def test_a_second_copy_of_the_writer_is_refused_by_name(tmp_path):
    config = CONFIG + "library: [analysis/R, analysis/lib2]\n"
    p = project(tmp_path, config, {"analysis/R/a.R": "a <- function() 1\n", "analysis/lib2/b.R": "b <- function() 2\n"})
    cmd_add_tables("r", p, into="analysis/R", stars=ECON)
    with pytest.raises(KitError, match="the kit's writer is already in analysis/R/tex_tables.R; one copy per R library"):
        cmd_add_tables("r", p, into="analysis/lib2")


def test_a_python_package_and_a_python_folder(tmp_path):
    config = CONFIG.replace("[r]", "[python]").replace("packages: {}", 'packages: {python: "mypkg"}')
    p = project(tmp_path, config, {"pkg/python/src/mypkg/__init__.py": "", "pkg/python/src/mypkg/out.py":
                                   "def tex_table(rows):\n    return rows\n"})
    assert cmd_add_tables("python", p, stars=ECON)[0] == "pkg/python/src/mypkg/tex_tables.py"   # no clash check
    q = project(tmp_path / "q", CONFIG.replace("[r]", "[python]") + "library: [analysis/lib]\n",
                {"analysis/lib/__init__.py": ""})
    assert cmd_add_tables("python", q, stars=ECON)[0] == "analysis/lib/tex_tables.py"


# --- the writer where it lands ----------------------------------------------------------------------------------------
@pytest.mark.parametrize("kind", ["r folder", "r package", "python package", "python folder"])
def test_the_code_gate_finds_nothing_in_the_writer(tmp_path, capsys, kind):
    if kind == "r folder":
        p = project(tmp_path)
        target = cmd_add_tables("r", p, stars=ECON)[0]
    elif kind == "r package":
        p = r_package(tmp_path)
        target = cmd_add_tables("r", p, stars=ECON)[0]
    else:
        config = CONFIG.replace("[r]", "[python]")
        if kind == "python package":
            config = config.replace("packages: {}", 'packages: {python: "mypkg"}')
            p = project(tmp_path, config, {"pkg/python/src/mypkg/__init__.py": ""})
        else:
            p = project(tmp_path, config + "library: [analysis/lib]\n", {"analysis/lib/__init__.py": ""})
        target = cmd_add_tables("python", p, stars=ECON)[0]
    capsys.readouterr()
    assert lint_code.main(["--project", str(p), "--all", target]) == 0
    out = capsys.readouterr().out
    assert f"{target}:" not in out, out


def test_the_code_map_counts_the_table_settings_as_used(tmp_path, capsys):
    p = project(tmp_path)
    cmd_add_tables("r", p, stars=ECON)
    capsys.readouterr()
    assert code_map.main(["--project", str(p)]) == 0
    out = capsys.readouterr().out
    assert "21 parameters (1 unused)" in out.splitlines()[0]
    assert "table_decimals = 3  pipeline:" in out and "used in 1: analysis/R/tex_tables.R" in out
