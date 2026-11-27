import pytest

import lint_tables
from build_fixture import git, init_repo, minimal_project, write

DOC = "\\documentclass{article}\n\\begin{document}\n{body}\n\\end{document}\n"
LEGEND = "$^{\\dagger}p<.10$, $^{*}p<.05$, $^{**}p<.01$, $^{***}p<.001$."


def table(rows, spec="lcc", notes=LEGEND, caption="Results."):
    return ("\\begin{table}\n\\caption{" + caption + "}\n\\begin{tabular}{" + spec + "}\n" + rows +
            "\n\\end{tabular}\n" + (f"\\par {notes}\n" if notes else "") + "\\end{table}\n")


def paper(tmp_path, body="Hello.", files=None, commit=True):
    p = minimal_project(tmp_path)
    write(p / "paper" / "main.tex", DOC.replace("{body}", body))
    write(p / "paper" / ".lint_baseline", "0\n")
    for name, text in (files or {}).items():
        write(p / "paper" / name, text)
    if commit:
        init_repo(p / "paper", "main")
    return p


def found(p, where="worktree"):
    res = lint_tables.check(p, lint_tables.load_config(p), where)
    return [(f.file, f.line, f.detail) for f in res.findings], res


def details(p, where="worktree"):
    return [d for _, _, d in found(p, where)[0]]


# --- hyphen for minus ------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("row,expected", [
    ("a & -0.18 & (0.04) \\\\", ["hyphen for minus: -0.18"]),
    ("a & (-0.18) & [-1.2, 3] \\\\", ["hyphen for minus: -0.18", "hyphen for minus: -1.2"]),
    ("a & -1,234 & -1{,}234.5 \\\\", ["hyphen for minus: -1,234", "hyphen for minus: -1{,}234.5"]),
    ("a & -.5 & -1e-05 \\\\", ["hyphen for minus: -.5", "hyphen for minus: -1e-05"]),
    ("a & -12.3\\% & 4 \\\\", ["hyphen for minus: -12.3\\%"]),
    ("a & $-$0.18 & $-0.18$ \\\\", []),
    ("a & \\ensuremath{-}0.18 & \\ensuremath{-0.18} \\\\", []),
    ("1990--2000 & 2016-01-01 & t-1 \\\\", []),
    ("a\\vspace{-2pt} & \\multirow{2}{*}[-1ex]{b} & c \\\\[-2pt]", []),
    ("a & \\addlinespace[-2pt] b & \\num{-0.5} \\\\", []),
    ("a & -0.18 & 1 \\\\ %table-ok: a label, not a number", []),
])
def test_hyphen_for_minus_in_cells(tmp_path, row, expected):
    p = paper(tmp_path, table(row))
    assert details(p) == expected


def test_siunitx_and_dcolumn_columns_set_their_own_minus(tmp_path):
    rows = "a & -0.18 & -0.18 & -0.18 & \\multicolumn{1}{c}{-0.5} \\\\"
    body = "\\newcolumntype{d}[1]{D{.}{.}{#1}}\n" + table(rows, spec="lSd{2}>{$}c<{$}S")
    assert details(paper(tmp_path, body)) == ["hyphen for minus: -0.5"]


def test_star_repeats_in_the_column_spec(tmp_path):
    body = table("a & -1 & -2 & -3 \\\\", spec="l*{2}{S}c")
    assert details(paper(tmp_path, body)) == ["hyphen for minus: -3"]


def test_numbers_outside_cells_are_not_checked(tmp_path):
    body = table("a & 1 \\\\", notes="The change was -0.5 points. " + LEGEND, caption="Change of -2.")
    assert details(paper(tmp_path, body)) == []


