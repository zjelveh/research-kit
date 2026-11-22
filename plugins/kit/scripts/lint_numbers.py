#!/usr/bin/env python3
"""Count bare numbers in LaTeX prose (research-kit spec §5.5).

Exit codes: 0 = count <= baseline, 1 = regression, 2 = error.
"""
from __future__ import annotations

import argparse
import bisect
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kitlib import KitError, git, glob_to_regex, load_config  # noqa: E402

# =====================================================================================
# Policy: what is never linted. This is the authoritative list; extending it is a kit edit.
# =====================================================================================

# Command signatures: one letter per argument slot, in order.
#   o  optional arguments [..] may appear here: skipped (whitespace before '[' is allowed)
#   O  an optional argument [..] may appear here: its content is prose (\twocolumn[...])
#   p  an optional (..) spec may appear here: skipped (\cmidrule(lr){2-4})
#   d  an optional TeX box spec may appear here: skipped (\hbox to 3cm{...})
#   s  a required argument, skipped: brace-matched and never interpreted
#   t  a required argument that is prose, even inside math (where $ opens math again)
#   m  a required argument that is math
#   a  a required argument read in the surrounding mode (\textcolor{red}{x_1} in math is math)
# Arguments beyond the signature are read by the main scan in the surrounding mode.
# A command that is not listed takes no optional argument: a '[' after it is text or math.
# Any command may be followed directly by a Beamer overlay <..>, as may its optional arguments
# (in math, only the commands in BEAMER_OVERLAY_CMDS). A command written as a bare token, as in
# \pretocmd{\section}{..}, reads no arguments: its first required argument would meet '}'.
COMMAND_SIGNATURES: dict[str, str] = {
    # text mode (no optional argument) and math
    **dict.fromkeys(["text", "textrm", "textit", "textbf", "textsf", "texttt", "textnormal",
                     "textup", "textsc", "textsl", "textmd", "emph", "mbox", "fbox",
                     "intertext", "shortintertext"], "t"),
    "hbox": "dt", "ensuremath": "m",
    "sqrt": "om", "xrightarrow": "om", "xleftarrow": "om",
    # sectioning, captions, footnotes, lists, title page
    **dict.fromkeys(["part", "chapter", "section", "subsection", "subsubsection", "paragraph",
                     "subparagraph"], "ot"),
    "caption": "ot", "captionof": "sot", "subcaption": "ot", "subfloat": "ot",
    "footnote": "ot", "footnotemark": "o", "footnotetext": "ot",
    "item": "o", "bibitem": "os",
    "title": "ot", "author": "ot", "institute": "ot", "date": "os",
    # files and packages
    "includegraphics": "os", "usepackage": "os", "documentclass": "os", "lstinputlisting": "os",
    "inputminted": "oss", "input": "s", "include": "s", "includeonly": "s", "subfile": "s",
    "import": "ss", "bibliography": "s", "bibliographystyle": "s",
    # labels and cross-references
    **dict.fromkeys(["label", "ref", "eqref", "pageref", "autoref", "nameref", "vref", "cref",
                     "Cref", "cpageref", "Cpageref", "labelcref", "tag"], "s"),
    "crefrange": "ss", "Crefrange": "ss", "hyperlink": "st", "hypertarget": "st",
    "hyperref": "oa",
    # lengths, counters, breaks
    "vspace": "s", "hspace": "s", "setlength": "ss", "addtolength": "ss", "setcounter": "ss",
    "addtocounter": "ss",
    **dict.fromkeys(["linebreak", "pagebreak", "nolinebreak", "nopagebreak"], "o"),
    "twocolumn": "O",
    # boxes and colour (box contents are text mode, even inside math)
    "makebox": "ot", "framebox": "ot", "parbox": "ost", "raisebox": "sot", "scalebox": "sot",
    "resizebox": "sst", "rotatebox": "ost", "colorbox": "ost", "fcolorbox": "osst",
    "textcolor": "osa", "color": "os", "phantom": "s", "hphantom": "s", "vphantom": "s",
    # table and slide layout
    "multicolumn": "ss", "multirow": "ososo", "cline": "s", "cmidrule": "ops", "rule": "oss",
    "column": "os",
    # definitions
    **dict.fromkeys(["newcommand", "renewcommand", "providecommand", "DeclareRobustCommand",
                     "newcolumntype"], "sos"),
    "newenvironment": "soss", "renewenvironment": "soss", "newtheorem": "soto",
    "DeclareMathOperator": "ss",
    **dict.fromkeys(["NewDocumentCommand", "RenewDocumentCommand", "ProvideDocumentCommand",
                     "DeclareDocumentCommand"], "sss"),
    "NewDocumentEnvironment": "ssss", "RenewDocumentEnvironment": "ssss",
}

# Citation commands, matched case-insensitively (\Citet, \Parencite): [..] notes, then a key.
CITE_CMDS = frozenset({
    "cite", "citep", "citet", "citealp", "citealt", "citeauthor", "citeyear", "citeyearpar",
    "citenum", "nocite", "parencite", "textcite", "autocite", "footcite", "fullcite",
    "smartcite", "supercite",
})
CITE_SIGNATURE = "os"
# Multi-key citations: every consecutive {key} group, with [..] notes between them.
MULTI_CITE_CMDS = frozenset({
    "cites", "parencites", "textcites", "autocites", "footcites", "smartcites",
})

# Arguments skipped after \begin{env}; such an environment's signature is "o" + "os" * count.
# Any other environment takes optional arguments right after \begin{env} in prose, none in math.
ENV_ARG_SKIPS: dict[str, int] = {
    "column": 1, "minipage": 1, "tabular": 1, "tabular*": 2, "tabularx": 2, "longtable": 1,
    "array": 1, "subfigure": 1, "wrapfigure": 2, "adjustbox": 1, "multicols": 1, "multicols*": 1,
}

