import pytest

from lint_numbers import LintParseError, lint_text


def toks(src: str) -> list[str]:
    return [f.token for f in lint_text(src, "t.tex")]


def located(src: str) -> list[tuple[int, str]]:
    return [(f.line, f.token) for f in lint_text(src, "t.tex")]


# --- Original rule clauses (spec §5.5) -------------------------------------------------
@pytest.mark.parametrize("src,expected", [
    ("We ran 500 draws.", ["500"]),
    ("Coverage was 0.94.", ["0.94"]),
    ("Since 2016 the rule held. %num-ok", []),
    ("Text % 42 in a comment", []),
    ("A 45\\% rate.", ["45"]),
    ("It cost \\$500.", ["500"]),
    ("Let $x_1 + x^2 = 3$.", []),
    ("$\\alpha = 0.05$", ["0.05"]),
    ("$\\alpha = 0.05$ %num-ok", []),
    ("\\[ y = 2x + 0.5 \\]", ["0.5"]),
    ("$$ n = 100 $$", []),
    ("\\( n = 10 \\)", []),
    ("\\begin{align} a &= 1 \\\\ b &= 2.5 \\end{align}", ["2.5"]),
    ("\\ensuremath{x_2}", []),
    ("\\section{Three 3 cases}", ["3"]),
    ("\\includegraphics[width=0.8\\textwidth]{fig1.pdf}", []),
    ("as shown \\citep[p.~12]{smith2020}.", []),
    ("See Section~\\ref{sec:2} and \\label{eq:3}.", []),
    ("\\item<2-> point \\only<3>{x}", []),
    ("\\vspace*{2em}", []),
    ("\\setlength{\\parindent}{0pt}", []),
    ("\\multicolumn{2}{c}{Total 7}", ["7"]),
    ("\\resizebox{0.9\\textwidth}{!}{content}", []),
    ("\\scalebox{0.8}{x}", []),
    ("\\begin{column}{0.5\\textwidth} text \\end{column}", []),
    ("\\begin{minipage}[t]{0.4\\textwidth}x\\end{minipage}", []),
    ("\\begin{tabular}{p{3cm}l} a & b \\end{tabular}", []),
    ("a\\\\[2pt] b", []),
    ("\\href{http://x.org/2020}{the 2 sites}", ["2"]),
    ("\\url{http://x.org/2020}", []),
    ("\\begin{verbatim}\ndf$x <- 3.5\n\\end{verbatim}", []),
    ("\\begin{lstlisting}[language=R]\nmean(df$x) # 50% done\n\\end{lstlisting}", []),
    ("\\begin{minted}{r}\nx <- df$y * 2.5\n\\end{minted}", []),
    ("Use \\verb|df$x[1:3]| here.", []),
    ("Use \\lstinline{df$x} and \\verb+a$b+ then 9.", ["9"]),
])
def test_rule_clauses(src, expected):
    assert toks(src) == expected


# --- Review fixes: % inside code/URLs must not hide later lines (C1) -------------------
@pytest.mark.parametrize("src,expected", [
    ("Use \\verb|50%|.\nWe ran 500 draws.\nWe had 12 sites.\n"
     "\\begin{tabular}{l|c} a & b \\end{tabular}\nThen 9.",
     [(2, "500"), (3, "12"), (5, "9")]),
    ("Run \\lstinline{df %>% filter(x > 2)} first.\nWe ran 500 draws in 2020.\n\\textbf{bold} 7 more.",
     [(2, "500"), (2, "2020"), (3, "7")]),
    ("\\verb|x %in% y| and 3", [(1, "3")]),
    ("\\lstinline{sprintf(\"%.2f\", x)} and 4", [(1, "4")]),
    ("\\url{https://x.org/a%20b} and 5", [(1, "5")]),
    ("\\href{https://x.org/a%20b}{site 6}", [(1, "6")]),
])
def test_percent_inside_code_and_urls(src, expected):
    assert located(src) == expected


# --- Review fixes: skip rules apply inside math (I1); \text is prose ---------------------
@pytest.mark.parametrize("src,expected", [
    ("\\begin{align} a &= b \\\\[0.5ex] c &= d \\end{align}", []),
    ("\\( x \\eqref{eq:2.3} \\)", []),
    ("\\begin{equation} x \\label{eq:a.1} \\end{equation}", []),
    ("\\[ x \\hspace{0.5em} y \\]", []),
    ("\\begin{equation} x \\text{\\citep[Eq.~2.1]{a}} \\end{equation}", []),
    ("$a \\text{ for all $i > 1$ with } c$", []),
    ("$x = 1 \\text{ we ran 500 draws}$", ["500"]),
    ("\\begin{equation} x % 2.5 note\n= y \\end{equation}", []),
    ("\\begin{equation} x % \\end{equation} fake\n = 0.5 \\end{equation}", ["0.5"]),
    ("$x \\tag{A.1}$", []),
])
def test_math_mode_rules(src, expected):
    assert toks(src) == expected