def test_tabular_outside_a_float_and_never_input_table_files(tmp_path):
    body = "\\begin{tabular}{lc}\na & -1 \\\\\n\\end{tabular}\n"
    p = paper(tmp_path, body, {"tables/unused.tex": "\\begin{tabular}{lc}\nb & -2^{**} \\\\\n\\end{tabular}\n"})
    got = found(p)[0]
    assert ("main.tex", 4, "hyphen for minus: -1") in got
    assert ("tables/unused.tex", 2, "hyphen for minus: -2") in got
    assert not any("legend" in d for _, _, d in got)            # never-input files get cell checks only


def test_input_in_place_reports_the_table_file_and_line(tmp_path):
    p = paper(tmp_path, "\\begin{table}\n\\input{tables/t1}\n" + LEGEND + "\n\\end{table}",
              {"tables/t1.tex": "\\begin{tabular}{lc}\na & 1 \\\\\nb & -0.3 \\\\\n\\end{tabular}\n"})
    assert found(p)[0] == [("tables/t1.tex", 3, "hyphen for minus: -0.3")]


def test_macros_in_generated_files(tmp_path):
    p = paper(tmp_path, "\\input{generated/numbers}\nSee \\gapLow.",
              {"generated/numbers.tex": "\\newcommand{\\gapLow}{-15.9}% src=x\n\\newcommand{\\ok}{\\ensuremath{-}1}\n",
               "tables/m.tex": "\\def\\lo{-8.3}\n\\newcommand{\\word}{-a}\n"})
    got = found(p)[0]
    assert ("generated/numbers.tex", 1, "hyphen for minus in \\gapLow: -15.9 (rerun numbers_build)") in got
    assert ("tables/m.tex", 1, "hyphen for minus in \\lo: -8.3") in got
    assert len(got) == 2


def test_a_file_reached_from_two_roots_counts_once(tmp_path):
    p = paper(tmp_path, "\\input{sections/a}", {"sections/a.tex": table("a & -1 \\\\")})
    assert details(p) == ["hyphen for minus: -1"]


# --- negative zero ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("cell", ["-0.0", "$-$0.00", "\\ensuremath{-}0.0", "[$-$0.0, 18.9]", "−0.0"])
def test_negative_zero_is_a_warning(tmp_path, cell):
    findings, res = found(paper(tmp_path, table(f"a & {cell} \\\\")))
    assert any("negative zero" in w and "interval" in w for w in res.warnings)
    assert all(d.startswith("hyphen") for _, _, d in findings)


# --- legends ---------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("notes", [
    LEGEND,
    "$^{\\dagger}$ $p<0.10$, * $p<0.05$, ** $p<0.01$, *** $p<0.001$.",
    "\\sym{\\dagger} \\(p<0.10\\), \\sym{*} \\(p<0.05\\), \\sym{**} \\(p<0.01\\), \\sym{***} \\(p<0.001\\)",
    "$^{\\dagger}p<10\\%$, $^{*}p<5\\%$, $^{**}p<1\\%$, $^{***}p<0.1\\%$",
    "***, **, * and $\\dagger$ denote significance at the 0.1\\%, 1\\%, 5\\% and 10\\% levels.",
    "Signif. codes: ***: 0.001, **: 0.01, *: 0.05, \\dagger: 0.10",
])
def test_legend_forms_are_recognised(tmp_path, notes):
    rows = "a & 1.2$^{***}$ & 0.4^{\\dagger} \\\\\nb & 0.3** & \\sym{*} \\\\"
    assert details(paper(tmp_path, table(rows, notes=notes))) == []


def test_stars_without_a_legend(tmp_path):
    p = paper(tmp_path, table("a & 1.2$^{***}$ & 0.4$^{**}$ \\\\", notes="Standard errors in parentheses."))
    assert details(p) == ["stars without a legend: **, ***"]


