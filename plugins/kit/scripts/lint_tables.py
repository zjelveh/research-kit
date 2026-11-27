#!/usr/bin/env python3
"""Checks on the paper's tables (table checks spec, docs/specs/2026-11-26-table-checks-design.md).

Counted, and gated with a ratchet by the paper repo's pre-commit hook (through lint_numbers.py --precommit):
  - hyphen for minus: a negative number in a table cell, in text mode, printed with a hyphen; or a macro in a
    generated file whose whole value is a negative number written with a hyphen;
  - stars without a legend: a star symbol in a table's cells that its legend doesn't define;
  - legends that disagree: a table whose legend gives a symbol another threshold than most tables give it.
Printed, not counted: negative zero, unresolved table inputs, and files the scanner can't parse (the last two also
stop the baseline from being lowered). --report lists where the paper mixes two forms of one thing.

Escapes: a line ending in %table-ok: <reason> drops that line's counted findings; %legend-ok: <reason> anywhere in a
table drops its legend findings.

Exit: 0 ok, 1 regression, 2 error.
"""
from __future__ import annotations

import argparse
import bisect
import posixpath
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lint_numbers  # noqa: E402
from check_bib import DEF_RE, INPUT_RE  # noqa: E402
from kitlib import KitError, git, glob_to_regex, load_config, paper_folders  # noqa: E402

BASELINE_NAME = ".lint_baseline_tables"
BLOCKED = ("Commit blocked: print negatives with a real minus ($-$ or \\ensuremath{-}) in the code that writes the "
           "table, give every star a legend, or end the line with %table-ok: <reason> (%legend-ok: <reason> for a "
           "legend given elsewhere).")

# A signed number (spec §3): digits with optional thousands groups and decimals, or a decimal part alone, then an
# optional exponent and percent. numbers_build uses the same pattern (spec §5).
NUMBER_BODY = r"(?:\d+(?:(?:,|\{,\}|\\,)\d{3})*(?:\.\d+)?|\.\d+)(?:[eE][-+]?\d+)?(?:\\%)?"
SIGNED_NUMBER = re.compile(rf"-?{NUMBER_BODY}")
NEGATIVE_NUMBER = re.compile(rf"-{NUMBER_BODY}")

TABULARS = ("tabular", "tabular*", "tabularx", "longtable")
TABLE_FLOATS = ("table", "table*", "sidewaystable", "sidewaystable*", "wraptable")
FLOATS = TABLE_FLOATS + ("figure", "figure*")
# A table's legend unit is the outermost of these around its tabular (kableExtra puts a longtable's notes in a
# ThreePartTable around it).
CONTAINERS = FLOATS + ("longtable", "ThreePartTable", "threeparttable")
# siunitx (and pgf's number printer) set their own minus: the table check skips their arguments; the number lint
# does not.
SIUNITX = {"num": "os", "SI": "oss", "qty": "oss", "tablenum": "os", "numrange": "oss", "SIrange": "osss",
           "qtyrange": "osss", "pgfmathprintnumber": "os"}

_BEGIN_END = re.compile(r"\\(begin|end)[ \t]*\{([A-Za-z*]+)\}")
_ROW_END = re.compile(r"\\\\|\\tabularnewline\b")
_END_DOCUMENT = re.compile(r"\\end[ \t]*\{document\}")
_CONDITIONAL = re.compile(r"\\(iffalse|if[A-Za-z]*|fi|else)(?![A-Za-z])")
_MACRO_DEF = re.compile(r"\\(?:(?:re)?newcommand|providecommand)\*?[ \t]*\{?[ \t]*\\([A-Za-z@]+)[ \t]*\}?[ \t]*"
                        r"(?:\[\d\])?[ \t]*\{([^{}]*(?:\{,\}[^{}]*)*)\}"
                        r"|\\[gex]?def[ \t]*\\([A-Za-z@]+)[ \t]*\{([^{}]*(?:\{,\}[^{}]*)*)\}")
_ZERO = r"(?:0+(?:\.0+)?|\.0+)(?![\d.])"
_NEG_ZERO = re.compile(rf"(?:(?<![\w.\-\\])-|\$-\$|\\textminus[ \t]*|\\ensuremath\{{-\}}|\\ensuremath\{{-(?={_ZERO})"
                       rf"|−)[ \t]*(?:\\,)?{_ZERO}")

# Star symbols used in cells: $^{**}$, ^\dagger, \sym{*}, \textsuperscript{*}, or *s right after a digit.
_SYM = r"\*{1,3}|\\dagger|\\ddagger"
_CELL_STAR = re.compile(rf"\^[ \t]*\{{?[ \t]*({_SYM})[ \t]*\}}?|\\sym\{{({_SYM})\}}|\\textsuperscript\{{({_SYM})\}}"
                        rf"|(?<=\d)(\*{{1,3}})(?!\*)")
# The same symbols used as note markers outside the cells, which the notes then explain: superscripts
# ("$^{\dagger}$ Unit B had no ..."), threeparttable's \item[*], or a symbol starting a note ("* Provisional").
# A symbol the notes use this way is not a star without a legend.
_MARKER = re.compile(rf"\^[ \t]*\{{?[ \t]*({_SYM})[ \t]*\}}?|\\textsuperscript\{{({_SYM})\}}"
                     rf"|\\item[ \t]*\[[ \t$]*({_SYM})[ \t$]*\]"
                     rf"|(?<![^\s.;:])(\*{{1,3}}|\\dagger|\\ddagger)(?=[ \t]+[A-Z])")
# Legends, read from each symbol forward (no nested repeats, so the time is linear): "$^{*}p<.05$", "* ($p<0.1$)",
# "\sym{*} \(p<0.05\)", "p-value $<$ 0.1"; "*** Significant at the 1 percent level"; fixest's "***: 0.001"; and
# lists, "***, **, * denote significance at the 1%, 5%, 10% levels" (or "1, 5 and 10 percent").
_SYM_TOKEN = re.compile(r"\*+|\\d?dagger(?![A-Za-z])")
_AFTER_P = re.compile(r"[ \t}$(]*(?:\\\([ \t$]*)?(?:\\textit\{p\}|\\emph\{p\}|\\mathit\{p\}|p)"
                      r"(?:-value)?[ \t$]*"
                      r"(?:<=|<|\\leq?(?![A-Za-z])|\\textless(?![A-Za-z])|≤)[ \t$]*"
                      r"(\d+(?:\.\d+)?(?:[ \t]*(?:\\?%|percent))?|\.\d+)")
