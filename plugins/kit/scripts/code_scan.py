"""Reading a project's R and Python code for the code map and the code gate (code spec sections 3 and 4):
which files there are, what class each belongs to, the functions they define, and the strings they hold."""
from __future__ import annotations

import ast
import re
import warnings
from dataclasses import dataclass
from pathlib import Path

from kitlib import KitError, git

CODE_SUFFIXES = (".R", ".r", ".py")
SKIP_DIRS = {"renv", ".venv"}
ARCHIVE_DIRS = {"archive", "_archive", "legacy", "retired"}
TEST_DIRS = {"tests", "test"}
TEST_FILE = re.compile(r"(test_.*\.py|.*_test\.py|test_.*\.[Rr]|test-.*\.[Rr]|conftest\.py|testthat\.R)")
FILE_EXT = re.compile(r"\.(csv|tsv|txt|parquet|feather|rds|rda|rdata|dta|xls|xlsx|json|yaml|yml|pkl|pickle|"
                      r"sqlite|db|gz|zip|pdf|png|svg|tex|html|r|py)$", re.I)
DATE = re.compile(r"\d{4}-\d{2}(-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?)?")
R_DEF = re.compile(r"([A-Za-z.][\w.]*)\s*(?:<-|=)\s*(?:function\s*\(|\\\()")
R_ASSIGN = re.compile(r"([A-Za-z.][\w.]*)\s*(?:<-|=(?!=))")
R_STRING = re.compile(r"\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'")


@dataclass
class Func:
    name: str
    args: str
    file: str
    line: int
    desc: str


def split_comment(line: str) -> tuple[str, str]:
    """The code before a # outside quotes, and the comment after it."""
    quote, i = None, 0
    while i < len(line):
        c = line[i]
        if quote:
            if c == "\\":
                i += 1
            elif c == quote:
                quote = None
        elif c in "\"'":
            quote = c
        elif c == "#":
            return line[:i], line[i + 1:]
        i += 1
    return line, ""


def literals(code: str) -> list[str]:
    """The quoted strings in one line of code (comments already removed)."""
    out, quote, cur, i = [], None, [], 0
    while i < len(code):
        c = code[i]
        if quote:
            if c == "\\" and i + 1 < len(code):
                cur.append(code[i + 1])
                i += 1
            elif c == quote:
                out.append("".join(cur))
                quote, cur = None, []
            else:
                cur.append(c)
        elif c in "\"'":
            quote = c
        i += 1
    return out


def depth_change(code: str) -> int:
    d = 0
    for c in R_STRING.sub("", code):
        d += c in "([{"
        d -= c in ")]}"
    return d


def classify(rel: str, library: list[str]) -> str:
    """test, archive, library, explore or pipeline: the first that matches, by directory names."""
    parts = rel.split("/")
    dirs, name = parts[:-1], parts[-1]
    if any(d in TEST_DIRS for d in dirs) or TEST_FILE.fullmatch(name):
        return "test"
    if any(d.lower() in ARCHIVE_DIRS for d in dirs) or (dirs and dirs[0] in ("docs", "notes")):
        return "archive"
    if any(rel == lib or rel.startswith(lib + "/") for lib in library):
        return "library"
    if any(d.lower().startswith(("explore", "scratch")) for d in dirs):
        return "explore"
    return "pipeline"


def library_folders(project: Path, cfg: dict) -> list[str]:
    """The `library` entries of research.yml, or else the package's source folders."""
    if "library" in cfg:
        entries = cfg["library"]
    else:
        pk = cfg["packages"]
        entries = (["pkg/r/R"] if "r" in pk else []) + ([f"pkg/python/src/{pk['python']}"] if "python" in pk else [])
    root, out = project.resolve(), []
    for e in entries:
        path = (root / e).resolve()
        if path == root or root not in path.parents:
            raise KitError(f"research.yml: library entry {e} is outside the project")
        if not path.exists():
            raise KitError(f"research.yml: library entry {e} does not exist")
        out.append(path.relative_to(root).as_posix())
    return out


def _z(text: str) -> list[str]:
    return [p for p in text.split("\0") if p]


def in_scope(rel: str, cfg: dict) -> bool:
    """A code file of the project's own: not in renv/, .venv/, a hidden folder or the paper clone."""
    return rel.endswith(CODE_SUFFIXES) and not rel.startswith(cfg["paper_dir"].rstrip("/") + "/") \
        and not any(d in SKIP_DIRS or d.startswith(".") for d in rel.split("/")[:-1])


def code_files(project: Path, cfg: dict, library: list[str]) -> tuple[list[str], list[str]]:
    """The code files git tracks or would track, and the library's code files that git ignores."""
    listed = _z(git(project, "ls-files", "--cached", "--others", "--exclude-standard", "-z"))
    files = sorted({f for f in listed if in_scope(f, cfg) and (project / f).is_file()})
    ignored = sorted({f for lib in library
                      for f in _z(git(project, "ls-files", "--others", "--ignored", "--exclude-standard", "-z",
                                      "--", lib)) if f.endswith(CODE_SUFFIXES)})
    return files, ignored


def _balanced_args(lines: list[str], i: int, start: int) -> str:
    text = "\n".join(lines[i:i + 30])[start:]
    d = 0
    for j, c in enumerate(text):
        d += c == "("
        d -= c == ")"
        if d == 0:
            return re.sub(r"\s+", " ", text[1:j]).strip()
    return ""


def _r_desc(lines: list[str], i: int, trailing: str) -> str:
    j, block = i - 1, []
    while j >= 0 and lines[j].lstrip().startswith("#'"):
        block.insert(0, lines[j].strip()[2:].strip())
        j -= 1
    for text in block:
        if text and not text.startswith("@"):
            return text
    while j >= 0 and lines[j].lstrip().startswith("#"):
        j -= 1
    for text in (lines[k].strip().lstrip("#").strip() for k in range(j + 1, i)):
        if text:
            return text
    return trailing.strip()


def r_functions(rel: str, lines: list[str]) -> list[Func]:
    """Top-level R functions; names that start with _ or . are private and left out."""
    funcs, depth = [], 0
    for i, line in enumerate(lines):
        code, comment = split_comment(line)
        if depth == 0 and (m := R_DEF.match(line)) and not m.group(1).startswith(("_", ".")):
            funcs.append(Func(m.group(1), _balanced_args(lines, i, m.end() - 1), rel, i + 1,
                              _r_desc(lines, i, comment)))
        depth = max(0, depth + depth_change(code))
    return funcs


def parse_python(text: str) -> ast.Module | None:
    """The syntax tree, or None if the code doesn't parse. A leading byte-order mark is dropped, as Python does."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            return ast.parse(text.removeprefix("\ufeff"))
    except (SyntaxError, ValueError):
        return None


def py_functions(rel: str, tree: ast.Module) -> list[Func]:
    """Top-level Python functions and classes; names that start with _ are left out."""
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not node.name.startswith("_"):
            args = "" if isinstance(node, ast.ClassDef) else ast.unparse(node.args)
            doc = (ast.get_docstring(node) or "").strip()
            out.append(Func(node.name, args, rel, node.lineno, doc.splitlines()[0] if doc else ""))
    return out