# --- Review fixes: cite commands (I2), optional args (I3), unbraced args (I4), minor ---
@pytest.mark.parametrize("src,expected", [
    ("\\Citet{abadie2010} show that", []),
    ("\\Citep[p.~12]{abadie2010}", []),
    ("\\Citeauthor{abadie2010}", []),
    ("\\citereset and 3", ["3"]),
    ("\\newcommand{\\foo}[1]{#1 x}", []),
    ("\\scalebox{0.8}[1.2]{x}", []),
    ("\\item [1.] first", []),
    ("a\\\\*[2pt] b", []),
    ("\\setlength\\tabcolsep{4pt}", []),
    ("\\vspace\\baselineskip", []),
    ("\\begin {equation} x = 0.5 \\end{equation}", ["0.5"]),
    ("\\input main", []),
    ("\\item[a[b] text 3", ["3"]),
    ("\\ifnum\\x<3 a\\fi", ["3"]),
    ("A rate of 45\\%num-ok", ["45"]),
])
def test_review_fixes(src, expected):
    assert toks(src) == expected


# --- Policy decisions approved 2026-10-07 ----------------------------------------------
@pytest.mark.parametrize("src,expected", [
    # 1. TikZ / pgfplots skipped whole
    ("\\begin{tikzpicture}\n\\node (X) at (0,0) {X};\n\\end{tikzpicture}", []),
    ("\\begin{axis}[xmin=0]\n\\addplot coordinates {(0,0.5)};\n\\end{axis}", []),
    # 2. table/layout command arguments skipped; table cells still flagged
    ("\\cline{2-3} \\cmidrule(lr){2-4} \\multirow{2}{*}{a} \\renewcommand{\\arraystretch}{1.2} "
     "\\setcounter{page}{0} \\phantom{0} \\parbox{3cm}{t} \\raisebox{2pt}{t} \\rule{0pt}{2ex}", []),
    ("\\begin{tabular}{lc} a & 0.94 \\\\ b & 100 \\end{tabular}", ["0.94", "100"]),
    ("\\begin{subfigure}[b]{0.48\\textwidth} x \\end{subfigure}", []),
    ("\\begin{longtable}{p{3cm}l} a \\end{longtable}", []),
    ("\\column{.5\\textwidth}", []),
    ("\\begin{wrapfigure}{r}{0.4\\textwidth} x \\end{wrapfigure}", []),
    ("\\begin{adjustbox}{width=0.9\\textwidth} x \\end{adjustbox}", []),
    # 3. more reference/file commands and multi-key cites
    ("\\pageref{fig:1} \\nameref{s:2} \\vref{x:3} \\cpageref{e:4} \\crefrange{eq:1}{eq:3} "
     "\\labelcref{e:5} \\hyperlink{t2}{see} \\bibliography{refs2020} \\lstinputlisting{code/sim2.R}", []),
    ("\\cites{a2019}{b2020} and \\parencites[p.~3]{c2018}{d2017}", []),
    # 4. more code forms
    ("\\mintinline{r}|df$x| and \\Sexpr{round(mean(df$x),2)} then 8", ["8"]),
    ("\\begin{Verbatim*}\ndf$x\n\\end{Verbatim*}", []),
    ("\\begin{alltt}\ndf$x 3\n\\end{alltt}", []),
    ("\\begin{knitrout}\ndf$x\n\\end{knitrout}", []),
    # 5. commented-out blocks
    ("\\begin{comment}\n$ stray 3\n\\end{comment}\nThen 4.", ["4"]),
    ("\\iffalse\n$ stray 3 \\ifx a b \\fi\n\\fi\nThen 4.", ["4"]),
    # 6. digits attached to letters are names, not numbers
    ("The L1 norm, R2, Assumption A1, H1, the 21st draw and 2SLS.", ["2"]),
    ("COVID-19 cases", ["19"]),
    ("Table 1 shows", ["1"]),
    # 8. grouped digits count once
    ("We had 1{,}204 cases.", ["1{,}204"]),
    # 9. optional titles are never linted (as specified)
    ("\\begin{proposition}[Coverage 0.95] x \\end{proposition}", []),
])
def test_policy(src, expected):
    assert toks(src) == expected


# --- Whole-document behavior -----------------------------------------------------------
def test_preamble_skipped_with_line_numbers():
    src = ("\\documentclass[12pt]{article}\n\\date{October 2026}\n\\usepackage{x}\n"
           "\\begin{document}\nWe had 3 cases.\n\\end{document}\n")
    assert located(src) == [(5, "3")]