_AFTER_SIG = re.compile(r"[ \t}$:]*(?:significant|significance)[ \t]+(?:at[ \t]+)?(?:the[ \t]+)?"
                        r"(\d+(?:\.\d+)?)[ \t]*(?:\\?%|percent|per[ \t]cent)", re.I)
_AFTER_FIXEST = re.compile(r"[ \t]*:[ \t]*(0?\.\d+)")
_AFTER_PCT = re.compile(r"[ \t}$:]*(\d+(?:\.\d+)?[ \t]*(?:\\?%|percent))")       # only after "signific..."
_SIGNIFICANCE = re.compile(r"signific", re.I)
_LIST_VERB = re.compile(r"\b(?:denotes?|indicates?|represents?|marks?)\b", re.I)
_SIG_SCOPE = re.compile(r"\.\s|[;&]|\\par(?![A-Za-z])|\\item(?![A-Za-z])|\\\\|\\end\{[^}]*\}|\n[ \t]*\n")
_CLAUSE_END = re.compile(r"\.(?!\d)|[;}]|\\item(?![A-Za-z])|\\par(?![A-Za-z])|\\\\|\n[ \t]*\n")
_CLAUSE_START = re.compile(r"\.\s|[;:&]|\\par(?![A-Za-z])|\\item(?![A-Za-z])|\\\\|\\end\{[^}]*\}|\n[ \t]*\n")
_P = r"(?:\\textit\{p\}|\\emph\{p\}|\\mathit\{p\}|p)"
_P_VALUE = re.compile(rf"{_P}[ \t]*\$?[ \t]*(?:<|=|>|\\leq?|\\geq?|\$<\$|\$=\$)[ \t]*\$?[ \t]*(0?)\.\d")
_CAPTION = re.compile(r"\\caption(?:\[[^\]]*\])?\{")
_BIG = re.compile(r"(?<![\w.,{}\\])(\d{1,3}(?:(?:,|\{,\}|\\,)\d{3})+|\d{5,})(?![\d.]|\{,\}|,\d|\\,\d)")


@dataclass
class Finding:
    file: str
    line: int
    kind: str          # "hyphen", "legend", "disagree"
    detail: str

    def text(self) -> str:
        return f"{self.file}:{self.line}: {self.detail}"


@dataclass
class Result:
    findings: list[Finding] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    hold: bool = False         # an unresolved table input or a skipped file: never lower the baseline

    @property
    def count(self) -> int:
        return len(self.findings)


# -- reading files from the worktree, the index or a commit ----------------------------------------------------------
class Source:
    """The paper repo's files as they are in the worktree, the index ("index") or a commit. Reads are strict UTF-8:
    a file that isn't is a KitError naming it."""

    def __init__(self, repo: Path, where: str = "worktree"):
        self.repo, self.where = Path(repo), where
        if where == "worktree":
            self.names = None
        else:
            listing = git(self.repo, "ls-files", "-z") if where == "index" else \
                git(self.repo, "ls-tree", "-r", "-z", "--name-only", where)
            self.names = {n for n in listing.split("\0") if n}
        self.cache: dict[str, str] = {}

    def exists(self, rel: str) -> bool:
        if self.names is not None:
            return rel in self.names
        return (self.repo / rel).is_file()

    def glob(self, pattern: str) -> list[str]:
        if self.names is None:
            return sorted(p.relative_to(self.repo).as_posix() for p in self.repo.glob(pattern) if p.is_file())
        rx = glob_to_regex(pattern)
        return sorted(n for n in self.names if rx.match(n))

    def under(self, folder: str) -> list[str]:
        """Every .tex file in `folder` (relative), not in its subfolders."""
        if self.names is None:
            d = self.repo / folder
            return sorted(f"{folder}/{p.name}" for p in d.glob("*.tex") if p.is_file()) if d.is_dir() else []
        return sorted(n for n in self.names if posixpath.dirname(n) == folder and n.endswith(".tex"))

    def read(self, rel: str) -> str:
        if rel not in self.cache:
            if self.names is None:
                try:
                    self.cache[rel] = (self.repo / rel).read_bytes().decode("utf-8")
                except UnicodeDecodeError:
                    raise KitError(f"{self.repo / rel}: not valid UTF-8") from None
            else:
                self.cache[rel] = lint_numbers._show(self.repo, (":" if self.where == "index" else f"{self.where}:")
                                                     + rel)
        return self.cache[rel]


# -- documents: a root file with its inputs read in place -------------------------------------------------------------
@dataclass
class Piece:
    start: int        # in the document
    end: int
    file: str
    offset: int       # in the file, at `start`


@dataclass
class Doc:
    text: str
    pieces: list[Piece]
    files: list[str]                                  # every file read, in order
    unresolved: list[tuple[int, str, tuple, str, int]] = field(default_factory=list)
    #             (position, name as written, the paths it could be, the file and offset of the \input)
    resolved: set[tuple[str, int]] = field(default_factory=set)   # (file, offset) of each \input that resolved

    def origin(self, pos: int) -> tuple[str, int]:
        """(file, offset in that file) of a document position."""
        k = bisect.bisect_right(self.starts, pos) - 1
        if k >= 0 and pos < self.pieces[k].end:
            p = self.pieces[k]
            return p.file, p.offset + pos - p.start
        last = self.pieces[k] if k >= 0 else (self.pieces[0] if self.pieces else Piece(0, 0, "", 0))
        return last.file, last.offset + max(0, pos - last.start)

    @property
    def starts(self) -> list[int]:
        if not hasattr(self, "_starts"):
            self._starts = [p.start for p in self.pieces]
        return self._starts


def comment_start(line: str) -> int:
    """Index of the first unescaped % in a line, or its length."""
    for m in re.finditer("%", line):
        i = m.start()
        if (i - len(line[:i].rstrip("\\"))) % 2 == 0:
            return i
    return len(line)