# Math environments, with the signature of what follows \begin{env}.
# In math, integers are ignored and decimals are flagged.
MATH_ENVS: dict[str, str] = {
    **dict.fromkeys(["equation", "equation*", "align", "align*", "gather", "gather*", "multline",
                     "multline*", "eqnarray", "eqnarray*", "math", "displaymath", "flalign",
                     "flalign*", "alignat", "alignat*"], ""),
    **dict.fromkeys(["dmath", "dmath*", "dseries", "dgroup"], "o"),  # breqn
    "IEEEeqnarray": "os", "IEEEeqnarray*": "os",                     # {colspec} skipped
    "empheq": "os",                                                  # [options]{inner env}
    "numcases": "m", "subnumcases": "m",                             # {lhs} is math
}

# Environments skipped whole, up to the matching \end{...}.
# Raw (code): read literally, so %, $ and braces inside mean nothing.
RAW_ENVS = frozenset({
    "verbatim", "verbatim*", "Verbatim", "Verbatim*", "BVerbatim", "LVerbatim", "lstlisting",
    "minted", "Schunk", "Sinput", "Soutput", "alltt", "knitrout", "comment",
    "Code", "CodeInput", "CodeOutput", "CodeChunk",  # jss.cls
})
# Not raw (TikZ / pgfplots drawings): TeX still reads them, so % starts a comment inside.
# The inline \tikz[..]{...} and \tikz ... ; are skipped too.
SKIPPED_ENVS = frozenset({"tikzpicture", "axis", "semilogxaxis", "semilogyaxis", "loglogaxis"})

# Inline code and URLs, read literally: \verb|..|, \lstinline[..]|..| or {..},
# \mintinline{lang}|..| or {..}, \Sexpr{..}, \code{..} (jss.cls), \url{..}, and the first
# argument of \href{..}{..} (the second is prose).
RAW_INLINE_CMDS = frozenset({"verb", "lstinline", "mintinline", "Sexpr", "code", "url", "href"})

# Size-delimiter commands take one delimiter token: the [ in \left[ 0, 1 \right) is a delimiter.
DELIMITER_CMDS = frozenset({
    "left", "right", "middle", "big", "Big", "bigg", "Bigg", "bigl", "Bigl", "biggl", "Biggl",
    "bigr", "Bigr", "biggr", "Biggr", "bigm", "Bigm", "biggm", "Biggm",
})

# Beamer overlays <..> (\item<2->, \only<3>{..}) are skipped after any command in prose, but in
# math only after these overlay-aware commands; elsewhere in math '<' is a relation.
BEAMER_OVERLAY_CMDS = frozenset({
    "only", "uncover", "visible", "invisible", "alt", "temporal", "onslide", "alert", "item",
    "pause", "action", "structure", "textbf", "textit", "color", "includegraphics",
})

# \def\name<parameter text>{body}: the name, the parameter text (#1#2) and the body are
# skipped, and the body is not interpreted (a \begin{equation} inside it opens nothing).
DEF_CMDS = frozenset({"def", "gdef", "edef", "xdef"})

# \iffalse ... \fi is skipped up to the matching \fi (an \else at its level ends the skip:
# that branch is typeset). Nesting counts only TeX conditionals: these primitives, plus every
# \if<name> declared in the file by \newif.
TEX_CONDITIONALS = frozenset({
    "if", "ifx", "ifnum", "ifdim", "ifodd", "ifcase", "ifmmode", "ifvmode", "ifhmode", "ifinner",
    "ifvoid", "ifhbox", "ifvbox", "ifeof", "iftrue", "iffalse", "ifcat", "ifdefined", "ifcsname",
})

# A number token: 1{,}204, 1e-5 and 2.5E3 are one token each, as are 0.94, 1,000 and .5.
# A token is a name, not a number, when it starts with a digit right after a letter (L1, R2,
# x1; not after a control word: \S2), or is followed by st/nd/rd/th/s that is not followed by
# a letter (21st, 3rd, 1990s). Other letter suffixes count (12pp, 3x, 2SLS); COVID-19 counts 19.
NUM_RE = re.compile(r"\d+(?:\{,\}\d{3})+|\d+(?:\.\d+)?[eE][-+]?\d+|\d+(?:[.,]\d+)*|\.\d+")

PROSE, MATH = "prose", "math"

_SPECIAL = re.compile(r"[%\\{}$#\d]|\.(?=\d)")       # where the main scan must stop
_SPECIAL_IN_OPTION = re.compile(r"[%\\{}$#\]\d]|\.(?=\d)")
_CONTROL_WORD = re.compile(r"\\([A-Za-z]+)")
_ENV_NAME = re.compile(r"\{([^{}\n]*)\}")
_BLANK_LINE = re.compile(r"\n[ \t\r]*\n")              # a paragraph break
# A Beamer overlay spec: items separated by ',' or '|', each an optional mode ("handout:") and
# action ("alert@") before a slide range: 2, 2-, -3, 1-3, +-, .-, +(1)-. So <2-| alert@2>,
# <1,3,5> and <presentation:2-> match, but 0.5, n and 0.05|Z (from $\rho<0.5, n>1$) do not.
_OVERLAY_POINT = r"(?:\d+|[+.](?:\(-?\d+\))?)"
_OVERLAY_ITEM = (rf"\s*(?:[A-Za-z]+:)?(?:[A-Za-z]+@)?"
                 rf"(?:{_OVERLAY_POINT}(?:-{_OVERLAY_POINT}?)?|-{_OVERLAY_POINT})\s*")