def test_a_starred_symbol_and_note_markers_are_not_stars_without_a_legend(tmp_path):
    rows = "Break-even $C^*$ & 7,750 \\\\\nUnit A & 2023$^{\\ddagger}$ \\\\\nUnit C & 2018$^{*}$ \\\\\nUnit B & ---$^{\\dagger}$ \\\\"
    notes = ("$^{*}$ Unit C is excluded. $^{\\dagger}$ Unit B had no rule. "
             "$^{\\ddagger}$ Unit A came later.")
    assert details(paper(tmp_path, table(rows, notes=notes))) == []
    assert details(paper(tmp_path / "b", table("a & 1.2$^{*}$ \\\\", notes="Notes."))) == ["stars without a legend: *"]


def test_legend_in_the_wrapper_of_an_input_table(tmp_path):
    p = paper(tmp_path, "\\begin{table}\n\\input{tables/t}\n\\begin{tablenotes}\\item " + LEGEND +
              "\\end{tablenotes}\n\\end{table}",
              {"tables/t.tex": "\\begin{tabular}{lc}\na & 1.2$^{***}$ \\\\\n\\end{tabular}\n"})
    assert details(p) == []


def test_notes_row_inside_the_tabular_is_a_legend(tmp_path):
    rows = ("a & 1.2$^{***}$ \\\\\n\\multicolumn{2}{l}{$^{*}$p$<$0.05; $^{**}$p$<$0.01; $^{***}$p$<$0.001} \\\\")
    assert details(paper(tmp_path, table(rows, notes=""))) == []


def test_legends_that_disagree(tmp_path):
    good = table("a & 1$^{*}$ \\\\")
    odd = table("a & 1$^{*}$ \\\\", notes="$^{*}p<.10$, $^{**}p<.05$, $^{***}p<.01$.")
    p = paper(tmp_path, good + good + odd + "\\begin{table}\\begin{tabular}{l}a\\end{tabular}"
              "$^{*}p<0.05$, $^{**}p \\leq .01$\\end{table}")
    assert details(p) == ["legend disagrees with the paper's: * p<.1 (most tables: .05), ** p<.05 (most tables: .01), "
                          "*** p<.01 (most tables: .001)"]


def test_legend_escape_and_line_escape_are_separate(tmp_path):
    a = table("a & 1$^{**}$ \\\\ %table-ok: a label", notes="See Table 1.")
    b = table("a & 1$^{**}$ \\\\", notes="Stars as in Table 1. %legend-ok: given in Table 1")
    assert details(paper(tmp_path, a + b)) == ["stars without a legend: **"]


# --- warnings that hold the baseline ---------------------------------------------------------------------------------
def test_unresolved_table_input_holds_the_baseline(tmp_path):
    p = paper(tmp_path, "\\input{glyphtounicode}\n\\input{tables/missing}")
    findings, res = found(p)
    assert res.hold and any("tables/missing" in w for w in res.warnings)
    assert not any("glyphtounicode" in w for w in res.warnings)


def test_a_file_the_scanner_cant_parse_is_skipped(tmp_path):
    p = paper(tmp_path, "\\input{tables/bad}\n\\input{tables/good}",
              {"tables/bad.tex": "\\begin{tabular}{lc}\na & $$-$0.003$ \\\\\n\\end{tabular}\n",
               "tables/good.tex": "\\begin{tabular}{lc}\na & -1 \\\\\n\\end{tabular}\n"})
    findings, res = found(p)
    assert [d for _, _, d in findings] == ["hyphen for minus: -1"]
    assert res.hold and any("tables/bad.tex: skipped" in w for w in res.warnings)


# --- the gate (through lint_numbers --precommit) ---------------------------------------------------------------------
# The tables live in tables/, which the number lint doesn't read, as in a real paper.
def tpaper(tmp_path, rows, files=None, commit=True):
    return paper(tmp_path, "\\input{tables/t}", {"tables/t.tex": table(rows), **(files or {})}, commit)


def retable(p, rows, extra=""):
    write(p / "paper" / "tables" / "t.tex", table(rows))
    if extra:
        write(p / "paper" / "main.tex", DOC.replace("{body}", "\\input{tables/t}" + extra))
    git(p / "paper", "add", "-A")