def without_comments(text: str) -> str:
    """Comments blanked with spaces, so positions stay the same."""
    out = []
    for line in text.split("\n"):
        k = comment_start(line)
        out.append(line[:k] + " " * (len(line) - k))
    return "\n".join(out)


def _blank(text: str, a: int, b: int) -> str:
    return text[:a] + re.sub(r"[^\n]", " ", text[a:b]) + text[b:]


def without_skipped(plain: str) -> str:
    """Comment-free text with what LaTeX never typesets blanked too: \\iffalse up to its \\fi (or \\else), and the
    raw environments the number lint skips (verbatim, comment, lstlisting, ...)."""
    out = plain
    for m in _BEGIN_END.finditer(plain):
        if m.group(1) == "begin" and m.group(2) in lint_numbers.RAW_ENVS:
            e = re.compile(rf"\\end[ \t]*\{{{re.escape(m.group(2))}\}}").search(plain, m.end())
            out = _blank(out, m.start(), e.end() if e else len(plain))
    conditionals = lint_numbers.TEX_CONDITIONALS | lint_numbers._declared_conditionals(plain)
    i, scanned, depth = 0, 0, 0                  # the brace depth at `scanned`, carried forward (linear time)
    while (m := _CONDITIONAL.search(out, i)) is not None:
        if m.group(1) != "iffalse":
            i = m.end()
            continue
        depth = _depth(out, scanned, m.start(), depth)
        scanned = m.start()
        if depth > 0 or _LET.search(out, max(0, m.start() - 80), m.start()):
            i = m.end()                           # inside a definition's body, or \let\ifdraft\iffalse
            continue
        depth, j, stop = 1, m.end(), len(out)
        while (n := _CONDITIONAL.search(out, j)) is not None:   # count only real TeX conditionals, as the
            word = n.group(1)                                   # number lint's scanner does (not \ifthenelse)
            j = n.end()
            if word == "fi":
                depth -= 1
            elif word == "else":
                depth -= depth == 1
            elif word in conditionals:
                depth += 1
            if depth == 0:
                stop = n.end()
                break
        out = _blank(out, m.start(), stop)
        i = stop
    return out


_LET = re.compile(r"\\let[ \t]*\\[A-Za-z@]+[ \t]*=?[ \t]*$")


def _depth(text: str, a: int, b: int, depth: int) -> int:
    """The brace depth at b, given the depth at a (escaped braces don't count)."""
    j = a
    while j < b:
        c = text[j]
        if c == "\\":
            j += 2
            continue
        depth += (c == "{") - (c == "}")
        j += 1
    return depth


def _resolve(name: str, dirs: list[str], src: Source) -> str | None:
    for rel in _candidates(name, dirs):
        for cand in (rel, f"{rel}.tex"):
            if src.exists(cand):
                return cand
    return None


def _candidates(name: str, dirs: list[str]) -> list[str]:
    """The repo paths an \\input name could be, from each folder LaTeX would try."""
    out = []
    for d in dirs:
        rel = posixpath.normpath(posixpath.join(d, name)) if d else posixpath.normpath(name)
        if not rel.startswith("../") and rel != ".." and rel not in out:
            out.append(rel)
    return out


def assemble(root: str, src: Source, defs: dict[str, str]) -> Doc:
    """The root with every \\input, \\include and \\subfile outside a comment (or an \\iffalse) replaced by the file
    it names, read from `src`. An input that is a document of its own (subfiles, standalone) gives its body only.
    Plain path macros in `defs` are expanded in the names; definitions found on the way are added."""
    root_dir = posixpath.dirname(root)
    parts: list[str] = []
    doc = Doc("", [], [])
    pos = 0

    def emit(text: str, f: str, offset: int) -> None:
        nonlocal pos
        if text:
            parts.append(text)
            doc.pieces.append(Piece(pos, pos + len(text), f, offset))
            pos += len(text)

    def walk(f: str, chain: tuple[str, ...]) -> None:
        text = src.read(f)
        doc.files.append(f)
        plain = without_skipped(without_comments(text))
        defs.update(DEF_RE.findall(plain))
        lo, hi = 0, len(text)
        if len(chain) > 1 and (body := lint_numbers._document_body(text)) is not None:
            end = _END_DOCUMENT.search(plain, body[1])
            lo, hi = body[1], (end.start() if end else len(text))
        last = lo
        for m in INPUT_RE.finditer(plain, lo, hi):
            name = (m.group(1) or m.group(2)).strip()
            if "#" in name:                                   # a macro's parameter, not a file
                continue
            expanded = re.sub(r"\\([A-Za-z]+)", lambda d: defs.get(d.group(1), d.group(0)), name)
            dirs = [root_dir, posixpath.dirname(f), ""]
            target = _resolve(expanded, dirs, src)
            emit(text[last:m.start()], f, last)
            if target is not None:
                doc.resolved.add((f, m.start()))
            if target is not None and target not in chain and len(chain) < 20:
                walk(target, chain + (target,))
            else:
                if target is None:
                    doc.unresolved.append((pos, name, tuple(_candidates(expanded, dirs)), f, m.start()))
                emit(text[m.start():m.end()], f, m.start())
            last = m.end()
        emit(text[last:hi], f, last)

    walk(root, (root,))
    doc.text = "".join(parts)
    return doc


def standalone(rel: str, src: Source) -> Doc:
    text = src.read(rel)
    return Doc(text, [Piece(0, len(text), rel, 0)], [rel])


# -- environments, tabulars and cells ---------------------------------------------------------------------------------
@dataclass
class Env:
    name: str
    begin: int        # at \begin
    body: int         # where the body starts
    end: int          # at \end


def environments(plain: str, names: tuple[str, ...]) -> list[Env]:
    """The named environments in comment-free text, matched with a stack, in order of \\begin."""
    out, stack = [], []
    for m in _BEGIN_END.finditer(plain):
        kind, name = m.groups()
        if name not in names:
            continue
        if kind == "begin":
            stack.append((name, m.start(), m.end()))
        else:
            for k in range(len(stack) - 1, -1, -1):
                if stack[k][0] == name:
                    n, b, body = stack.pop(k)
                    out.append(Env(n, b, body, m.start()))
                    break
    return sorted(out, key=lambda e: e.begin)