def test_commented_begin_document_is_not_the_body_start():
    src = "% \\begin{document} 9\n\\begin{document}\nWe had 3 cases.\n\\end{document}\n"
    assert located(src) == [(3, "3")]


def test_beamer_template_shape_is_clean():
    src = ("\\documentclass[aspectratio=169]{beamer}\n\\begin{document}\n"
           "\\begin{frame}{Title}\nHi\n\\end{frame}\n\\end{document}\n")
    assert toks(src) == []


def test_file_without_document_is_linted_whole():
    assert toks("\\section{Intro}\nWe had 3 cases.") == ["3"]


def test_realistic_excerpt():
    src = (
        "\\section{Results}\n"                                                   # 1
        "We ran 500 draws.\\footnote{See \\citet{smith2020}, p.~4.}\n"           # 2
        "\\begin{figure}[htbp]\n"                                                # 3
        "  \\centering\n"                                                        # 4
        "  \\includegraphics[width=0.8\\textwidth]{figs/fig_2.pdf}\n"            # 5
        "  \\caption{Coverage across 12 designs.}\\label{fig:2}\n"               # 6
        "\\end{figure}\n"                                                        # 7
        "\\begin{table}[t]\n"                                                    # 8
        "\\begin{tabular}{lcc}\\hline\n"                                         # 9
        "Design & Bias & Coverage \\\\ \\cmidrule(lr){2-3}\n"                    # 10
        "A & 0.01 & 0.94 \\\\\n"                                                 # 11
        "\\end{tabular}\n"                                                       # 12
        "\\end{table}\n"                                                         # 13
        "Equation~\\eqref{eq:1} gives $\\hat\\tau = 0.3$.\n"                     # 14
    )
    assert located(src) == [(2, "500"), (2, "4"), (6, "12"), (11, "0.01"), (11, "0.94"), (14, "0.3")]


# --- Fail hard on genuinely unbalanced input, naming file:line ---------------------------
@pytest.mark.parametrize("src", [
    "$x = 1",
    "\\begin{equation} x",
    "\\begin{document} x",
    "\\( x",
    "\\begin{verbatim} x",
    "\\verb|x",
    "\\verb|a\nb|",
])
def test_unbalanced_input_fails_hard(src):
    with pytest.raises(LintParseError, match=r"t\.tex:\d+"):
        lint_text(src, "t.tex")


@pytest.mark.parametrize("src,expected", [
    ("$\\theta \\in [0.1, 0.9]$", ["0.1", "0.9"]),
    ("$\\Pr[\\hat\\tau > 0.05]$", ["0.05"]),
    ("$\\sqrt[3]{x} + \\sqrt[2.5]{y}$", []),
    ("$a \\xrightarrow[0.5]{} b$", []),
    ("\\begin{align} a &= b \\\\[0.5ex] c \\end{align}", []),
    ("\\newcolumntype{C}{>{$}c<{$}}", []),
    ("\\begin{multicols}{2} text \\end{multicols}", []),
])
def test_followup_math_brackets_and_layout(src, expected):
    assert toks(src) == expected


def test_def_bodies_are_skipped():
    src = "\\def\\be{\\begin{equation}}\n\\def\\ee{\\end{equation}}\n\\gdef\\x#1{#1 0.5}\nWe had 3."
    assert located(src) == [(4, "3")]