def run_gate(p):
    import lint_numbers
    return lint_numbers.main(["--project", str(p), "--gate", "paper", "--precommit"])


def staged(p):
    return git(p / "paper", "diff", "--cached", "--name-only").split()


def test_first_run_sets_the_baseline_from_head(tmp_path, capsys):
    p = tpaper(tmp_path, "a & -1 & -2 \\\\")
    assert run_gate(p) == 0
    assert (p / "paper" / ".lint_baseline_tables").read_text() == "2\n"
    assert ".lint_baseline_tables" in staged(p)
    assert "tables: baseline set to 2 (HEAD 2, staged 2) (staged)" in capsys.readouterr().out


def test_first_run_takes_the_lower_count_and_blocks_a_rise(tmp_path):
    p = tpaper(tmp_path, "a & -1 & -2 \\\\")
    retable(p, "a & -1 & 2 \\\\")
    assert run_gate(p) == 0
    assert (p / "paper" / ".lint_baseline_tables").read_text() == "1\n"
    git(p / "paper", "commit", "-q", "-m", "x")
    retable(p, "a & -1 & -2 \\\\")
    assert run_gate(p) == 1


def test_no_head_starts_at_zero(tmp_path):
    p = tpaper(tmp_path, "a & -1 \\\\", commit=False)
    git(p / "paper", "init", "-q", "-b", "main")
    git(p / "paper", "add", "-A")
    assert run_gate(p) == 1                  # a first commit with a hyphen minus is a rise from 0
    retable(p, "a & 1 \\\\")
    assert run_gate(p) == 0
    assert (p / "paper" / ".lint_baseline_tables").read_text() == "0\n"


def test_a_fall_lowers_and_stages_unless_held(tmp_path):
    p = tpaper(tmp_path, "a & -1 & -2 \\\\", {".lint_baseline_tables": "2\n"})
    retable(p, "a & -1 & 2 \\\\")
    assert run_gate(p) == 0
    assert (p / "paper" / ".lint_baseline_tables").read_text() == "1\n"
    git(p / "paper", "commit", "-q", "-m", "x")
    retable(p, "a & 1 & 2 \\\\", extra="\n\\input{tables/later}")
    assert run_gate(p) == 0
    assert (p / "paper" / ".lint_baseline_tables").read_text() == "1\n"     # held by the unresolved input


def test_both_checks_report_and_nothing_is_staged_when_either_blocks(tmp_path, capsys):
    p = tpaper(tmp_path, "a & 1 \\\\", {".lint_baseline_tables": "0\n", ".lint_baseline": "5\n"})
    write(p / "paper" / "main.tex", DOC.replace("{body}", "We had 3 cases. \\input{tables/t}"))
    retable(p, "a & -1 \\\\")
    assert run_gate(p) == 1
    out = capsys.readouterr().out
    assert "paper [index]: count=1 baseline=5 ok" in out and "tables [index]: count=1 baseline=0 REGRESSION" in out
    assert (p / "paper" / ".lint_baseline").read_text() == "5\n"
    assert sorted(staged(p)) == ["main.tex", "tables/t.tex"]


def test_an_error_wins_over_a_regression(tmp_path, capsys):
    p = tpaper(tmp_path, "a & 1 \\\\", {".lint_baseline_tables": "x\n"})
    write(p / "paper" / "main.tex", DOC.replace("{body}", "We had 3 cases. \\input{tables/t}"))
    git(p / "paper", "add", "main.tex")
    assert run_gate(p) == 2
    assert "table baseline must be one non-negative integer" in capsys.readouterr().err


def test_the_gate_reads_the_index(tmp_path):
    p = tpaper(tmp_path, "a & 1 \\\\", {".lint_baseline_tables": "0\n"})
    write(p / "paper" / "tables" / "t.tex", table("a & -1 \\\\"))                       # unstaged
    write(p / "paper" / "tables" / "new.tex", "\\begin{tabular}{l}\n-1 \\\\\n\\end{tabular}\n")  # untracked
    assert run_gate(p) == 0