def _group_end(text: str, i: int) -> int:
    """Index just past the balanced {...} or [...] that opens at text[i]."""
    close = "}" if text[i] == "{" else "]"
    opener, depth, j = text[i], 0, i
    while j < len(text):
        c = text[j]
        if c == "\\":
            j += 2
            continue
        if c == opener:
            depth += 1
        elif c == close:
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    return len(text)


def column_types(spec: str, newtypes: dict[str, str], depth: int = 0) -> list[str]:
    """One type per column: "S" (siunitx), "D" (dcolumn), "M" (wrapped in math by >{$}...<{$}), or the letter."""
    out, i, math_next = [], 0, False
    while i < len(spec):
        ch = spec[i]
        if ch in " |\n\t":
            i += 1
        elif ch in "@!<":
            i += 1
            if i < len(spec) and spec[i] == "{":
                i = _group_end(spec, i)
        elif ch == ">":
            i += 1
            if i < len(spec) and spec[i] == "{":
                k = _group_end(spec, i)
                math_next = "$" in spec[i:k] or "\\(" in spec[i:k]
                i = k
        elif ch == "*" and i + 1 < len(spec):                  # *{3}{c}, *{3}c, *3{c} or *3c
            j = _group_end(spec, i + 1) if spec[i + 1] == "{" else i + 2
            count = spec[i + 1:j].strip("{} ")
            if j < len(spec) and spec[j] == "{":
                k = _group_end(spec, j)
                inner = spec[j + 1:k - 1]
            else:
                k = j + 1
                inner = spec[j:k]
            try:
                out += column_types(inner, newtypes, depth) * int(count)
            except ValueError:
                pass
            i = k
        elif ch.isalpha():
            i += 1
            if ch in newtypes and depth < 1:
                while i < len(spec) and spec[i] == "{":           # the new type's arguments
                    i = _group_end(spec, i)
                inner = column_types(newtypes[ch], newtypes, depth + 1)
                out += [("M" if math_next else t) for t in inner] or ["?"]
            else:
                while i < len(spec) and spec[i] in "{[":
                    i = _group_end(spec, i)
                out.append("M" if math_next else "S" if ch in "Ss" else "D" if ch == "D" else ch)
            math_next = False
        else:
            i += 1
    return out


def new_column_types(plain: str) -> dict[str, str]:
    """\\newcolumntype{d}[1]{D{.}{.}{#1}} -> {"d": "D{.}{.}{#1}"}, read from comment-free text."""
    out = {}
    for m in re.finditer(r"\\newcolumntype\{(\w)\}(?:\[\d\])?\{", plain):
        k = _group_end(plain, m.end() - 1)
        out[m.group(1)] = plain[m.end():k - 1]
    return out


@dataclass
class Cell:
    start: int
    end: int
    column: str        # its column type; "multi" for a \multicolumn cell


@dataclass
class Tabular:
    env: Env
    cells: list[Cell]


def tabulars(plain: str, newtypes: dict[str, str]) -> list[Tabular]:
    out = []
    for env in environments(plain, TABULARS):
        i = env.body
        if env.name in ("tabular*", "tabularx"):                  # the width
            i = _skip_space(plain, i)
            if i < env.end and plain[i] == "{":
                i = _group_end(plain, i)
        i = _skip_space(plain, i)
        if i < env.end and plain[i] == "[":
            i = _group_end(plain, i)
            i = _skip_space(plain, i)
        if i >= env.end or plain[i] != "{":
            continue
        k = _group_end(plain, i)
        types = column_types(plain[i + 1:k - 1], newtypes)
        out.append(Tabular(env, list(_cells(plain, k, env.end, types))))
    return out


def _skip_space(text: str, i: int) -> int:
    while i < len(text) and text[i] in " \t\n":
        i += 1
    return i


def _cells(plain: str, start: int, end: int, types: list[str]):
    """The cells between start and end: split at & and row ends outside braces and nested tabulars."""
    col, cell_start, depth, i, nested = 0, start, 0, start, 0
    while i < end:
        c = plain[i]
        if c == "\\":
            m = _BEGIN_END.match(plain, i)
            if m and m.group(2) in TABULARS:
                nested += 1 if m.group(1) == "begin" else -1
                i = m.end()
                continue
            if depth == 0 and nested == 0 and _ROW_END.match(plain, i):
                yield _cell(plain, cell_start, i, col, types)
                i = _ROW_END.match(plain, i).end()
                if i < end and plain[i] == "*":
                    i += 1
                j = _skip_space(plain, i)
                if j < end and plain[j] == "[":
                    i = _group_end(plain, j)
                col, cell_start = 0, i
                continue
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif c == "&" and depth == 0 and nested == 0:
            yield _cell(plain, cell_start, i, col, types)
            col += _multi_width(plain, cell_start, i)
            cell_start = i + 1
        i += 1
    yield _cell(plain, cell_start, end, col, types)


# A \multicolumn at the start of a cell, after any rules or row colours (\midrule, \cmidrule(lr){2-3}, \rowcolor{..}).
_LEAD = (r"(?:\\(?:hline|toprule|midrule|bottomrule|cmidrule|cline|addlinespace|rowcolor|noalign|specialrule|"
         r"hdashline)(?![A-Za-z])\*?(?:\([^)]*\))?(?:\[[^\]]*\])?(?:\{[^{}]*\})*\s*)*")
_MULTI = re.compile(rf"\s*{_LEAD}\\multicolumn\s*\{{\s*(\d+)\s*\}}")


def _multi_width(plain: str, start: int, end: int) -> int:
    m = _MULTI.match(plain, start, end)
    return int(m.group(1)) if m else 1


def _cell(plain: str, start: int, end: int, col: int, types: list[str]) -> Cell:
    if _MULTI.match(plain, start, end):
        return Cell(start, end, "multi")
    return Cell(start, end, types[col] if col < len(types) else "?")


# -- the checks -------------------------------------------------------------------------------------------------------
class _TableScanner(lint_numbers._Scanner):
    """The number lint's scanner, keeping every number in text mode, with siunitx's arguments skipped."""
    SIGNATURES = {**lint_numbers.COMMAND_SIGNATURES, **SIUNITX}

    def record(self, start: int, end: int, mode: str) -> None:
        if mode == lint_numbers.PROSE:
            self.found.append((start, self.text[start:end]))


