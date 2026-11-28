"""The table writer (table writer spec): tex_tables.py directly, tex_tables.R through Rscript on the same cases,
the text they write passing the paper's table check, and the writer passing the code gate."""
import csv
import importlib.util
import math
import shutil
import subprocess
import sys

import pytest

import kit_params
import lint_tables
from build_fixture import CONFIG, init_repo, minimal_project, write
from kitlib import PLUGIN_ROOT

KIT = PLUGIN_ROOT.parents[1]
WRITER = PLUGIN_ROOT / "templates" / "tables"
CASES = KIT / "tests" / "fixtures" / "tex_tables_cases.csv"
HARNESS = KIT / "tests" / "r" / "tex_tables_cases.R"
DEFAULT = PLUGIN_ROOT / "defaults" / "table-style.yml"
R = pytest.mark.skipif(shutil.which("Rscript") is None, reason="R is not installed")

ECON = {"table_star_thresholds": "[0.1, 0.05, 0.01]", "table_star_markers": "['*', '**', '***']"}
STYLES = {
    "econ": ECON,
    "apa": {"table_star_thresholds": "[0.1, 0.05, 0.01, 0.001]",
            "table_star_markers": "['\\dagger', '*', '**', '***']", "table_p_leading_zero": "false",
            "table_p_decimals": "2", "table_thousands": "'\\,'", "table_se_brackets": "['[', ']']",
            "table_interval_brackets": "['(', ')']"},
    "none": {"table_star_thresholds": "[]", "table_star_markers": "[]", "table_thousands": "''",
             "table_decimals": "2", "table_missing": "''", "table_p_floor": "0.0001", "table_interval_sep": "'; '"},
    "braces": {**ECON, "table_thousands": "'{,}'", "table_notes_lead": "''", "table_size": "'small'",
               "table_tabcolsep": "'4pt'", "table_arraystretch": "'1.2'", "table_caption_period": "true",
               "table_notes_size": "''"},
}