def test_non_utf8_staged_table_is_an_error(tmp_path, capsys):
    p = paper(tmp_path, "\\input{tables/t}", {".lint_baseline_tables": "0\n",
                                              "tables/t.tex": "\\begin{tabular}{l}\n1 \\\\\n\\end{tabular}\n"})
    (p / "paper" / "tables" / "t.tex").write_bytes(b"\\begin{tabular}{l}\n\xff \\\\\n\\end{tabular}\n")
    git(p / "paper", "add", "tables/t.tex")
    assert run_gate(p) == 2
    assert "not valid UTF-8" in capsys.readouterr().err


# --- the command line and the report ---------------------------------------------------------------------------------
def test_cli_without_a_baseline_prints_none(tmp_path, capsys):
    p = paper(tmp_path, table("a & -1 \\\\"))
    assert lint_tables.main(["--project", str(p), "-v"]) == 0
    out = capsys.readouterr().out
    assert "count=1 baseline: none" in out and "main.tex:6: hyphen for minus: -1" in out


def test_write_baseline(tmp_path):
    p = paper(tmp_path, table("a & -1 \\\\"))
    assert lint_tables.main(["--project", str(p), "--write-baseline"]) == 0
    assert (p / "paper" / ".lint_baseline_tables").read_text() == "1\n"


def test_report_lists_the_less_common_form(tmp_path, capsys):
    body = (table("a & 14{,}918 & 3 \\\\") + table("a & 15,001 & 1 \\\\") + table("a & 16001 & 1 \\\\",
            caption="No period", notes="$^{*}p<0.05$."))
    p = paper(tmp_path, body)
    write(p / "slides" / "talk" / "talk.tex", "$^{*}p<0.10$")
    assert lint_tables.main(["--project", str(p), "--report"]) == 0
    out = capsys.readouterr().out
    assert "p-values: .05 2, 0.05 1; the less common form:" in out or "p-values: 0.05 1, .05 2" in out
    assert "captions:" in out and "thousands:" in out
    assert "slides: slides/talk/talk.tex: * p<.1, the paper's * p<.05" in out


# --- review fixes: layouts, column positions, stars, legends, speed ---------------------------------------------------
SUB = DOC.replace("{body}", "\\input{sections/results}")


def subpaper(tmp_path, files, globs='["ms/main.tex", "ms/sections/*.tex"]'):
    """A manuscript in a subfolder (ms/), with every section a root of its own."""
    from build_fixture import CONFIG, set_config
    p = minimal_project(tmp_path, CONFIG.replace("paper/generated/", "paper/ms/generated/"))
    set_config(p, 'globs: ["main.tex", "sections/*.tex"]', f"globs: {globs}")
    write(p / "paper" / ".lint_baseline", "0\n")
    for name, text in files.items():
        write(p / "paper" / "ms" / name, text)
    init_repo(p / "paper", "main")
    return p


def test_an_unresolved_table_input_in_a_subfolder_manuscript_holds(tmp_path):
    p = subpaper(tmp_path, {"main.tex": DOC.replace("{body}", "\\input{tables/missing}")})
    findings, res = found(p)
    assert res.hold and any("tables/missing" in w for w in res.warnings)


def test_an_input_that_resolves_from_one_root_is_resolved(tmp_path):
    p = subpaper(tmp_path, {"main.tex": SUB,
                            "sections/results.tex": "\\begin{table}\\input{tables/t1}\\end{table}\n",
                            "tables/t1.tex": "\\begin{tabular}{lc}\na & -1 \\\\\n\\end{tabular}\n"})
    findings, res = found(p)
    assert not res.hold and res.warnings == []
    assert [(f, d) for f, _, d in findings] == [("ms/tables/t1.tex", "hyphen for minus: -1")]