def prose_numbers(text: str, fname: str) -> list[tuple[int, str]]:
    """(position, token) of every number in text mode; raises LintParseError as lint_text does."""
    scanner = _TableScanner(text, fname)
    body = lint_numbers._document_body(text)
    try:
        if body is None:
            scanner.scan(0, lint_numbers.PROSE, lint_numbers._Closer("eof", 0))
        else:
            scanner.scan(body[1], lint_numbers.PROSE, lint_numbers._Closer("document", body[0]))
    except RecursionError:
        raise lint_numbers.LintParseError(f"{fname}: nesting too deep to scan") from None
    return scanner.found


def _escaped_lines(text: str, marker: str) -> set[int]:
    out = set()
    for n, line in enumerate(text.split("\n"), start=1):
        k = comment_start(line)
        if line[k:].lstrip("%").lstrip().startswith(marker.lstrip("%")) and k < len(line):
            out.add(n)
    return out


class Checker:
    """Collects findings over every document of one source, each once by file and position."""

    def __init__(self, src: Source, generated: list[str], newtypes: dict[str, str] | None = None):
        self.src, self.generated, self.newtypes = src, generated, newtypes or {}
        self.result = Result()
        self.seen: set[tuple] = set()
        self.units: dict[tuple[str, int], dict] = {}     # (file, line of \begin) -> legend, stars used, raw text
        self.lines: dict[str, list[int]] = {}
        self.escaped: dict[str, set[int]] = {}
        self.unresolved: dict[tuple[str, int], tuple[str, int, str]] = {}   # (file, offset) -> (file, line, name)
        self.resolved: set[tuple[str, int]] = set()

    def line(self, f: str, offset: int) -> int:
        if f not in self.lines:
            self.lines[f] = [0] + [m.end() for m in re.finditer("\n", self.src.read(f))]
        return bisect.bisect_right(self.lines[f], offset)

    def where(self, doc: Doc, pos: int) -> tuple[str, int]:
        f, off = doc.origin(pos)
        return f, self.line(f, off)

    def add(self, key: tuple, f: str, line: int, kind: str, detail: str) -> None:
        """One finding per key (a file and a position in it), however many documents reach it."""
        if key in self.seen:
            return
        self.seen.add(key)
        if f not in self.escaped:
            self.escaped[f] = _escaped_lines(self.src.read(f), "%table-ok")
        if line not in self.escaped[f]:
            self.result.findings.append(Finding(f, line, kind, detail))

    def warn(self, msg: str) -> None:
        if msg not in self.result.warnings:
            self.result.warnings.append(msg)

    # cells: hyphen for minus, negative zero
    def cells(self, doc: Doc, units: bool) -> None:
        plain = without_skipped(without_comments(doc.text))
        if units:
            self._inputs(doc, plain)
        tabs = tabulars(plain, self.newtypes)
        if not tabs:
            return
        numbers = self._numbers(doc)
        if numbers is None:
            return
        hyphens: dict[tuple[int, int], list[int]] = {}          # (tabular, cell) -> positions of hyphen numbers
        for pos, token in numbers:
            inner = [k for k, tb in enumerate(tabs) if tb.env.begin <= pos < tb.env.end]
            if not inner:
                continue
            k = max(inner, key=lambda k: tabs[k].env.begin)           # the innermost tabular
            cells = tabs[k].cells
            c = bisect.bisect_right([x.start for x in cells], pos) - 1
            if c < 0 or not cells[c].start <= pos < cells[c].end or cells[c].column in ("S", "D", "M"):
                continue
            if pos > 0 and doc.text[pos - 1] == "-" and (pos < 2 or not re.match(r"[\w.\-\\]", doc.text[pos - 2])):
                hyphens.setdefault((k, c), []).append(pos - 1)
        for spots in hyphens.values():
            f, off = doc.origin(spots[0])
            first = NEGATIVE_NUMBER.match(doc.text, spots[0])
            more = f" (and {len(spots) - 1} more in this cell)" if len(spots) > 1 else ""
            self.add(("hyphen", f, off), f, self.line(f, off), "hyphen",
                     f"hyphen for minus: {first.group() if first else '-'}{more}")
        for tb in tabs:
            for c in tb.cells:
                if c.column in ("S", "D", "M"):
                    continue
                for m in _NEG_ZERO.finditer(plain, c.start, c.end):
                    f, line = self.where(doc, m.start())
                    self.warn(f"{f}:{line}: negative zero: {m.group().strip()} (no sign on a value that rounds to "
                              f"zero; on an interval bound the sign says the interval reaches below zero, so show "
                              f"more decimals instead, such as -0.04)")
        if units:
            self._units(doc, plain, tabs)

    def _numbers(self, doc: Doc) -> list[tuple[int, str]] | None:
        try:
            return prose_numbers(doc.text, doc.files[0])
        except lint_numbers.LintParseError:
            pass
        if len(doc.files) == 1:
            self._skip(doc.files[0])
            return None
        found = []                       # the assembled document failed: scan each file on its own
        for f in dict.fromkeys(doc.files):
            text = self.src.read(f)
            try:
                own = prose_numbers(text, f)
            except lint_numbers.LintParseError:
                self._skip(f)
                continue
            starts = [p for p in doc.pieces if p.file == f]
            for off, token in own:
                for p in starts:
                    if p.offset <= off < p.offset + (p.end - p.start):
                        found.append((p.start + off - p.offset, token))
                        break
        return sorted(found)

    def _skip(self, f: str) -> None:
        self.result.hold = True
        self.warn(f"{f}: skipped: the scanner can't parse it (its cells are not checked, and the baseline is not "
                  f"lowered while it is skipped)")

    # macros in generated files
    def macros(self, f: str) -> None:
        if not any(f == g or f.startswith(g + "/") for g in self.generated):
            return
        plain = without_skipped(without_comments(self.src.read(f)))
        for m in _MACRO_DEF.finditer(plain):
            name, value = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
            value = value.strip()
            if NEGATIVE_NUMBER.fullmatch(value):
                line = self.line(f, m.start())
                advice = " (rerun numbers_build)" if posixpath.basename(f) == "numbers.tex" else ""
                if re.fullmatch(rf"-{_ZERO}(?:\\%)?", value):
                    self.warn(f"{f}:{line}: negative zero in \\{name}: {value}")
                self.add(("hyphen", f, m.start()), f, line, "hyphen", f"hyphen for minus in \\{name}: {value}{advice}")

    # legends
    def _units(self, doc: Doc, plain: str, tabs: list[Tabular]) -> None:
        containers = environments(plain, CONTAINERS)
        for tb in tabs:
            around = [e for e in containers if e.begin <= tb.env.begin and tb.env.end <= e.end]
            if around:
                unit = min(around, key=lambda e: e.begin)                # the outermost
                key, span = self.where(doc, unit.begin), (unit.begin, unit.end)
            else:                                                       # its legend may be anywhere in its file
                key = self.where(doc, tb.env.begin)
                span = self._file_span(doc, key[0])
            u = self.units.get(key)
            if u is None:
                inside = [c for t2 in tabs if span[0] <= t2.env.begin and t2.env.end <= span[1] for c in t2.cells]
                cell_spans = [(c.start, c.end) for c in inside]
                parts = legend_parts(plain, span[0], span[1])
                u = self.units[key] = {
                    "raw": doc.text[span[0]:span[1]], "used": set(),
                    "legend": _legend_dict(parts), "spans": [(a, b) for _, _, a, b in parts],
                    "marked": {next(g for g in m.groups() if g) for m in _MARKER.finditer(plain, span[0], span[1])
                               if not any(a <= m.start() < b for a, b in cell_spans)}}
            for c in tb.cells:
                for m in _CELL_STAR.finditer(plain, c.start, c.end):
                    if not any(a <= m.start() < b for a, b in u["spans"]) and _star_counts(plain, m):
                        u["used"].add(next(g for g in m.groups() if g))

    def _inputs(self, doc: Doc, plain: str) -> None:
        """Note each unresolved input inside a table or naming a file in tables/ or generated/; finish() warns
        about those that no document resolves."""
        self.resolved |= doc.resolved
        floats = environments(plain, CONTAINERS)
        for pos, name, cands, f, off in doc.unresolved:
            if any(e.begin <= pos < e.end for e in floats) or any(self._is_generated_path(c) for c in cands):
                self.unresolved.setdefault((f, off), (f, self.line(f, off), name))

    def _is_generated_path(self, path: str) -> bool:
        return any(path == g or path.startswith(g + "/") for g in self.generated)

    def _file_span(self, doc: Doc, f: str) -> tuple[int, int]:
        ps = [p for p in doc.pieces if p.file == f]
        return (ps[0].start, ps[-1].end) if ps else (0, len(doc.text))

    def finish(self) -> None:
        for key, (f, line, name) in self.unresolved.items():
            if key not in self.resolved:
                self.result.hold = True
                self.warn(f"{f}:{line}: \\input{{{name}}} doesn't resolve here (its tables are not checked, and the "
                          f"baseline is not lowered until it does)")
        self.legends()

    def legends(self) -> None:
        """Stars without a legend, and legends that disagree with the paper's most common thresholds."""
        votes: dict[str, Counter] = {}
        order: dict[tuple[str, float], int] = {}
        live = {k: u for k, u in self.units.items() if not re.search(r"(?<!\\)%[ \t]*legend-ok", u["raw"])}
        for n, (k, u) in enumerate(live.items()):
            for sym, thr in u["legend"].items():
                votes.setdefault(sym, Counter())[thr] += 1
                order.setdefault((sym, thr), n)
        ref = {sym: max(c, key=lambda thr: (c[thr], -order[(sym, thr)])) for sym, c in votes.items()}
        for (f, line), u in live.items():
            missing = sorted(u["used"] - set(u["legend"]) - u["marked"], key=lambda s: (len(s), s))
            if missing:
                self.add(("legend", f, line), f, line, "legend", f"stars without a legend: {', '.join(missing)}")
            other = {s: t for s, t in u["legend"].items() if ref.get(s) != t}
            if other:
                detail = ", ".join(f"{s} p<{_fmt(t)} (most tables: {_fmt(ref[s])})" for s, t in sorted(other.items()))
                self.add(("disagree", f, line), f, line, "disagree", f"legend disagrees with the paper's: {detail}")