_OVERLAY = re.compile(rf"{_OVERLAY_ITEM}(?:[,|]{_OVERLAY_ITEM})*")
_BOX_SPEC = re.compile(r"(?:to|spread)(?![A-Za-z])[^{}\n]*")
_NAME_SUFFIX = re.compile(r"(?:st|nd|rd|th|s)(?![^\W\d_])")
_FILE_NAME = re.compile(r"[^ \t\r\n{}%]+")             # \input main.tex
_BRACE = re.compile(r"[{}]")
_GROUP_STOP = re.compile(r"[\\{}%]")
_TIKZ_STOP = re.compile(r"[\\{};%]")
_COMMAND_OR_COMMENT = re.compile(r"[\\%]")
_BRACKET_STOP = {"]": re.compile(r"[\\{}\]%\n$&]"), ")": re.compile(r"[\\{})%\n$&]")}
_BEGIN_DOCUMENT_SCAN = re.compile(r"\\begin[ \t]*\{document\}|\\.|%")
_NEWIF_SCAN = re.compile(r"\\newif[ \t]*\\(if[A-Za-z]*)|\\.|%")


class LintParseError(KitError):
    """The file could not be scanned: an unbalanced or unclosed delimiter, or nesting too deep.
    The message names <file>:<line>."""


@dataclass(frozen=True)
class Finding:
    file: str
    line: int
    token: str


@dataclass(frozen=True)
class _Closer:
    """What ends the current scan, and where it was opened (for error messages)."""
    kind: str  # "eof", "document", "group", "option", "$", "$$", ")" for \(, "]" for \[, "env"
    at: int
    env: str = ""

    def describe(self) -> str:
        names = {"group": "'{'", "option": "'['", "$": "'$'", "$$": "'$$'", ")": "'\\('",
                 "]": "'\\['", "document": "\\begin{document}", "eof": "the file"}
        return names.get(self.kind, f"\\begin{{{self.env}}}")