def test_column_types_defined_in_the_main_file_reach_every_section(tmp_path):
    main = DOC.replace("\\begin{document}", "\\newcolumntype{d}[1]{D{.}{.}{#1}}\n\\newcolumntype{N}{S[table-format=1.2]}"
                       "\n\\begin{document}").replace("{body}", "\\input{sections/results}")
    p = subpaper(tmp_path, {"main.tex": main,
                            "sections/results.tex": "\\begin{tabular}{ld{3}N}\na & -0.5 & -0.25 \\\\\n\\end{tabular}\n",
                            "tables/alone.tex": "\\begin{tabular}{ld{3}}\na & -0.5 \\\\\n\\end{tabular}\n"})
    assert details(p) == []


def test_a_subfile_with_its_own_document_is_read_for_its_body(tmp_path):
    sub = "\\documentclass[../main.tex]{subfiles}\n\\begin{document}\n\\begin{tabular}{l}\n-1 \\\\\n\\end{tabular}\n" \
          "\\end{document}\n"
    p = paper(tmp_path, "\\subfile{sections/a}\n\\begin{tabular}{l}\n-2 \\\\\n\\end{tabular}", {"sections/a.tex": sub})
    assert sorted(details(p)) == ["hyphen for minus: -1", "hyphen for minus: -2"]


def test_an_input_inside_a_macro_definition_is_not_a_file(tmp_path):
    p = paper(tmp_path, "\\newcommand{\\tabinput}[1]{\\input{tables/#1}}\nHello.")
    assert found(p)[1].warnings == [] and not found(p)[1].hold


def test_tables_inside_iffalse_and_comment_are_skipped(tmp_path):
    body = ("\\iffalse\n" + table("a & 1$^{***}$ & -1 \\\\", notes="None.") + "\\fi\n\\begin{comment}\n" +
            table("a & 1$^{***}$ \\\\", notes="None.") + "\\end{comment}\n\\iffalse \\input{tables/gone} \\fi")
    findings, res = found(paper(tmp_path, body))
    assert findings == [] and not res.hold


@pytest.mark.parametrize("rows,spec", [
    ("a & b & 1 \\\\\n\\midrule\n\\multicolumn{2}{l}{Mean} & -0.5 \\\\", "lcS"),
    ("a & b & 1 \\\\\n\\rowcolor{gray}\\multicolumn{2}{l}{Mean} & -0.5 \\\\", "lcS"),
    ("a & b & c & -0.5 \\\\", "l*{2}cS"),
    ("a & b & c & -0.5 \\\\", "l*2{c}S"),
    ("a & \\begin{tabular}{S}-0.5\\end{tabular} & 1 \\\\", "lcc"),
])
def test_column_positions(tmp_path, rows, spec):
    assert details(paper(tmp_path, table(rows, spec=spec))) == []


def test_one_finding_per_cell_and_per_position(tmp_path):
    p = paper(tmp_path, table("a & -0.1 & -0.1 \\\\\nb & [-0.5, -0.1] & 1 \\\\"))
    assert details(p) == ["hyphen for minus: -0.1", "hyphen for minus: -0.1",
                          "hyphen for minus: -0.5 (and 1 more in this cell)"]


@pytest.mark.parametrize("rows,notes", [
    ("$\\theta_1^*$ & 1 \\\\\n$x_{0}^{*}$ & $k_2^{*}$ \\\\", "None."),
    ("x1*x2 & 1 \\\\\nAge2*Female & 2 \\\\", "None."),
    ("Unit A & 2023* \\\\", "* Provisional figure."),
    ("Unit A & 2023$^{*}$ & 1$^{\\dagger}$ \\\\", "\\begin{tablenotes}\\item[*] Provisional. \\item[$\\dagger$] Revised."
     "\\end{tablenotes}"),
])
def test_symbols_that_are_not_significance_stars(tmp_path, rows, notes):
    assert details(paper(tmp_path, table(rows, spec="lcc", notes=notes))) == []