def _star_counts(plain: str, m: re.Match) -> bool:
    """Whether a star symbol in a cell marks significance: after a number, a closing parenthesis or bracket, a
    percent or a dash. Not after a name or a subscript ($C^*$, $\\theta_1^*$, $x_{0}^{*}$), and not a product
    (x1*x2)."""
    if m.group(2):                                   # \sym{..}
        return True
    if m.group(4):                                   # *s right after a digit
        return not plain[m.end():m.end() + 1].isalnum() and _number_before(plain, m.start())
    i = m.start() - 1
    while i >= 0 and plain[i] in " \t$":
        i -= 1
    if i >= 0 and plain[i] == "}":
        i -= 1
    if i < 0:
        return False
    return plain[i] in ")]%-" or (plain[i].isdigit() and _number_before(plain, i + 1))


def _number_before(plain: str, end: int) -> bool:
    """The digits ending at `end` are a number, not part of a name (x1) or a subscript (\\theta_1, x_{0})."""
    i = end - 1
    while i >= 0 and (plain[i].isdigit() or plain[i] in ".,"):
        i -= 1
    if i >= 1 and plain[i] == "{" and plain[i - 1] == "_":
        return False
    return not (i >= 0 and (plain[i].isalpha() or plain[i] == "_"))


def _symbols(plain: str, lo: int, hi: int):
    """(start, end, symbol) for each run of one to three stars, \\dagger or \\ddagger between lo and hi."""
    for m in _SYM_TOKEN.finditer(plain, lo, hi):
        s = m.group()
        if s.startswith("*") and len(s) > 3:
            continue
        yield m.start(), m.end(), s


def _wrapper_start(plain: str, i: int) -> int:
    """Where a legend symbol's wrapper starts: $^{, \\sym{ or \\textsuperscript{ before it."""
    while i > 0 and plain[i - 1] in " \t{^$":
        i -= 1
        for cmd in ("\\sym", "\\textsuperscript"):
            if plain.startswith(cmd, i - len(cmd)) and plain[i] == "{":
                i -= len(cmd)
    return i