class _Scanner:
    """One pass over a file. `scan` dispatches on the next special character and recurses
    into groups, math, and prose arguments inside math (\\text{... $x$ ...})."""

    def __init__(self, text: str, fname: str):
        self.text, self.fname, self.n = text, fname, len(text)
        self.line_starts = [0] + [m.end() for m in re.finditer(r"\n", text)]
        self.found: list[tuple[int, str]] = []
        self.word_end = -1  # just past the last control word: the 2 in \S2 is not a name
        self.innermost = 0  # where the innermost scan was opened (for "nesting too deep")
        self.conditionals = TEX_CONDITIONALS | _declared_conditionals(text)
        self.char_handlers = {
            "%": self.handle_comment, "\\": self.handle_backslash,
            "{": self.handle_open_group, "}": self.handle_close_group,
            "]": self.handle_close_option, "$": self.handle_dollar, "#": self.handle_parameter,
        }
        self.command_handlers = {
            "begin": self.handle_begin_end, "end": self.handle_begin_end,
            "iffalse": self.handle_iffalse, "string": self.handle_string, "let": self.handle_let,
            "tikz": self.handle_tikz,
            **dict.fromkeys(RAW_INLINE_CMDS, self.handle_raw_inline),
            **dict.fromkeys(DEF_CMDS, self.handle_def),
        }

    # -- dispatcher ------------------------------------------------------------------
    def scan(self, i: int, mode: str, closer: _Closer) -> int:
        """Scan from i in `mode` until `closer`; return the index just past the closer."""
        self.innermost = closer.at
        special = _SPECIAL_IN_OPTION if closer.kind == "option" else _SPECIAL
        while True:
            m = special.search(self.text, i)
            if m is None:
                if closer.kind == "eof":
                    return self.n
                raise self.error(closer.at, f"{closer.describe()} is never closed")
            handler = self.char_handlers.get(m.group()[0], self.handle_number)
            i, closed = handler(m.start(), mode, closer)
            if closed:
                return i

    # -- character handlers: (i, mode, closer) -> (next index, closed?) ---------------
    def handle_comment(self, i: int, mode: str, closer: _Closer) -> tuple[int, bool]:
        return self.eol(i), False

    def handle_open_group(self, i: int, mode: str, closer: _Closer) -> tuple[int, bool]:
        return self.scan(i + 1, mode, _Closer("group", i)), False

    def handle_close_group(self, i: int, mode: str, closer: _Closer) -> tuple[int, bool]:
        if closer.kind == "group":
            return i + 1, True
        raise self.error(i, f"'}}' without a matching '{{' (innermost open: {self.where(closer)})")

    def handle_close_option(self, i: int, mode: str, closer: _Closer) -> tuple[int, bool]:
        """']' is special only while scanning a prose optional argument (\\twocolumn[...])."""
        return i + 1, True

    def handle_dollar(self, i: int, mode: str, closer: _Closer) -> tuple[int, bool]:
        double = self.text.startswith("$$", i)
        if mode == PROSE:
            kind = "$$" if double else "$"
            return self.scan(i + len(kind), MATH, _Closer(kind, i)), False
        if closer.kind == "$":
            return i + 1, True
        if closer.kind == "$$" and double:
            return i + 2, True
        raise self.error(i, f"unexpected '$' in math (innermost open: {self.where(closer)})")

    def handle_parameter(self, i: int, mode: str, closer: _Closer) -> tuple[int, bool]:
        """#1 in a macro body is a parameter, not the number 1."""
        j = i
        while j < self.n and self.text[j] == "#":
            j += 1
        if j < self.n and "1" <= self.text[j] <= "9":
            j += 1
        return j, False

    def handle_number(self, i: int, mode: str, closer: _Closer) -> tuple[int, bool]:
        end = NUM_RE.match(self.text, i).end()
        self.record(i, end, mode)
        return end, False

    def handle_backslash(self, i: int, mode: str, closer: _Closer) -> tuple[int, bool]:
        t = self.text
        nxt = t[i + 1:i + 2]
        if nxt in ("(", "["):
            return self.handle_math_open(i, mode)
        if nxt in (")", "]"):
            return self.handle_math_close(i, closer)
        if nxt == "\\":  # \\ and \\* take an optional argument
            j = i + 2 + t.startswith("*", i + 2)
            if mode == MATH:  # amsmath's \\ does not look past spaces for '['
                end = self.bracket_end(j, mode) if t.startswith("[", j) else None
                return (j if end is None else end), False
            return self.skip_options(j, mode), False
        m = _CONTROL_WORD.match(t, i)
        if m is None:  # control symbol: \% \$ \& \{ \} \, \  ...
            return min(i + 2, self.n), False
        name, j = m.group(1), m.end()
        self.word_end = j
        handler = self.command_handlers.get(name)
        if handler is not None:
            return handler(i, name, j, mode, closer)
        return self.handle_command(i, name, j, mode), False

    def handle_math_open(self, i: int, mode: str) -> tuple[int, bool]:
        """\\( or \\[ ($ is handled by handle_dollar)."""
        if mode == MATH:
            raise self.error(i, f"'{self.text[i:i + 2]}' inside math")
        kind = ")" if self.text[i + 1] == "(" else "]"
        return self.scan(i + 2, MATH, _Closer(kind, i)), False

    def handle_math_close(self, i: int, closer: _Closer) -> tuple[int, bool]:
        kind = self.text[i + 1]
        if closer.kind == kind:
            return i + 2, True
        token = self.text[i:i + 2]
        raise self.error(i, f"'{token}' does not close the innermost open {self.where(closer)}")

    # -- command handlers: (i, name, j, mode, closer) -> (next index, closed?) --------
    # i is at the backslash; j is just past the command name.
    def handle_begin_end(self, i: int, name: str, j: int, mode: str,
                         closer: _Closer) -> tuple[int, bool]:
        m = _ENV_NAME.match(self.text, self.skip_ws(j))
        if m is None:
            raise self.error(i, f"\\{name} is not followed by an {{environment}} name")
        env, after = m.group(1), m.end()
        label = f"begin{{{env}}}"
        if name == "end":
            return self.handle_end(i, env, after, closer)
        if env in RAW_ENVS:
            return self.skip_raw_env(i, env, after), False
        if env in SKIPPED_ENVS:
            return self.skip_env(i, env, after), False
        if env in MATH_ENVS:
            k = self.arg_chain(i, after, MATH, label, MATH_ENVS[env], overlays=False)
            return self.scan(k, MATH, _Closer("env", i, env)), False
        count = ENV_ARG_SKIPS.get(env)
        if count is None:
            signature = "o" if mode == PROSE else ""
        else:
            signature = "o" + "os" * count
        return self.arg_chain(i, after, mode, label, signature), False

    def handle_end(self, i: int, env: str, after: int, closer: _Closer) -> tuple[int, bool]:
        if closer.kind == "env" and env == closer.env:
            return after, True
        if env == "document" and closer.kind in ("document", "eof"):
            return after, True  # LaTeX ignores everything after \end{document}
        if env == "document" or env in MATH_ENVS:
            if closer.kind in ("document", "eof"):
                raise self.error(i, f"\\end{{{env}}} without a matching \\begin{{{env}}}")
            raise self.error(closer.at, f"{closer.describe()} is not closed before "
                                        f"\\end{{{env}}} on line {self.line_of(i)}")
        return after, False  # other environments are not tracked

    def handle_raw_inline(self, i: int, name: str, j: int, mode: str,
                          closer: _Closer) -> tuple[int, bool]:
        t, label = self.text, "\\" + name
        if name == "verb":
            return self.raw_delimited(i, j + t.startswith("*", j), label), False
        if name in ("Sexpr", "code"):
            k = self.skip_ws(j)
            if not t.startswith("{", k):
                raise self.error(i, f"{label} is not followed by {{...}}")
            return self.raw_braced(i, k, label), False
        if name == "href":  # the URL is literal; the link text that follows is prose
            k = self.skip_ws(self.skip_options(j, mode))
            if t.startswith("{", k):
                return self.raw_braced(i, k, label), False
            return self.required_arg(i, k, name), False
        if name == "url":
            k = self.skip_spaces(j)
        else:  # \lstinline[opts] and \mintinline[opts]{lang}, then |code| or {code}
            k = self.skip_options(j, mode)
            if name == "mintinline":
                k = self.required_arg(i, self.skip_ws(k), name)
            k = self.skip_spaces(k)
        if t.startswith("{", k):
            return self.raw_braced(i, k, label), False
        return self.raw_delimited(i, k, label), False

    def handle_iffalse(self, i: int, name: str, j: int, mode: str,
                       closer: _Closer) -> tuple[int, bool]:
        return self.skip_iffalse(i, j), False

    def handle_def(self, i: int, name: str, j: int, mode: str,
                   closer: _Closer) -> tuple[int, bool]:
        return self.skip_def(i, name, j), False

    def handle_string(self, i: int, name: str, j: int, mode: str,
                      closer: _Closer) -> tuple[int, bool]:
        """\\string takes the next token literally: \\string\\input does not run \\input."""
        return self.literal_token_end(i, self.skip_ws(j), name), False

    def handle_let(self, i: int, name: str, j: int, mode: str,
                   closer: _Closer) -> tuple[int, bool]:
        """\\let\\new = \\old: both tokens are literal (\\let\\oldsection\\section)."""
        k = self.skip_ws(self.literal_token_end(i, self.skip_ws(j), name))
        if self.text.startswith("=", k):
            k = self.skip_ws(k + 1)
        return self.literal_token_end(i, k, name), False

    def handle_tikz(self, i: int, name: str, j: int, mode: str,
                    closer: _Closer) -> tuple[int, bool]:
        """Inline TikZ is skipped: \\tikz[opts]{...} or \\tikz[opts] ... ; (to the first ';'
        outside braces)."""
        t = self.text
        overlays = self.overlays_allowed(name, mode)
        if overlays:
            j = self.skip_overlay(j)
        k = self.skip_ws(self.skip_options(j, mode, overlays))
        if t.startswith("{", k):
            return self.skip_group(k), False
        depth = 0
        while True:
            m = _TIKZ_STOP.search(t, k)
            if m is None:
                raise self.error(i, "\\tikz path is never ended by ';'")
            k = m.start()
            c = t[k]
            if c == "\\":
                k += 2
            elif c == "%":
                k = self.eol(k)
            elif c == "{":
                depth, k = depth + 1, k + 1
            elif c == "}":
                if depth == 0:
                    raise self.error(i, "\\tikz path is not ended by ';' before '}'")
                depth, k = depth - 1, k + 1
            elif depth == 0:  # ';'
                return k + 1, False
            else:
                k += 1

    def handle_command(self, i: int, name: str, j: int, mode: str) -> int:
        if self.text.startswith("*", j):
            j += 1
        folded = name.lower()
        if folded in MULTI_CITE_CMDS:
            return self.skip_multi_cite(j, mode)
        if name in DELIMITER_CMDS:
            k = self.skip_ws(j)
            if self.text.startswith("}", k):  # passed as a token: {\left}
                return j
            return self.required_arg(i, k, name)
        signature = CITE_SIGNATURE if folded in CITE_CMDS else COMMAND_SIGNATURES.get(name, "")
        return self.arg_chain(i, j, mode, name, signature)

    # -- argument chains -------------------------------------------------------------
    def arg_chain(self, i: int, j: int, mode: str, name: str, signature: str,
                  overlays: bool = True) -> int:
        """Read the arguments in `signature` (see COMMAND_SIGNATURES), starting at j, just past
        the command name and any *. With `overlays`, a Beamer overlay <..> directly after the
        name or after an optional argument is skipped."""
        t = self.text
        overlays = overlays and self.overlays_allowed(name, mode)
        if overlays:
            j = self.skip_overlay(j)
        first_required = True
        for slot in signature:
            if slot in "stma":
                # {\section} passes the command itself as a token (\pretocmd{\section}{..}):
                # its first required argument meets '}' at once, so it reads no arguments.
                if first_required and t.startswith("}", self.skip_ws(j)):
                    return j
                first_required = False
            if slot == "o":
                j = self.skip_options(j, mode, overlays)
            elif slot == "O":
                k = self.skip_ws(j)
                if t.startswith("[", k) and self.bracket_end(k, mode) is not None:
                    j = self.scan(k + 1, PROSE, _Closer("option", k))
            elif slot == "p":
                k = self.skip_ws(j)
                if t.startswith("(", k):
                    end = self.bracket_end(k, mode)
                    if end is None:
                        raise self.error(i, f"\\{name}( is never closed by ')'")
                    j = end
            elif slot == "d":
                m = _BOX_SPEC.match(t, self.skip_ws(j))
                if m is not None:
                    j = m.end()
            elif slot == "s":
                j = self.required_arg(i, self.skip_ws(j), name)
            else:  # t, m, a
                k = self.skip_ws(j)
                arg_mode = PROSE if slot == "t" else MATH if slot == "m" else mode
                if t.startswith("{", k):
                    j = self.scan(k + 1, arg_mode, _Closer("group", k))
                else:
                    j = self.mode_token_arg(i, k, name, arg_mode)
        return j

    def required_arg(self, i: int, k: int, name: str) -> int:
        """Skip one required argument at k (after whitespace): a {group}, else one TeX token."""
        t = self.text
        if k >= self.n or t[k] in "}\n":  # "\n" here: skip_ws stopped at a paragraph break
            raise self.error(i, f"\\{name} is missing a required argument")
        if t[k] == "{":
            return self.skip_group(k)
        if name == "input":  # the primitive \input reads a file name up to a space
            return _FILE_NAME.match(t, k).end()
        if t[k] == "\\":
            w = _CONTROL_WORD.match(t, k)
            if w is None:
                return min(k + 2, self.n)
            self.word_end = w.end()
            return w.end()
        return k + 1

    def mode_token_arg(self, i: int, k: int, name: str, arg_mode: str) -> int:
        """Unbraced scanned argument (\\text 5): one token, read in arg_mode."""
        t = self.text
        if k >= self.n or t[k] in "}\n":
            raise self.error(i, f"\\{name} is missing a required argument")
        if t[k] in "0123456789":
            self.record(k, k + 1, arg_mode)
            return k + 1
        return k  # any other single token holds no number; the main scan reads it

    def literal_token_end(self, i: int, k: int, name: str) -> int:
        """End of the single token at k, taken literally (never dispatched as a command)."""
        t = self.text
        if k >= self.n:
            raise self.error(i, f"\\{name} is missing a token")
        if t[k] == "\\":
            w = _CONTROL_WORD.match(t, k)
            return w.end() if w else min(k + 2, self.n)
        return k + 1

    def skip_options(self, j: int, mode: str, overlays: bool = False) -> int:
        """Skip consecutive optional arguments [..] (each optionally followed by a Beamer
        overlay); return j unchanged if there are none."""
        while True:
            k = self.skip_ws(j)
            end = self.bracket_end(k, mode) if self.text.startswith("[", k) else None
            if end is None:
                return j
            j = self.skip_overlay(end) if overlays else end

    def skip_multi_cite(self, j: int, mode: str) -> int:
        t = self.text
        while True:
            k = self.skip_ws(j)
            if t.startswith("[", k):
                end = self.bracket_end(k, mode)
                if end is None:
                    return j
                j = end
            elif t.startswith("{", k):
                j = self.skip_group(k)
            else:
                return j

    def bracket_end(self, k: int, mode: str) -> int | None:
        """k is at '[' (or the '(' of a \\cmidrule trim spec). Return the index just past the
        first ']' (or ')') not inside braces; there is no bracket nesting.

        Return None when the bracket cannot be an optional argument, so it is plain text: no
        closer comes before a paragraph break, the end of the file, the end of the enclosing
        group, or an alignment tab '&'; in math, also when the formula or row ends first
        ('$', '\\)', '\\]', '\\end', '\\\\').
        """
        t = self.text
        close = "]" if t[k] == "[" else ")"
        stop = _BRACKET_STOP[close]
        depth, j = 0, k + 1
        while True:
            m = stop.search(t, j)
            if m is None:
                return None
            j = m.start()
            c = t[j]
            if c == "\\":
                w = _CONTROL_WORD.match(t, j)
                if depth == 0 and mode == MATH and (
                        t.startswith(("\\)", "\\]", "\\\\"), j) or (w and w.group(1) == "end")):
                    return None
                j = w.end() if w else j + 2
            elif c == "%":
                j = self.eol(j)
            elif c == "\n":
                if _BLANK_LINE.match(t, j):
                    return None
                j += 1
            elif c == "{":
                depth, j = depth + 1, j + 1
            elif c == "}":
                if depth == 0:
                    return None
                depth, j = depth - 1, j + 1
            elif c == close:
                if depth == 0:
                    return j + 1
                j += 1
            else:  # '$' or '&'
                if depth == 0 and (c == "&" or mode == MATH):
                    return None
                j += 1

    @staticmethod
    def overlays_allowed(name: str, mode: str) -> bool:
        """In prose any command may carry a Beamer overlay; in math only the overlay-aware
        Beamer commands do, so the < in $\\rho<0.5, n>100$ is a relation."""
        return mode == PROSE or name in BEAMER_OVERLAY_CMDS

    def skip_overlay(self, j: int) -> int:
        """Skip a Beamer overlay <..> at j: it must close on the same line and hold only overlay
        syntax; otherwise '<' is plain text (\\ifnum\\x<3)."""
        t = self.text
        if not t.startswith("<", j):
            return j
        close = t.find(">", j + 1, self.eol(j))
        if close == -1 or not _OVERLAY.fullmatch(t, j + 1, close):
            return j
        return close + 1

    # -- skipped regions -------------------------------------------------------------
    def skip_group(self, k: int) -> int:
        """k is at '{': skip the balanced group without interpreting it. Escapes and comments
        count, as when TeX reads an argument."""
        t, depth, j = self.text, 0, k
        while True:
            m = _GROUP_STOP.search(t, j)
            if m is None:
                raise self.error(k, "'{' is never closed")
            j = m.start()
            c = t[j]
            if c == "\\":
                j += 2
            elif c == "%":
                j = self.eol(j)
            elif c == "{":
                depth, j = depth + 1, j + 1
            else:
                depth, j = depth - 1, j + 1
                if depth == 0:
                    return j

    def raw_braced(self, i: int, k: int, label: str) -> int:
        """k is at the '{' of a literal argument: only braces are counted."""
        t, depth, j = self.text, 0, k
        while True:
            m = _BRACE.search(t, j)
            if m is None:
                raise self.error(i, f"{label}{{...}} is never closed")
            j = m.end()
            depth += 1 if m.group() == "{" else -1
            if depth == 0:
                return j

    def raw_delimited(self, i: int, k: int, label: str) -> int:
        """k is at the delimiter of \\verb|...|-style code, which must close on the same line."""
        t = self.text
        if k >= self.n or t[k] in "\r\n":
            raise self.error(i, f"{label} has no delimiter")
        close = t.find(t[k], k + 1, self.eol(k))
        if close == -1:
            raise self.error(i, f"{label}{t[k]}...{t[k]} is not closed on the same line")
        return close + 1

    def skip_raw_env(self, i: int, env: str, j: int) -> int:
        end_tag = f"\\end{{{env}}}"
        k = self.text.find(end_tag, j)
        if k == -1:
            raise self.error(i, f"\\begin{{{env}}} is never closed")
        return k + len(end_tag)

    def skip_env(self, i: int, env: str, j: int) -> int:
        """Skip to the matching \\end{env}; comments still hide \\begin and \\end."""
        t, depth = self.text, 0
        while True:
            m = _COMMAND_OR_COMMENT.search(t, j)
            if m is None:
                raise self.error(i, f"\\begin{{{env}}} is never closed")
            j = m.start()
            if t[j] == "%":
                j = self.eol(j)
                continue
            w = _CONTROL_WORD.match(t, j)
            if w is None:
                j += 2
                continue
            j = w.end()
            if w.group(1) in ("begin", "end"):
                e = _ENV_NAME.match(t, self.skip_ws(j))
                if e is not None and e.group(1) == env:
                    j = e.end()
                    if w.group(1) == "begin":
                        depth += 1
                    elif depth == 0:
                        return j
                    else:
                        depth -= 1

    def skip_def(self, i: int, name: str, j: int) -> int:
        """Skip \\def\\name<parameter text>{body}. The body is brace-matched (escapes and
        comments respected) but not interpreted."""
        t = self.text
        k = self.skip_ws(j)
        if k >= self.n or t[k] in "{}\n":
            raise self.error(i, f"\\{name} is not followed by a control sequence to define")
        k = self.literal_token_end(i, k, name)
        while True:  # parameter text such as #1#2 or #1\relax, up to the body's '{'
            m = _GROUP_STOP.search(t, k)
            if m is None or m.group() == "}":
                raise self.error(i, f"\\{name} has no {{body}}")
            k = m.start()
            if m.group() == "{":
                return self.skip_group(k)
            if m.group() == "%":
                k = self.eol(k)
            else:
                w = _CONTROL_WORD.match(t, k)
                k = w.end() if w else k + 2

    def skip_iffalse(self, i: int, j: int) -> int:
        """Skip to the matching \\fi, counting nested TeX conditionals. As in TeX, an \\else at
        the same level ends the skip: its branch is typeset, so it is linted."""
        t, depth = self.text, 0
        while True:
            m = _COMMAND_OR_COMMENT.search(t, j)
            if m is None:
                raise self.error(i, "\\iffalse is never closed by \\fi")
            j = m.start()
            if t[j] == "%":
                j = self.eol(j)
                continue
            w = _CONTROL_WORD.match(t, j)
            if w is None:
                j += 2
                continue
            j, word = w.end(), w.group(1)
            if word == "fi":
                if depth == 0:
                    return j
                depth -= 1
            elif word == "else" and depth == 0:
                return j
            elif word == "newif":  # \newif\ifdraft declares \ifdraft; it is not a conditional
                declared = _CONTROL_WORD.match(t, self.skip_ws(j))
                if declared is not None:
                    j = declared.end()
            elif word in self.conditionals:
                depth += 1

    # -- utilities -------------------------------------------------------------------
    def record(self, start: int, end: int, mode: str) -> None:
        t = self.text
        if (t[start] != "." and start > 0 and t[start - 1].isalpha()
                and start != self.word_end):
            return  # a name such as L1, R2, A1, x1
        if _NAME_SUFFIX.match(t, end):
            return  # an ordinal or decade: 21st, 3rd, 1990s
        token = t[start:end]
        if mode == MATH and "." not in token:
            return  # integers in math are subscripts, exponents and indices
        self.found.append((start, token))

    def skip_ws(self, j: int) -> int:
        """Skip spaces, line ends and comments, stopping at a paragraph break (blank line)."""
        t, n = self.text, self.n
        while j < n:
            c = t[j]
            if c in " \t\r":
                j += 1
            elif c == "\n":
                if _BLANK_LINE.match(t, j):
                    return j
                j += 1
            elif c == "%":
                j = self.eol(j)
            else:
                return j
        return j

    def skip_spaces(self, j: int) -> int:
        while j < self.n and self.text[j] in " \t":
            j += 1
        return j

    def eol(self, i: int) -> int:
        """Index of the newline that ends the line containing i, or the end of the text."""
        k = self.text.find("\n", i)
        return self.n if k == -1 else k

    def line_of(self, pos: int) -> int:
        return bisect.bisect_right(self.line_starts, pos)

    def where(self, closer: _Closer) -> str:
        return f"{closer.describe()} from line {self.line_of(closer.at)}"

    def error(self, pos: int, msg: str) -> LintParseError:
        return LintParseError(f"{self.fname}:{self.line_of(pos)}: {msg}")