@pytest.mark.parametrize("notes", [
    "*** Significant at the 1 percent level. ** Significant at the 5 percent level. * Significant at the 10 "
    "percent level.",
    "***, **, and * denote significance at the 1, 5, and 10 percent levels.",
    "* significant at 10\\%; ** significant at 5\\%; *** significant at 1\\%",
    "* ($p<0.1$), ** ($p<0.05$), *** ($p<0.01$)",
    "*** p-value $<$ 0.01, ** p-value $<$ 0.05, * p-value $<$ 0.1",
])
def test_more_legend_wordings(tmp_path, notes):
    assert details(paper(tmp_path, table("a & 1.2$^{***}$ & 0.4** \\\\\nb & 0.3* & 1 \\\\", notes=notes))) == []


def test_kableextra_three_part_longtable(tmp_path):
    body = ("\\begin{ThreePartTable}\n\\begin{TableNotes}\n\\item " + LEGEND + "\n\\end{TableNotes}\n"
            "\\begin{longtable}{lc}\n\\caption{T.}\\\\\na & 1.2$^{***}$ \\\\\n\\insertTableNotes\n\\end{longtable}\n"
            "\\end{ThreePartTable}")
    assert details(paper(tmp_path, body)) == []


def test_a_tabular_outside_a_float_reports_its_legend_at_the_tabular(tmp_path):
    p = paper(tmp_path, "Intro.\n\\begin{tabular}{lc}\na & 1.2$^{**}$ \\\\\n\\end{tabular}")
    assert found(p)[0] == [("main.tex", 4, "stars without a legend: **")]


@pytest.mark.parametrize("text", [
    "\\multicolumn{6}{c}{" + "*" * 40 + "}",
    "* " * 40,
    "0.123***" + " " * 60 + "& " + "\\dagger " * 30,
    "***, " * 40 + " denote significance at the " + "1\\%, " * 40,
])
def test_legend_parsing_is_fast(tmp_path, text):
    import time
    p = paper(tmp_path, "\\begin{tabular}{l}\na \\\\\n\\end{tabular}\n\\begin{verbatim}\n" + text +
              "\n\\end{verbatim}\n" + text)
    t0 = time.monotonic()
    found(p)
    assert time.monotonic() - t0 < 1.0


# --- the gate's first run, edge cases ---------------------------------------------------------------------------------
def test_first_run_keeps_the_head_count_while_an_input_is_unresolved(tmp_path):
    p = tpaper(tmp_path, "a & -1 & -2 \\\\")
    retable(p, "a & 1 & 2 \\\\", extra="\n\\input{tables/later}")
    assert run_gate(p) == 0
    assert (p / "paper" / ".lint_baseline_tables").read_text() == "2\n"


def test_first_run_skips_a_file_that_cant_be_parsed_at_head(tmp_path):
    p = tpaper(tmp_path, "a & -1 \\\\", {"tables/bad.tex": "\\begin{tabular}{l}\n$$-$0.003$ \\\\\n\\end{tabular}\n"})
    retable(p, "a & -1 \\\\", extra="\n\\input{tables/bad}")
    assert run_gate(p) == 0
    assert (p / "paper" / ".lint_baseline_tables").read_text() == "1\n"


def test_first_run_uses_the_staged_count_when_head_isnt_utf8(tmp_path, capsys):
    p = tpaper(tmp_path, "a & -1 \\\\")
    (p / "paper" / "tables" / "t.tex").write_bytes(b"\\begin{tabular}{l}\n\xff -1 \\\\\n\\end{tabular}\n")
    git(p / "paper", "add", "-A")
    git(p / "paper", "commit", "-q", "-m", "latin-1")
    retable(p, "a & -1 & -2 \\\\")
    assert run_gate(p) == 0
    assert (p / "paper" / ".lint_baseline_tables").read_text() == "2\n"
    assert "HEAD can't be read" in capsys.readouterr().out