def load_writer():
    spec = importlib.util.spec_from_file_location("tex_tables_under_test", WRITER / "tex_tables.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod                   # dataclasses look the module up while building the class
    spec.loader.exec_module(mod)
    return mod


tt = load_writer()


def params_text(overrides):
    """A params.yml holding the kit's default table settings with these entries replaced or added."""
    entries, problems = kit_params.read_text(DEFAULT.read_text(), "default")
    assert not problems
    lines = ["# Parameters for a test (research-kit)", ""]
    raw = {name: line.split(":", 1)[1].strip() for line in DEFAULT.read_text().splitlines()
           if (name := line.split(":", 1)[0]) in entries}
    for name, value in {**raw, **overrides}.items():
        lines += [f"# {name}", f"{name}: {value}", ""]
    return "\n".join(lines)


def style_of(overrides=ECON, **kw):
    entries, problems = kit_params.read_text(params_text(overrides), "test")
    assert not problems, problems

    def param(name):
        if name not in entries:
            raise KeyError(f"no parameter {name!r}")
        return entries[name][0]
    return tt.table_style(param, **kw)


# --- the Python harness, the same steps as tests/r/tex_tables_cases.R ----------------------------------------------
def run_cases(mod, style):
    def value(s):
        return float("nan") if s == "NA" else float(s) if s else None

    def one(r):
        d, plus = value(r["decimals"]), r["plus"] == "TRUE"
        fn = r["fn"]
        if fn == "number":
            return mod.tex_number(value(r["a"]), style, decimals=d, plus=plus, prefix=r["prefix"], suffix=r["suffix"])
        if fn == "se":
            return mod.se_cell(value(r["a"]), style, decimals=d)
        if fn == "interval":
            return mod.interval_cell(value(r["a"]), value(r["b"]), style, decimals=d)
        if fn == "p":
            return mod.p_cell(value(r["a"]), style)
        if fn == "star":
            return mod.star_marker(value(r["a"]), style)
        return mod.star_legend(style)
    out = []
    with open(CASES, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            try:
                got = one(r)
            except (TypeError, ValueError, KeyError):
                got = "ERROR"
            out.append(r["case"] + "\t" + got.replace("\n", "\\n"))
    band = mod.header_band([("Outcome A", "a1", "a2"), ("Outcome B", "b1", "b1")], ["a1", "a2", "b1", "n"])
    rows = [band[0], band[1], mod.table_row(["", "(1)", "(2)", "(3)", "N"]), "\\midrule",
            mod.table_row(["Treated", mod.tex_number(-0.1234, style) + mod.star_marker(0.004, style),
                           mod.tex_number(0.0004, style), mod.tex_number(2.5, style) + mod.star_marker(0.2, style),
                           mod.tex_number(12345, style, decimals=0)]),
            mod.table_row(["", mod.se_cell(0.05, style), mod.se_cell(0.0001, style), mod.se_cell(None, style), ""]),
            mod.table_row(["95\\% CI", mod.interval_cell(-0.2, -0.04, style), mod.interval_cell(-0.0004, 0.1, style),
                           mod.interval_cell(1, 4, style), ""]),
            mod.table_row(["p", mod.p_cell(0.004, style), mod.p_cell(0.0996, style), mod.p_cell(0.5, style), ""])]
    float_ = mod.tex_table("lcccc", rows, style, caption="Main results.", label="tab:main",
                           notes="Standard errors in brackets.", landscape=True)
    fragment = mod.tex_table("lcccc", rows[2:], style)
    plain = mod.tex_table("lc", [mod.table_row(["Mean", mod.tex_number(1.5, style)])], style)
    out += ["float\t" + float_.replace("\n", "\\n"), "fragment\t" + fragment.replace("\n", "\\n"),
            "plain\t" + plain.replace("\n", "\\n")]
    return "\n".join(out) + "\n"


def results(style_name):
    return dict(line.split("\t", 1) for line in run_cases(tt, style_of(STYLES[style_name])).splitlines())


# --- cells -----------------------------------------------------------------------------------------------------------
def test_numbers_print_a_real_minus_and_no_sign_on_zero():
    r = results("econ")
    assert (r["zero"], r["negzero"], r["tiny"], r["negtiny"]) == ("0.000", "0.000", "0.000", "0.000")
    assert r["neghalf"] == "$-$0.001" and r["half"] == "0.001"     # printf rounds the binary value
    assert r["tie15"] == "0.002" and r["tie25"] == "0.003" and r["classic"] == "2.67"
    assert r["negbig"] == "$-$1,234.5" and r["big"] == "1,234,567.891" and r["roundup"] == "1,000.000"
    assert (r["halfint"], r["neghalfint"]) == ("0", "0")
    assert (r["count"], r["small_count"], r["four_digits"]) == ("12,345", "999", "1,000")
    assert r["missing"] == "---" and r["seven"] == "0.000"


def test_plus_prefix_suffix_and_decimals():
    r = results("econ")
    assert (r["plus"], r["plus_zero"], r["plus_neg"]) == ("+0.100", "0.000", "$-$0.100")
    assert r["dollars"] == "$-$\\$1,500.25" and r["percent"] == "12.3\\%"
    assert r["dec_whole"] == "1.2346" and r["dec_half"] == "ERROR" and r["dec_big"] == "ERROR"


@pytest.mark.parametrize("sep,expected", [(",", "1,234,567"), ("{,}", "1{,}234{,}567"), ("\\,", "1\\,234\\,567"),
                                          ("", "1234567")])
def test_thousands_separators_are_joined_as_written(sep, expected):
    assert tt.tex_number(1234567, style_of(ECON, thousands=sep), decimals=0) == expected


class Float32Like:
    """Stands in for numpy's float32 (not a float subclass): unequal to itself when NaN."""
    def __init__(self, v):
        self.v = v

    def __ne__(self, other):
        return self.v != self.v

    def __float__(self):
        return self.v


def test_missing_values_of_every_kind_print_the_missing_cell(monkeypatch):
    style = style_of()
    for x in (None, float("nan"), math.nan, Float32Like(float("nan"))):
        assert tt.tex_number(x, style) == "---"
    assert tt.tex_number(Float32Like(-1.25), style) == "$-$1.250"
    na = type("NAType", (), {"__ne__": lambda self, o: (_ for _ in ()).throw(TypeError("ambiguous")),
                             "__bool__": lambda self: (_ for _ in ()).throw(TypeError("ambiguous"))})()
    monkeypatch.setitem(sys.modules, "pandas", type(sys)("pandas"))
    sys.modules["pandas"].NA = na                          # pandas' NA, recognised without importing pandas
    assert tt.tex_number(na, style) == "---" and tt.p_cell(na, style) == "---"


@pytest.mark.parametrize("x", [[1.0, 2.0], (1.0,), "1.0", True, float("inf"), -math.inf])
def test_one_number_at_a_time_and_no_infinity(x):
    with pytest.raises((TypeError, ValueError)):
        tt.tex_number(x, style_of())


def test_standard_errors_and_intervals():
    r = results("econ")
    assert r["se"] == "(0.012)" and r["se_big"] == "(1,234.5)" and r["se_missing"] == "---"
    assert r["iv_negtiny"] == "[$-$0.0004, 0.110]"
    assert r["iv_vtiny"] == "[$-$0.000000, 0.200]" and r["iv_postiny"] == "[0.000000, 3.000]"
    assert r["iv_neg"] == "[$-$1.5, $-$0.2]" and r["iv_missing"] == "---"
    a = results("apa")
    assert a["iv_negtiny"] == "($-$0.0004, 0.110)" and a["se"] == "[0.012]"
    assert results("none")["iv_neg"] == "[$-$1.5; $-$0.2]"


def test_stars_are_strict_and_the_legend_runs_from_the_largest_threshold():
    r = results("econ")
    assert [r[k] for k in ("s_00005", "s_001", "s_004", "s_005", "s_007", "s_01", "s_02", "s_missing")] == \
        ["$^{***}$", "$^{**}$", "$^{**}$", "$^{*}$", "$^{*}$", "", "", ""]
    assert r["legend"] == "$^{*}p<0.10$, $^{**}p<0.05$, $^{***}p<0.01$."
    a = results("apa")
    assert a["s_007"] == "$^{\\dagger}$" and a["s_0009"] == "$^{**}$" and a["s_0001"] == "$^{**}$"
    assert a["legend"] == "$^{\\dagger}p<.10$, $^{*}p<.05$, $^{**}p<.01$, $^{***}p<.001$."
    n = results("none")
    assert n["s_00005"] == "" and n["legend"] == ""


def test_p_values_never_cross_a_threshold_or_print_zero():
    r = results("econ")
    assert r["p_floor"] == "$<$0.001" and r["p_at_floor"] == "0.001"
    assert r["p_0499"] == "0.0499" and r["p_05"] == "0.050" and r["p_0501"] == "0.050"
    assert r["p_0996"] == "0.0996" and r["p_096"] == "0.096" and r["p_01"] == "0.100" and r["p_near1"] == "1.000"
    assert r["p_009999"] == "0.009999" and r["p_missing"] == "---"
    assert (r["p_negative"], r["p_above_one"], r["s_negative"]) == ("ERROR", "ERROR", "ERROR")
    assert (r["p_one"], r["p_zero"]) == ("1.000", "$<$0.001")
    a = results("apa")                                   # two decimals, no leading zero
    assert a["p_widen_zero"] == ".004" and a["p_096"] == ".096" and a["p_half"] == ".50" and a["p_floor"] == "$<$.001"
    assert results("none")["p_floor"] == "0.0004"         # floor 0.0001


# --- the style ------------------------------------------------------------------------------------------------------
def test_table_style_overrides_by_field_name_and_refuses_unknown_names():
    assert style_of(ECON, size="scriptsize").size == "scriptsize"
    with pytest.raises(TypeError, match="no setting named sise"):
        style_of(ECON, sise="small")


def test_table_style_needs_the_param_function():
    with pytest.raises(TypeError, match="pass the driver's param function"):
        tt.table_style({"table_decimals": 3})


def test_a_missing_setting_is_named():
    with pytest.raises(KeyError, match="no parameter table_star_thresholds in analysis/params.yml"):
        tt.table_style(lambda name: (_ for _ in ()).throw(KeyError(name)))


@pytest.mark.parametrize("overrides,msg", [
    ({"table_star_thresholds": "[0.1, 0.05]", "table_star_markers": "['*']"}, "1 markers for 2 thresholds"),
    ({"table_star_thresholds": "[0.1, 1.5]", "table_star_markers": "['*', '**']"}, "between 0 and 1"),
    ({"table_star_thresholds": "[0.1, 0.0000001]", "table_star_markers": "['*', '**']"}, "doesn't print exactly"),
    ({"table_star_thresholds": "[0.1, 0.1]", "table_star_markers": "['*', '**']"}, "given twice"),
    ({"table_star_thresholds": "[0.1]", "table_star_markers": "['+']"}, "is not one of"),
    ({**ECON, "table_decimals": "2.5"}, "whole number"),
    ({**ECON, "table_p_floor": "0"}, "table_p_floor"),
    ({**ECON, "table_caption_period": "'yes'"}, "true or false"),
    ({**ECON, "table_se_brackets": "['(']"}, "two strings"),
    ({**ECON, "table_size": "3"}, "not a string"),
    ({**ECON, "table_notes_width": "''"}, "table_notes_width: is empty"),
    ({**ECON, "table_notes_skip": "' '"}, "table_notes_skip: is empty"),
])
def test_table_style_checks_the_settings(overrides, msg):
    with pytest.raises(ValueError, match=msg):
        style_of(overrides)


def test_the_settings_list_agrees_with_the_default_file_and_both_writers():
    import tables_add
    entries, problems = kit_params.read_file(DEFAULT)
    assert not problems
    names = tuple(tables_add.TABLE_SETTINGS)
    assert names == tt.TABLE_SETTINGS
    assert set(entries) | {"table_star_thresholds", "table_star_markers"} == set(names)
    r_text = (WRITER / "tex_tables.R").read_text()
    block = r_text[r_text.index(".tex_tables_settings <- c("):r_text.index(")", r_text.index(".tex_tables_settings"))]
    assert tuple(n for n in names if f'"{n}"' in block) == names and block.count('"') == 2 * len(names)


# --- tables and files ----------------------------------------------------------------------------------------------
def test_tex_table_float_fragment_and_legend():
    r = results("econ")
    float_ = r["float"].replace("\\n", "\n")
    assert float_.startswith("\\begin{landscape}\n\\begin{table}[htbp]\n\\centering\n\\caption{Main results.}\n"
                             "\\label{tab:main}\n\\begingroup\n\\begin{tabular}{lcccc}\n\\toprule\n")
    assert "\\end{tabular}\n\\par\\vspace{6pt}\n\\begin{minipage}{\\linewidth}\\footnotesize\n\\textit{Notes:} " \
           "Standard errors in brackets. $^{*}p<0.10$, $^{**}p<0.05$, $^{***}p<0.01$.\n\\end{minipage}\n\\endgroup\n" \
           "\\end{table}\n\\end{landscape}\n" in float_
    assert "\\multicolumn{2}{c}{Outcome A} & \\multicolumn{1}{c}{Outcome B} &  \\\\" in float_
    assert "\\cmidrule(lr){2-3} \\cmidrule(lr){4-4}" in float_
    fragment = r["fragment"].replace("\\n", "\n")
    assert fragment.startswith("\\begingroup\n\\begin{tabular}") and "\\caption" not in fragment
    assert "$^{**}p<0.05$" in fragment                       # its rows still carry a marker
    assert r["plain"].replace("\\n", "\n") == ("\\begingroup\n\\begin{tabular}{lc}\n\\toprule\nMean & 1.500 \\\\\n"
                                               "\\bottomrule\n\\end{tabular}\n\\endgroup\n")
    b = results("braces")["float"].replace("\\n", "\n")
    assert "\\begingroup\n\\small\n\\setlength{\\tabcolsep}{4pt}\n\\renewcommand{\\arraystretch}{1.2}\n" in b
    assert "\\begin{minipage}{\\linewidth}\nStandard errors" in b and "12{,}345" in b


def test_tex_table_refusals():
    style = style_of()
    with pytest.raises(ValueError, match="needs a caption"):
        tt.tex_table("lc", ["a & b \\\\"], style, label="tab:x")
    with pytest.raises(ValueError, match="needs a caption"):
        tt.tex_table("lc", ["a & b \\\\"], style, landscape=True)
    with pytest.raises(ValueError, match="end with a period"):
        tt.tex_table("lc", ["a & b \\\\"], style_of(ECON, caption_period=True), caption="No period")
    assert tt.tex_table("lc", ["a \\\\"], style_of(ECON, placement=""), caption="X.").startswith(
        "\\begin{table}\n\\centering\n")
    with pytest.raises(TypeError, match="one string"):
        tt.write_tex(["a", "b"], "unused.tex")
    assert "\\textit{Notes:} $^{*}p<0.10$" in tt.tex_table("lc", ["a & 1$^{*}$ \\\\"], style)


def test_write_tex_names_the_script_by_its_base_name(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", [str(tmp_path / "deep" / "04_tables.py")])
    out = tt.write_tex("x\n", tmp_path / "paper" / "tables" / "t.tex")
    assert out.read_bytes() == b"% Generated by 04_tables.py; edit the code that writes it, not this file.\nx\n"
    tt.write_tex("x\n", tmp_path / "u.tex", made_by="")
    assert (tmp_path / "u.tex").read_text().startswith("% Generated; edit")


# --- R gives the same text ------------------------------------------------------------------------------------------
def style_project(tmp_path, name):
    p = tmp_path / name
    write(p / "analysis" / "params.yml", params_text(STYLES[name]))
    shutil.copyfile(PLUGIN_ROOT / "templates" / "params" / "params.R", p / "analysis" / "params.R")
    shutil.copyfile(PLUGIN_ROOT / "templates" / "params" / "params.py", p / "analysis" / "params.py")
    return p


def python_through_its_reader(p):
    spec = importlib.util.spec_from_file_location(f"params_{p.name}", p / "analysis" / "params.py")
    params = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(params)
    return run_cases(tt, tt.table_style(params.param))


@R
@pytest.mark.parametrize("name", sorted(STYLES))
def test_r_and_python_write_the_same_text(tmp_path, name):
    p = style_project(tmp_path, name)
    out = subprocess.run(["Rscript", "--vanilla", str(HARNESS), str(WRITER / "tex_tables.R"), str(CASES),
                          str(p / "r.txt")], cwd=p, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    r_lines = (p / "r.txt").read_text(encoding="utf-8").splitlines()
    py_lines = python_through_its_reader(p).splitlines()
    assert [a for a, b in zip(r_lines, py_lines) if a != b] == []
    assert len(r_lines) == len(py_lines)


R_SNIPPET = """
source("analysis/params.R"); source("{writer}")
style <- table_style(param)
check <- function(expr) tryCatch({{ expr; "ok" }}, error = function(e) "error")
message_of <- function(expr) tryCatch({{ expr; "ok" }}, error = function(e) conditionMessage(e))
broken <- function(name) stop("disk on fire")
cat(check(tex_number(c(1, 2), style)), check(tex_number(NA_character_, style)), tex_number(NA_integer_, style),
    check(table_style(param, sise = "small")), table_style(param, size = "small")$size, check(tex_number(1, style, 2.5)),
    tex_number(5L, style), message_of(table_style()), message_of(table_style(1)), message_of(table_style(broken)),
    check(write_tex(c("a", "b"), "x.tex")), sep = "|")
"""


@R
def test_r_specific_values(tmp_path):
    p = style_project(tmp_path, "econ")
    out = subprocess.run(["Rscript", "--vanilla", "-e", R_SNIPPET.format(writer=WRITER / "tex_tables.R")], cwd=p,
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.split("|") == ["error", "ok", "---", "error", "small", "error", "5.000",
                                     "table_style: pass the driver's param function: table_style(param)",
                                     "table_style: pass the driver's param function: table_style(param)",
                                     "disk on fire", "error"]


@R
def test_r_write_tex_names_the_sourced_script(tmp_path):
    p = style_project(tmp_path, "econ")
    write(p / "code" / "make_table.R", 'source("analysis/params.R"); source("{w}")\n'
          'write_tex("x\\n", "out/t.tex")\n'.replace("{w}", str(WRITER / "tex_tables.R")))
    write(p / "run_all.R", 'source("code/make_table.R")\n')
    out = subprocess.run(["Rscript", "--vanilla", "run_all.R"], cwd=p, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert (p / "out" / "t.tex").read_bytes() == b"% Generated by make_table.R; edit the code that writes it, not " \
                                                 b"this file.\nx\n"
    out = subprocess.run(["Rscript", "--vanilla", "code/make_table.R"], cwd=p, capture_output=True, text=True,
                         timeout=120)
    assert out.returncode == 0, out.stderr
    assert (p / "out" / "t.tex").read_text().startswith("% Generated by make_table.R;")


# --- the paper's table check passes -----------------------------------------------------------------------------------
DOC = "\\documentclass{article}\n\\begin{document}\n{body}\n\\end{document}\n"


@pytest.mark.parametrize("name", ["econ", "apa", "braces"])
def test_tables_the_writer_writes_pass_the_table_check(tmp_path, name):
    r = results(name)
    float_, fragment = r["float"].replace("\\n", "\n"), r["fragment"].replace("\\n", "\n")
    body = ("\\input{tables/main}\n\\begin{table}\n\\centering\n\\caption{A fragment.}\n\\input{tables/frag}\n"
            "\\end{table}\n")
    p = minimal_project(tmp_path)
    write(p / "paper" / "main.tex", DOC.replace("{body}", body))
    write(p / "paper" / ".lint_baseline", "0\n")
    tt.write_tex(float_, p / "paper" / "tables" / "main.tex", made_by="make_tables.py")
    tt.write_tex(fragment, p / "paper" / "tables" / "frag.tex", made_by="make_tables.py")
    init_repo(p / "paper", "main")
    res = lint_tables.check(p, lint_tables.load_config(p), "worktree")
    assert [(f.file, f.line, f.detail) for f in res.findings] == []
    assert res.warnings == []