def _uncommented_matches(text: str, pattern: re.Pattern):
    """Yield (line start offset, match) for matches of `pattern` outside comments. The pattern
    must also match '%' (a comment starts) and '\\\\.' (escapes, so \\% is not a comment)."""
    pos = 0
    for line in text.split("\n"):
        for m in pattern.finditer(line):
            if m.group() == "%":
                break
            yield pos, m
        pos += len(line) + 1


def _document_body(text: str) -> tuple[int, int] | None:
    """Span of the first \\begin{document} outside a comment, or None if there is none."""
    for pos, m in _uncommented_matches(text, _BEGIN_DOCUMENT_SCAN):
        if m.group().startswith("\\begin"):
            return pos + m.start(), pos + m.end()
    return None


def _declared_conditionals(text: str) -> set[str]:
    """Names declared anywhere in the file by \\newif\\if<name> (outside comments)."""
    return {m.group(1) for _, m in _uncommented_matches(text, _NEWIF_SCAN) if m.group(1)}


def _num_ok_lines(text: str) -> set[int]:
    """1-based lines that end in an unescaped %num-ok (45\\%num-ok is not an exemption)."""
    marker = "%num-ok"
    lines = set()
    for lineno, line in enumerate(text.split("\n"), start=1):
        line = line.rstrip()
        if not line.endswith(marker):
            continue
        k = len(line) - len(marker)
        backslashes = k - len(line[:k].rstrip("\\"))
        if backslashes % 2 == 0:
            lines.add(lineno)
    return lines