def legend_parts(plain: str, lo: int = 0, hi: int | None = None) -> list[tuple[str, float, int, int]]:
    """(symbol, threshold, start, end) for each legend entry between lo and hi (comment-free text)."""
    hi = len(plain) if hi is None else hi
    out = []
    for s, e, sym in _symbols(plain, lo, hi):
        for rx in (_AFTER_P, _AFTER_SIG, _AFTER_FIXEST, _AFTER_PCT):
            if rx is _AFTER_PCT and not _significance_clause(plain, max(lo, s - 80), s):
                continue
            m = rx.match(plain, e, hi)
            if m:
                thr = m.group(1) + ("%" if rx is _AFTER_SIG else "")
                out.append((sym, _threshold(thr), _wrapper_start(plain, s), m.end()))
                break
    for v in _LIST_VERB.finditer(plain, lo, hi):
        start = max(lo, v.start() - 200)
        for b in _CLAUSE_START.finditer(plain, start, v.start()):  # the list starts after the last boundary
            start = b.end()
        end = _CLAUSE_END.search(plain, v.end(), hi)
        stop = min(end.start() if end else hi, v.end() + 200)
        syms = list(_symbols(plain, start, v.start()))
        tail = plain[v.end():stop]
        nums = re.findall(r"\d+(?:\.\d+)?", tail)
        if len(syms) >= 2 and len(nums) == len(syms) and re.search(r"\\?%|percent", tail):
            first = _wrapper_start(plain, syms[0][0])
            out += [(sym, _threshold(n + "%"), first, stop) for (_, _, sym), n in zip(syms, nums)]
    return out


def _significance_clause(plain: str, lo: int, s: int) -> bool:
    """Whether "signific..." comes before s in the same clause (not across a cell, a row or a sentence)."""
    for b in _SIG_SCOPE.finditer(plain, lo, s):
        lo = b.end()
    return _SIGNIFICANCE.search(plain, lo, s) is not None