# --- Round 3 (second re-review): optional-argument signatures, boxes in math, policy refinements ---
@pytest.mark.parametrize("src,expected", [
    # N1: [...] after a command that takes no optional argument there is text
    ("The effect was \\estATE{} [0.30, 0.60].", ["0.30", "0.60"]),
    ("The effect was \\estATE [0.30, 0.60].", ["0.30", "0.60"]),
    ("The effect was \\estATE[0.30, 0.60].", ["0.30", "0.60"]),
    ("The effect was \\textbf{0.45} [0.30, 0.60].", ["0.45", "0.30", "0.60"]),
    ("as in \\citep{a} [12 studies].", ["12"]),
    ("\\section{Results}\n[0.30, 0.60] is the interval.", ["0.30", "0.60"]),
    ("\\noindent [Based on 500 draws.]", ["500"]),
    ("\\section [Short 3]{Long}", []),
    ("\\caption[Short 3]{Long 4}", ["4"]),
    ("\\footnote[2]{See 5 notes}", ["5"]),
    ("\\newtheorem{prop}[thm]{Proposition}[section]", []),
    # N2: \text-family takes no optional argument
    ("Draw $\\tau_i \\sim \\text{Uniform}[0.5, 1.5]$ for each unit.", ["0.5", "1.5"]),
    # N3: text-mode arguments of box commands inside math
    ("\\begin{equation} \\resizebox{\\textwidth}{!}{$a = 0.5$} \\end{equation}", ["0.5"]),
    ("\\[ \\scalebox{0.8}{$a=0.5$} \\]", ["0.5"]),
    ("$a \\hbox{for $i$} b$", []),
    ("\\[ \\fbox{$x$} \\]", []),
    ("\\[ \\makebox[2cm]{$x$} \\]", []),
    ("\\[ \\parbox{3cm}{for $i$} \\]", []),
    ("$\\textup{(if $x>0$)}$", []),
    ("$\\colorbox{yellow}{$x$}$", []),
    # N4: \string takes the next token literally
    ("\\texttt{\\string\\input} this file", []),
    # N6: more definition commands
    ("\\DeclareRobustCommand{\\x}{0.5}", []),
    # N7: amsmath \\ does not look past spaces for [ inside math environments
    ("\\begin{align} a &= b \\\\ [0.1, 0.9] &= c \\end{align}", ["0.1", "0.9"]),
    # PQ1: jss.cls code
    ("\\begin{CodeInput}\nR> results$results\n\\end{CodeInput}", []),
    ("\\begin{CodeChunk}\n\\begin{CodeOutput}\n[1] 0.5$\n\\end{CodeOutput}\n\\end{CodeChunk}", []),
    ("Use \\code{df$x} here 3.", ["3"]),
    # PQ3: inline \tikz
    ("See \\tikz \\draw (0,0) -- (1,2); here 4.", ["4"]),
    ("\\tikz[baseline]{\\draw (0,0) circle (1pt);} and 5", ["5"]),
    # PQ4: more math environments
    ("\\begin{dmath} x = 2 + 0.5 \\end{dmath}", ["0.5"]),
    ("\\begin{IEEEeqnarray}{rCl} a & = & 3 \\end{IEEEeqnarray}", []),
    # \iffalse ... \else ... \fi: the \else branch is linted
    ("\\iffalse\nhidden 3\n\\else\nshown 4\n\\fi", ["4"]),
    # %num-ok after an escaped backslash is a real comment marker
    ("Rate 45\\\\%num-ok", []),
])
def test_round3(src, expected):
    assert toks(src) == expected


def test_newif_inside_iffalse_is_not_counted():
    src = "\\iffalse\n\\newif\\ifdraft\n\\fi\nWe ran 500 draws."
    assert located(src) == [(4, "500")]


def test_user_conditional_declared_by_newif_is_counted_in_iffalse():
    src = "\\newif\\ifdraft\n\\iffalse\n\\ifdraft x\\fi 9\n\\fi\nWe ran 500 draws."
    assert located(src) == [(5, "500")]


def test_newdocumentcommand_body_is_not_parsed():
    src = "\\NewDocumentCommand{\\be}{}{\\begin{equation}}\nWe had 3."
    assert located(src) == [(2, "3")]


# PQ2 refinement of the approved "digits attached to letters" rule (approved examples unchanged)
@pytest.mark.parametrize("src,count", [
    ("The L1 norm, R2, Assumption A1, H1.", 0),
    ("the 21st draw, the 3rd case, the 1990s, the 2nd step", 0),
    ("12pp gain, 3x speedup, 100k draws, 2SLS", 4),
    ("Fig.3 and p.12", 2),
    ("COVID-19 cases", 1),
])
def test_names_vs_numbers(src, count):
    assert len(toks(src)) == count


def test_scientific_notation_is_one_token():
    assert toks("tolerance 1e-5 and 2.5E3") == ["1e-5", "2.5E3"]


@pytest.mark.parametrize("src", ["a } b", "\\begin{equation} x \\end{align}"])
def test_more_unbalanced_input_fails_hard(src):
    with pytest.raises(LintParseError, match=r"t\.tex:\d+"):
        lint_text(src, "t.tex")


def test_deep_nesting_is_a_named_error_not_a_crash():
    with pytest.raises(LintParseError, match=r"t\.tex"):
        lint_text("{" * 3000 + "x" + "}" * 3000, "t.tex")


@pytest.mark.parametrize("src,expected", [
    ("Coverage drops when $\\rho<0.5, n>100$.", ["0.5"]),
    ("We report $P(\\varepsilon<0.05|Z>1)$.", ["0.05"]),
    ("$\\uncover<2>{x} + \\only<3->{y}$", []),
    ("\\only<2->{x} and \\alert<3>{y} 4", ["4"]),
    ("\\pretocmd{\\section}{\\clearpage}{}{} then 3", ["3"]),
    ("\\titleformat{\\section}{\\bfseries}{}{}{} then 4", ["4"]),
])
def test_final_review_bugs(src, expected):
    assert toks(src) == expected


def test_command_passed_literally_does_not_raise():
    lint_text("\\titlespacing{\\section}{0pt}{1ex}{1ex}", "t.tex")


def test_missing_argument_at_paragraph_break_still_raises():
    with pytest.raises(LintParseError, match=r"t\.tex:\d+"):
        lint_text("\\section\n\nText", "t.tex")