def lint_text(text: str, fname: str) -> list[Finding]:
    """Bare numbers in the prose of one LaTeX file, in file order.

    Every number in prose is a finding; in math only decimals are. Skipped regions (see the
    policy tables above) and lines ending in an unescaped %num-ok yield nothing. In a file with
    \\begin{document}, only the body is linted. Input that cannot be scanned raises
    LintParseError naming <fname>:<line>.
    """
    scanner = _Scanner(text, fname)
    body = _document_body(text)
    try:
        if body is None:
            scanner.scan(0, PROSE, _Closer("eof", 0))
        else:
            scanner.scan(body[1], PROSE, _Closer("document", body[0]))
    except RecursionError:
        raise LintParseError(f"{fname}:{scanner.line_of(scanner.innermost)}: nesting too deep "
                             f"to scan") from None
    exempt = _num_ok_lines(text)
    findings = []
    for pos, token in scanner.found:
        line = scanner.line_of(pos)
        if line not in exempt:
            findings.append(Finding(fname, line, token))
    return findings


def gate_paths(project: Path, cfg: dict, gate: str) -> tuple[Path, list[str], str]:
    if gate == "paper":
        repo, g = Path(project) / cfg["paper_dir"], cfg["lint"]["paper"]
    elif gate == "slides":
        repo, g = Path(project), cfg["lint"]["slides"]
    else:
        raise KitError(f"unknown gate {gate!r}")
    return repo, list(g["globs"]), g["baseline"]