def _legend_dict(parts: list[tuple[str, float, int, int]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for sym, thr, _, _ in parts:
        out.setdefault(sym, thr)
    return out


def legend(plain: str) -> dict[str, float]:
    """{symbol: threshold} from every legend form in a table's text (comments removed)."""
    return _legend_dict(legend_parts(plain))


def _fmt(t: float) -> str:
    return f"{t:g}".lstrip("0") if t < 1 else f"{t:g}"


def _threshold(s: str) -> float:
    """The p threshold a legend gives. A confidence level ("* 90%", "significant at the 95% level") is its
    complement."""
    s = s.replace("\\", "").replace(" ", "").replace("\t", "")
    for suffix in ("%", "percent"):
        if s.endswith(suffix):
            value = float(s[:-len(suffix)].rstrip("%")) / 100
            break
    else:
        value = float(s)
    return round(1 - value if value > 0.5 else value, 6)


# -- running the checks on a paper ------------------------------------------------------------------------------------
def paper_paths(project: Path, cfg: dict) -> tuple[Path, list[str], str, list[str], str]:
    """(paper repo, manuscript globs, tables folder, generated folders, baseline path), paths relative to the repo."""
    paper = (Path(project) / cfg["paper_dir"]).resolve()
    folders = [d.relative_to(paper).as_posix() for d in paper_folders(project, cfg, paper)]
    tables = folders[-1]
    generated = folders[:-2] + [tables]
    base_rel = posixpath.join(posixpath.dirname(cfg["lint"]["paper"]["baseline"]), BASELINE_NAME)
    return paper, list(cfg["lint"]["paper"]["globs"]), tables, generated, base_rel


def check(project: Path, cfg: dict, where: str = "worktree") -> Result:
    """Every counted finding and warning in the paper as it is at `where` (worktree, index or a commit)."""
    paper, globs, tables, generated, _ = paper_paths(project, cfg)
    src = Source(paper, where)
    docs = _documents(src, globs)
    reached = [f for doc in docs for f in doc.files]
    alone = [standalone(f, src) for f in src.under(tables) if f not in reached]
    newtypes: dict[str, str] = {}                           # \newcolumntype from every root, for every table
    for doc in docs + alone:
        newtypes.update(new_column_types(without_skipped(without_comments(doc.text))))
    checker = Checker(src, generated, newtypes)
    for doc in docs:
        checker.cells(doc, units=True)
    for doc in alone:
        checker.cells(doc, units=False)
    for f in dict.fromkeys(reached + src.under(tables)):
        checker.macros(f)
    checker.finish()
    checker.result.findings.sort(key=lambda x: (x.file, x.line, x.kind, x.detail))
    return checker.result


def _documents(src: Source, globs: list[str]) -> list[Doc]:
    roots = sorted({r for g in globs for r in src.glob(g)})
    defs: dict[str, str] = {}
    for r in roots:                                         # once to learn the path macros,
        assemble(r, src, defs)
    return [assemble(r, src, dict(defs)) for r in roots]    # then with all of them


def read_baseline(paper: Path, rel: str, where: str) -> int | None:
    """The table baseline at `where`, or None when there is none there."""
    if where == "worktree":
        p = paper / rel
        if not p.is_file():
            return None
        raw = p.read_text(encoding="utf-8")
    else:
        listing = git(paper, "ls-files", "-z", "--", rel) if where == "index" else \
            git(paper, "ls-tree", "-z", where, "--", rel)
        if not listing:
            return None
        raw = lint_numbers._show(paper, (":" if where == "index" else f"{where}:") + rel)
    value = raw.strip()
    if not re.fullmatch(r"\d+", value):
        raise KitError(f"{paper / rel}: the table baseline must be one non-negative integer, got {value!r}")
    return int(value)


@dataclass
class Gate:
    code: int                   # 0 ok, 1 regression, 2 error
    lines: list[str]
    write: int | None = None    # the baseline to write and stage if the combined result is 0
    note: str = ""              # printed once it is written


def gate(project: Path, cfg: dict) -> Gate:
    """The table check on the index against the table baseline (spec §4). Writes nothing: the caller writes
    `write` only when its combined result is 0."""
    try:
        paper, *_, rel = paper_paths(project, cfg)
        res = check(project, cfg, "index")
        lines = [f"  warning: {w}" for w in res.warnings]
        baseline = read_baseline(paper, rel, "index")
        first = baseline is None
        if first:
            head = git(paper, "rev-parse", "-q", "--verify", "HEAD^{commit}", check=False).strip()
            if not head:
                baseline, how = 0, "no HEAD"
            else:
                try:
                    baseline, how = check(project, cfg, head).count, "HEAD"
                except KitError as e:
                    baseline, how = res.count, f"staged count: HEAD can't be read ({e})"
        status = "ok" if res.count <= baseline else "REGRESSION"
        head_lines = [f"tables [index]: count={res.count} baseline={baseline} {status}"]
        if res.count > baseline:
            return Gate(1, head_lines + [f"  {f.text()}" for f in res.findings] + lines + [BLOCKED])
        if first:
            value = baseline if res.hold else min(baseline, res.count)
            why = f"HEAD {baseline}, staged {res.count}" if how == "HEAD" else how
            return Gate(0, head_lines + lines, value, f"tables: baseline set to {value} ({why}) (staged)")
        if res.count < baseline and not res.hold:
            return Gate(0, head_lines + lines, res.count,
                        f"tables: baseline lowered {baseline} -> {res.count} (staged)")
        return Gate(0, head_lines + lines)
    except (KitError, lint_numbers.LintParseError) as e:
        return Gate(2, [f"lint_tables: ERROR: {e}"])


def write_baseline(project: Path, cfg: dict, value: int, stage: bool) -> None:
    paper, *_, rel = paper_paths(project, cfg)
    (paper / rel).parent.mkdir(parents=True, exist_ok=True)
    (paper / rel).write_text(f"{value}\n", encoding="utf-8")
    if stage:
        git(paper, "add", "--", rel)


# -- the consistency report -------------------------------------------------------------------------------------------
def report(project: Path, cfg: dict) -> list[str]:
    """Where the paper mixes two forms of one thing (spec §3), read from the worktree."""
    paper, globs, tables, generated, _ = paper_paths(project, cfg)
    src = Source(paper)
    docs = _documents(src, globs)
    forms: dict[str, dict[str, list[str]]] = {"p-values": {}, "captions": {}, "thousands": {}}
    seen = set()
    checker = Checker(src, generated)
    for doc in docs:
        plain = without_skipped(without_comments(doc.text))
        for m in _P_VALUE.finditer(plain):
            _note(forms["p-values"], "0.05" if m.group(1) else ".05", checker.where(doc, m.start()), seen)
        for e in environments(plain, TABLE_FLOATS + ("longtable", "ThreePartTable")):
            for m in _CAPTION.finditer(plain, e.begin, e.end):
                k = _group_end(plain, m.end() - 1)
                cap = re.sub(r"\\label\{[^}]*\}", "", plain[m.end():k - 1]).strip()
                _note(forms["captions"], "final period" if cap.endswith(".") else "no final period",
                      checker.where(doc, m.start()), seen)
        for t in tabulars(plain, new_column_types(plain)):
            for c in t.cells:
                for m in _BIG.finditer(plain, c.start, c.end):
                    _note(forms["thousands"], "separator" if not m.group(1).isdigit() else "no separator",
                          checker.where(doc, m.start()), seen)
    out = []
    for what, by_form in forms.items():
        if len(by_form) > 1:
            minority = min(by_form, key=lambda k: len(by_form[k]))
            out.append(f"{what}: {', '.join(f'{k} {len(v)}' for k, v in by_form.items())}; the less common form:")
            out += [f"  {w}" for w in by_form[minority]]
    out += _slide_legends(project, cfg, docs, src, generated)
    return out or ["tables: no mixed forms"]


def _note(forms: dict[str, list[str]], form: str, where: tuple[str, int], seen: set) -> None:
    key = (form, where)
    if key not in seen:
        seen.add(key)
        forms.setdefault(form, []).append(f"{where[0]}:{where[1]}")


def _slide_legends(project: Path, cfg: dict, docs: list[Doc], src: Source, generated: list[str]) -> list[str]:
    paper_votes: dict[str, Counter] = {}
    for doc in docs:
        plain = without_skipped(without_comments(doc.text))
        for e in environments(plain, CONTAINERS):
            for s, t in legend(plain[e.begin:e.end]).items():
                paper_votes.setdefault(s, Counter())[t] += 1
    ref = {s: c.most_common(1)[0][0] for s, c in paper_votes.items()}
    out = []
    slides = Source(Path(project))
    for g in cfg["lint"].get("slides", {}).get("globs", []):
        for rel in slides.glob(g):
            for s, t in legend(without_comments(slides.read(rel))).items():
                if s in ref and ref[s] != t:
                    out.append(f"slides: {rel}: {s} p<{_fmt(t)}, the paper's {s} p<{_fmt(ref[s])}")
    return out


# -- the command line -------------------------------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", type=Path, default=Path.cwd())
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--index", action="store_true", help="check the staged files against the staged baseline")
    src.add_argument("--git-ref", help="check the files and the baseline as of this git ref")
    src.add_argument("--write-baseline", action="store_true", help="set the baseline to the working tree's count")
    src.add_argument("--report", action="store_true", help="list where the paper mixes two forms (working tree)")
    ap.add_argument("-v", "--verbose", action="store_true", help="list every finding")
    a = ap.parse_args(argv)
    try:
        cfg = load_config(a.project)
        if a.report:
            print("\n".join(report(a.project, cfg)))
            return 0
        if a.write_baseline:
            count = check(a.project, cfg, "worktree").count
            write_baseline(a.project, cfg, count, stage=False)
            print(f"tables: baseline set to {count}")
            return 0
        where = "index" if a.index else (a.git_ref or "worktree")
        res = check(a.project, cfg, where)
        paper, *_, rel = paper_paths(a.project, cfg)
        baseline = read_baseline(paper, rel, where)
        if baseline is None:
            print(f"tables [{where}]: count={res.count} baseline: none")
            regress = False
        else:
            regress = res.count > baseline
            print(f"tables [{where}]: count={res.count} baseline={baseline} {'REGRESSION' if regress else 'ok'}")
        if a.verbose or regress:
            print("\n".join(f"  {f.text()}" for f in res.findings))
        for w in res.warnings:
            print(f"  warning: {w}")
        return 1 if regress else 0
    except (KitError, lint_numbers.LintParseError) as e:
        print(f"lint_tables: ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