def test_a_staged_file_that_isnt_on_disk_is_read_from_the_index(tmp_path):
    p = tpaper(tmp_path, "a & 1 \\\\", {".lint_baseline_tables": "0\n"})
    retable(p, "a & -1 \\\\")
    (p / "paper" / "tables" / "t.tex").unlink()
    assert run_gate(p) == 1


# --- second review pass -----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("preamble", [
    "\\let\\ifdraft\\iffalse\n",
    "\\def\\hidden{\\iffalse}\n",
    "\\iffalse\n\\ifthenelse{\\boolean{x}}{a}{b}\n\\iftoggle{y}{a}{b}\n\\fi\n",
])
def test_conditional_idioms_dont_hide_the_rest_of_the_file(tmp_path, preamble):
    body = preamble + table("a & -1 & 1$^{**}$ \\\\", notes="None.")
    assert sorted(details(paper(tmp_path, body))) == ["hyphen for minus: -1", "stars without a legend: **"]


@pytest.mark.parametrize("notes", [
    "\\begin{tablenotes}\n\\item ***, **, * denote significance at the 1\\%, 5\\%, 10\\% levels.\n"
    "\\item Standard errors clustered by county (24 counties).\n\\end{tablenotes}",
    "Notes: ***, **, * denote significance at the 1\\%, 5\\%, and 10\\% levels.\nWe use 3 lags.",
    "***, **, * denote significance at the 1\\%, 5\\% and 10\\% levels (two-sided).\nColumn 2 adds 5 controls.",
    "{\\footnotesize ***, **, and * denote significance at the 1, 5, and 10 percent levels.} Sample of 1,234 cases.",
    "Significance levels: * 10\\%, ** 5\\%, *** 1\\%.",
])
def test_a_listed_legend_ends_with_its_sentence(tmp_path, notes):
    assert details(paper(tmp_path, table("a & 1.2$^{***}$ & 0.4** \\\\\nb & 0.3* & 1 \\\\", notes=notes))) == []


# --- final review pass ------------------------------------------------------------------------------------------------
OTHER = table("x & 1$^{**}$ \\\\", notes="$^{**}p<0.05$.") * 2


@pytest.mark.parametrize("rows,caption", [
    ("Outcome & Significant & Share \\\\\na & 0.5** 4.5\\% & 1 \\\\", "Results."),
    ("a & 0.5$^{**}$ 4.5\\% & 1 \\\\", "Significance of effects."),
    ("Significant share & 0.5** 12\\% & 1 \\\\", "Results."),
])
def test_a_starred_cell_with_a_percent_is_not_a_legend(tmp_path, rows, caption):
    p = paper(tmp_path, OTHER + table(rows, notes="$^{**}p<0.05$.", caption=caption))
    assert details(p) == []


def test_a_starred_cell_with_a_percent_still_needs_a_legend(tmp_path):
    p = paper(tmp_path, table("Significant change & 0.5$^{**}$ 4.5\\% \\\\", notes="None."))
    assert details(p) == ["stars without a legend: **"]


def test_confidence_levels_read_as_p_thresholds(tmp_path):
    a = table("a & 1$^{*}$ \\\\", notes="$^{*}p<0.10$, $^{**}p<0.05$.")
    b = table("a & 1$^{*}$ \\\\", notes="Significance levels: * 90\\%, ** 95\\%.")
    c = table("a & 1$^{*}$ \\\\", notes="* Significant at the 90\\% level. ** Significant at the 95\\% level.")
    assert details(paper(tmp_path, a + b + c)) == []


def test_many_iffalse_blocks_stay_fast(tmp_path):
    import time
    block = "\\iffalse\n" + "x {y} " * 300 + "\n\\fi\n"
    p = paper(tmp_path, block * 200 + table("a & -1 \\\\"))
    t0 = time.monotonic()
    assert details(p) == ["hyphen for minus: -1"]
    assert time.monotonic() - t0 < 2.0