def _read_worktree(repo: Path, p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise KitError(f"{p}: cannot read: {e}") from e


def _show(repo: Path, spec: str) -> str:
    """`git show <spec>` read as bytes and decoded as strict UTF-8."""
    proc = subprocess.run(["git", "-C", str(repo), "show", spec], capture_output=True)
    if proc.returncode != 0:
        raise KitError(f"{repo}: git show {spec} failed: "
                       f"{proc.stderr.decode('utf-8', 'replace').strip()}")
    try:
        return proc.stdout.decode("utf-8")
    except UnicodeDecodeError:
        raise KitError(f"{repo} {spec}: not valid UTF-8") from None


def collect(repo: Path, globs: list[str], source: str) -> dict[str, str]:
    """source is 'worktree', 'index', or a git ref."""
    if source == "worktree":
        files = sorted({p for g in globs for p in repo.glob(g) if p.is_file()})
        return {str(p.relative_to(repo)): _read_worktree(repo, p) for p in files}
    listing = git(repo, "ls-files", "-z") if source == "index" else \
        git(repo, "ls-tree", "-r", "-z", "--name-only", source)
    regexes = [glob_to_regex(g) for g in globs]
    names = sorted(n for n in listing.split("\0") if n and any(r.match(n) for r in regexes))
    prefix = ":" if source == "index" else f"{source}:"
    return {n: _show(repo, prefix + n) for n in names}


def read_baseline(repo: Path, rel: str, source: str) -> int:
    if source == "worktree":
        path = repo / rel
        if not path.is_file():
            raise KitError(f"{path}: baseline file missing")
        raw, where = _read_worktree(repo, path), str(path)
    elif source == "index":
        if not git(repo, "ls-files", "-z", "--", rel):
            raise KitError(f"{repo}: baseline {rel} is not tracked/staged")
        raw, where = _show(repo, f":{rel}"), f"{repo} :{rel}"
    else:
        if not git(repo, "ls-tree", "-z", source, "--", rel):
            raise KitError(f"{repo}: baseline file missing at {source}:{rel}")
        raw, where = _show(repo, f"{source}:{rel}"), f"{repo} {source}:{rel}"
    value = raw.strip()
    if not re.fullmatch(r"\d+", value):
        raise KitError(f"{where}: baseline must be one non-negative integer, got {value!r}")
    return int(value)


def run_gate(project: Path, cfg: dict, gate: str, source: str) -> tuple[int, int, list[Finding]]:
    repo, globs, base_rel = gate_paths(project, cfg, gate)
    files = collect(repo, globs, source)
    if gate == "paper" and not files:
        raise KitError(f"no files match lint.paper.globs {globs} in {repo} ({source})")
    findings = [f for name, text in files.items() for f in lint_text(text, name)]
    return len(findings), read_baseline(repo, base_rel, source), findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", type=Path, default=Path.cwd())
    ap.add_argument("--gate", choices=("paper", "slides"), required=True)
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--git-ref", help="lint files and baseline as of this git ref")
    src.add_argument("--index", action="store_true", help="lint the staged (index) version")
    src.add_argument("--precommit", action="store_true",
                    help="lint the index; block on regression; lower and stage the baseline on improvement")
    ap.add_argument("--write-baseline", action="store_true",
                    help="set the baseline to the current working-tree count")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    try:
        cfg = load_config(a.project)
        repo, globs, base_rel = gate_paths(a.project, cfg, a.gate)
        if a.write_baseline:
            files = collect(repo, globs, "worktree")
            if a.gate == "paper" and not files:
                raise KitError(f"no files match lint.paper.globs {globs} in {repo} (worktree)")
            count = sum(len(lint_text(t, n)) for n, t in files.items())
            (repo / base_rel).write_text(f"{count}\n", encoding="utf-8")
            print(f"{a.gate}: baseline set to {count}")
            return 0
        source = "index" if (a.index or a.precommit) else (a.git_ref or "worktree")
        count, baseline, findings = run_gate(a.project, cfg, a.gate, source)
        status = "ok" if count <= baseline else "REGRESSION"
        print(f"{a.gate} [{source}]: count={count} baseline={baseline} {status}")
        if a.verbose or count > baseline:
            for f in findings:
                print(f"  {f.file}:{f.line}: {f.token}")
        if count > baseline:
            if a.precommit:
                print("Commit blocked: replace the new numbers with macros, "
                      "or end the line with %num-ok if the number is not a result.")
            return 1
        if a.precommit and count < baseline:
            (repo / base_rel).write_text(f"{count}\n", encoding="utf-8")
            git(repo, "add", base_rel)
            print(f"{a.gate}: baseline lowered {baseline} -> {count} (staged)")
        return 0
    except KitError as e:
        print(f"lint_numbers: ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
