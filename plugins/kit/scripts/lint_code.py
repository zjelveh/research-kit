#!/usr/bin/env python3
"""The code gate (code spec section 3): no typed numbers, dates or paths in code.

  lint_code.py --project P --precommit     the staged lines a commit adds (the pre-commit hook)
  lint_code.py --project P --files F ... [--base REV]
                                           the lines changed since REV (default HEAD) in these files,
                                           committed or not, and all of a file new since then;
                                           --base none checks the files whole
  lint_code.py --project P --all           every line, as counts by file: the project's backlog
  lint_code.py --project P --all F ...     every finding in these files, for a clean-up

Flags, in R and Python code that is not a test or archived: numbers other than 0, 1, 2 and 100 (and their
negatives), dates, and paths or file names. They belong in analysis/params.yml (or the explore file),
read with param("name"). In a package (pkg/), a number may also be a function default or part of a
top-level named constant, and param() is not used. A line that ends in `# literal: <reason>` is allowed.
A pipeline script defines no function (main and parse_args aside): the paper's code lives in the library.
A new library function may not be a near copy of another library function (near_copy.py): one function with
an argument does for both, unless its definition line ends in `# distinct: <reason>`.
Also checks the parameter files' format, and that every param("name") exists and that pipeline code uses no
explore parameter. A moved file counts only its changed lines; in a merge, only lines new to both parents.
Exit: 0 nothing found (always, with --all), 1 findings, 2 config or project error.
"""
from __future__ import annotations

import argparse
import ast
import os
import posixpath
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit_params  # noqa: E402
import near_copy  # noqa: E402
from code_scan import (CODE_SUFFIXES, DATE, ENTRY_POINTS, FILE_EXT, R_ASSIGN, R_DEF, R_STRING,  # noqa: E402
                       classify, code_files, depth_change, git_names, in_scope, kits_reader, library_folders,
                       lines_of, literals, parse_python, split_comment, top_level_definitions)
from kitlib import CONFIG_REL, KitError, find_project, git, load_config  # noqa: E402

ALLOWED_NUMBERS = {0, 1, 2, 100}
ESCAPE = re.compile(r"\bliteral:\s*\S")
R_NUMBER = re.compile(r"(?<![\w.])(\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)L?(?![\w.])")
FORMAT = re.compile(r"%[-+ #0]*\d*(?:\.\d+)?[a-zA-Z]")
# A diff that the user's git settings and attributes can't change: no external diff tool, colour, text
# conversion, merged hunks or binary treatment.
DIFF = ("diff", "--no-ext-diff", "--no-color", "--no-textconv", "--text", "--inter-hunk-context=0", "-U0", "-M")
CODE_PATHS = ("*.R", "*.r", "*.py")
PARAM_CALL = re.compile(r"(?<![\w.])param(?:_path)?\(\s*[\"']([^\"']*)[\"']\s*\)")
HUNK = re.compile(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@", re.M)
NEAR = " is a near copy of "
FINDING = re.compile(r"(.*?):\d+: ")


def kind_of_string(s: str) -> str | None:
    """"date" or "path" for a string that is one, else None. Paths of code files are how scripts load the
    library (source(), imports), so they are not flagged."""
    if DATE.fullmatch(s):
        return "date"
    if re.search(r"\s", s) or s.endswith(CODE_SUFFIXES) or not re.search(r"[A-Za-z0-9]", s):
        return None
    if (m := FILE_EXT.search(s)):
        stem = FORMAT.sub("", s[:m.start()])
        # ".csv", "*.csv" or "%s.csv" is an extension for a name built in code, not a file name
        return "path" if "/" in s or re.search(r"[A-Za-z0-9]", stem) else None
    return "path" if "/" in s and not FORMAT.search(s) else None   # "%m/%d/%Y" is a format, not a path


def _number_ok(v: float) -> bool:
    return abs(v) in ALLOWED_NUMBERS


def python_literals(text: str, package: bool) -> list[tuple[int, str, object]] | None:
    """(line, kind, value) for each typed value in Python code, or None if it doesn't parse."""
    tree = parse_python(text)
    if tree is None:
        return None
    allowed = set()
    docstrings = {id(n.body[0].value) for n in ast.walk(tree)
                  if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.body
                  and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
    if package:                                      # numbers in defaults and top-level constants (not strings)
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                allowed |= {id(x) for d in (*n.args.defaults, *n.args.kw_defaults) if d for x in ast.walk(d)}
        for n in tree.body:
            if isinstance(n, (ast.Assign, ast.AnnAssign)) and n.value is not None:
                allowed |= {id(x) for x in ast.walk(n.value)}
    negated = {id(n.operand) for n in ast.walk(tree) if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub)}
    out = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Constant) or id(n) in docstrings:
            continue
        if isinstance(n.value, (int, float)) and not isinstance(n.value, bool) and not _number_ok(n.value) \
                and id(n) not in allowed:
            out.append((n.lineno, "number", -n.value if id(n) in negated else n.value))
        elif isinstance(n.value, str) and (k := kind_of_string(n.value)):
            out.append((n.lineno, k, n.value))
    return out


def _r_formals(code: str) -> list[tuple[int, int]]:
    """Character spans of function formals in R code with strings blanked and comments removed."""
    spans = []
    for m in re.finditer(r"(?:function|\\)\s*\(", code):
        depth = 0
        for j in range(m.end() - 1, len(code)):
            depth += code[j] == "("
            depth -= code[j] == ")"
            if depth == 0:
                spans.append((m.end(), j))
                break
    return spans


def _r_top_assignments(codes: list[str]) -> set[int]:
    """Line numbers of top-level assignments that are not functions, through the end of each expression."""
    lines, depth, i = set(), 0, 0
    while i < len(codes):
        if depth == 0 and R_ASSIGN.match(codes[i]) and not R_DEF.match(codes[i]):
            j, d = i, depth_change(codes[i])
            while d > 0 and j + 1 < len(codes):
                j += 1
                d += depth_change(codes[j])
            if not any(re.search(r"function\s*\(|\\\(", c) for c in codes[i:j + 1]):   # methods are code, not constants
                lines.update(range(i + 1, j + 2))
            i = j + 1
            continue
        depth = max(0, depth + depth_change(codes[i]))
        i += 1
    return lines


def r_literals(text: str, package: bool) -> list[tuple[int, str, object]]:
    lines = lines_of(text)
    codes = [split_comment(line)[0] for line in lines]
    out = []
    for n, code in enumerate(codes, 1):
        for s in literals(code):
            if k := kind_of_string(s):
                out.append((n, k, s))
    blanked = "\n".join(R_STRING.sub(lambda m: '"' + " " * (len(m.group()) - 2) + '"', c) for c in codes)
    formals = _r_formals(blanked) if package else []
    constants = _r_top_assignments(codes) if package else set()
    starts = [0]
    for c in codes:
        starts.append(starts[-1] + len(c) + 1)
    for m in R_NUMBER.finditer(blanked):
        v = float(m.group(1))
        if _number_ok(v):
            continue
        n = next(i for i in range(len(codes)) if starts[i + 1] > m.start()) + 1
        if package and (any(a <= m.start() < b for a, b in formals) or n in constants):
            continue
        out.append((n, "number", v))
    return out


def param_calls(rel: str, text: str) -> list[tuple[int, str]]:
    """(line, name) for each param("name") call: from the syntax tree in Python, so that docstrings and
    comments don't count, and from the code outside comments in R."""
    if rel.endswith(".py"):
        tree = parse_python(text)
        return [] if tree is None else [
            (n.lineno, n.args[0].value) for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("param", "param_path")
            and n.args
            and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str)]
    return [(n, name) for n, line in enumerate(lines_of(text), 1)
            for name in PARAM_CALL.findall(split_comment(line)[0])]


def lint_text(rel: str, text: str, cls: str, lines: set[int] | None, pipe: dict, expl: dict,
              hints: dict, old_defs: set[str] = frozenset()) -> list[str]:
    """Findings, as `file:line: message`, for the given lines of one code file (all when lines is None).
    A function the file already defined before (old_defs) may be edited."""
    if cls in ("test", "archive"):
        return []
    package = rel.startswith("pkg/")
    raw = lines_of(text)
    found = python_literals(text, package) if rel.endswith(".py") else r_literals(text, package)
    if found is None:
        return [f"{rel}:1: Python that does not parse; fix it before committing"]
    out = []
    for n, kind, value in sorted(found, key=lambda x: x[0]):
        if (lines is None or n in lines) and n <= len(raw) and not ESCAPE.search(split_comment(raw[n - 1])[1]):
            shown = repr(value) if isinstance(value, str) else \
                str(int(value)) if float(value).is_integer() and abs(value) < 1e15 else f"{value:g}"
            hint = f" (it is param('{hints[value]}'))" if value in hints else ""
            out.append(f"{rel}:{n}: typed {kind} {shown}{hint}")
    for n, name in param_calls(rel, text):
        if lines is None or n in lines:
            if package:
                out.append(f"{rel}:{n}: param('{name}') in a package: a package can't read the parameter files, "
                           "so take the value as an argument and have the calling script pass param()")
            elif name not in pipe and name not in expl:
                out.append(f"{rel}:{n}: param('{name}') is in neither parameter file")
            elif name not in pipe and cls != "explore":
                out.append(f"{rel}:{n}: param('{name}') is an explore parameter; pipeline code uses "
                           f"{kit_params.PIPELINE} only")
    run_all = Path(rel).stem == "run_all"           # the run-all script may keep a small step-runner
    if cls == "pipeline" and not package and not run_all and not kits_reader(rel, text):
        out += [f"{rel}:{n}: defines {name}() in a pipeline script: the paper's code goes in the library, and the "
                "script calls it" for n, name in top_level_definitions(rel, text)
                if (lines is None or n in lines) and name not in ENTRY_POINTS and name not in old_defs]
    return out


def near_copies(texts: dict[str, str], new: dict[str, set[int] | None], old: dict[str, set[str]],
                before: dict[str, str] | None = None) -> list[str]:
    """Findings for the new library functions in `new` (lines None: every function in the file), each against
    its closest match among the library functions in `texts`. A function is new when its definition line is
    added and its file didn't define its name before (`old`), and it didn't just leave its place in the library
    as it was in `before` (moved to another file, or renamed with no other edit). Of two new near copies, only
    the later one is checked, so `# distinct:` goes on that one."""
    funcs = [b for rel, text in sorted(texts.items()) for b in near_copy.bodies(rel, text)]
    here = {(b.file, b.name) for b in funcs}
    gone = [b for rel, text in sorted((before or {}).items()) for b in near_copy.bodies(rel, text)
            if (b.file, b.name) not in here]
    gone_names, gone_tokens = {b.name for b in gone}, {tuple(b.tokens) for b in gone}
    fresh = [b for b in funcs if b.file in new and (new[b.file] is None or b.line in new[b.file])
             and b.name not in old.get(b.file, set()) and b.name not in gone_names
             and tuple(b.tokens) not in gone_tokens]
    order = {id(b): (b.file, b.line) for b in fresh}
    out = []
    for b in fresh:
        others = [o for o in funcs if id(o) not in order or order[id(o)] < order[id(b)]]
        if not b.distinct and (hit := near_copy.matches(b, others)):
            r, o = hit[0]
            out.append(f"{b.file}:{b.line}: {b.name}(){NEAR}{o.name}() ({o.file}:{o.line}), {int(100 * r)}% alike")
    return out


def _blobs(project: Path, names: list[str]) -> dict[str, str]:
    """The text of each git object name (`:path` in the index, `REV:path`), read through one `git cat-file
    --batch`; a name git doesn't have is left out."""
    batch = [n for n in names if "\n" not in n]
    proc = subprocess.run(["git", "-C", str(project), "cat-file", "--batch"], capture_output=True,
                          input=b"".join(os.fsencode(n) + b"\n" for n in batch))
    out, data, pos = {}, proc.stdout, 0
    for n in batch:
        end = data.find(b"\n", pos)
        if end < 0:
            break
        head, pos = data[pos:end].split(b" "), end + 1
        if len(head) == 3 and head[2].isdigit():           # "<id> <type> <size>", then the content
            size = int(head[2])
            if head[1] == b"blob":
                out[n] = data[pos:pos + size].decode("utf-8", "replace")
            pos += size + 1
    for n in names:
        if "\n" in n:                                       # cat-file's batch can't name these
            out[n] = _git_text(project, "show", n)
    return out


def library_then(project: Path, rev: str, library: list[str]) -> list[str]:
    """Today's library entries and those research.yml listed at `rev`, so that a function leaving a file the change
    drops from the library key counts as moved, not new."""
    text = _git_text(project, "show", f"{rev}:{CONFIG_REL.as_posix()}", check=False)
    try:
        old = yaml.safe_load(text) if text else None
    except yaml.YAMLError:
        old = None
    entries = old.get("library") if isinstance(old, dict) else None
    then = {posixpath.normpath(e.strip()) for e in entries if isinstance(e, str) and e.strip()} \
        if isinstance(entries, list) else set()
    return sorted(set(library) | {e for e in then if e != "." and not e.startswith("..")})


def library_texts(project: Path, cfg: dict, library: list[str], rev: str | None) -> dict[str, str]:
    """The library's code files as they are in the working tree (rev None), the index (rev ""), or a commit."""
    if not library:
        return {}
    if rev is None:
        files, ignored = code_files(project, cfg, library)    # ignored library code is library code too
        texts = {rel: (project / rel).read_text(encoding="utf-8", errors="replace") for rel in files + ignored}
    else:
        names = git_names(project, "ls-files", "-z") if rev == "" else \
            git_names(project, "ls-tree", "-r", "-z", "--name-only", rev)
        names = [n for n in names if in_scope(n, cfg) and classify(n, library) == "library"]
        found = _blobs(project, [f"{rev}:{n}" for n in names])      # ":path" is the index
        texts = {n: found[f"{rev}:{n}"] for n in names if f"{rev}:{n}" in found}
    return {rel: t for rel, t in texts.items() if in_scope(rel, cfg) and classify(rel, library) == "library"}


def _hints(pipe: dict, expl: dict) -> dict:
    out = {}
    for entries in (expl, pipe):              # pipeline names win
        for name, (value, _, _) in entries.items():
            for v in value if isinstance(value, list) else [value]:
                if isinstance(v, (int, float, str)) and not isinstance(v, bool):
                    out[v] = name
    return out


def _git_text(project: Path, *args: str, check: bool = True) -> str:
    """git's output decoded leniently, so that a file that isn't UTF-8 can't crash the hook."""
    proc = subprocess.run(["git", "-C", str(project), "-c", "core.quotePath=false", *args], capture_output=True)
    if check and proc.returncode != 0:
        raise KitError(f"git {' '.join(args)} failed in {project}: "
                       f"{proc.stderr.decode('utf-8', 'replace').strip()}")
    return proc.stdout.decode("utf-8", "replace")


def _hunk_lines(diff: str) -> set[int]:
    lines = set()
    for m in HUNK.finditer(diff):
        start, count = int(m.group(1)), int(m.group(2) or "1")
        lines.update(range(start, start + count))
    return lines


def changes(project: Path, against: list[str], only: set[str] | None = None) -> dict[str, tuple[set[int], str]]:
    """{path: (added line numbers, the path it had before)} for the code files that `git diff <against>` shows
    (`--cached` among them for the index). Names come from -z output, so any file name works; a moved file
    counts only its edited lines, because each file is diffed together with the path it moved from."""
    status = _git_text(project, *DIFF, "--name-status", "-z", "--diff-filter=ACMR", *against, "--", *CODE_PATHS)
    fields, out, i = status.split("\0"), {}, 0
    while i < len(fields) and fields[i]:
        kind = fields[i][0]
        paths = fields[i + 1:i + 3] if kind in "RC" else fields[i + 1:i + 2]
        i += 1 + len(paths)
        new = paths[-1]
        if only is None or new in only:
            diff = _git_text(project, *DIFF, *against, "--", *(f":(literal){p}" for p in paths))
            out[new] = (_hunk_lines(diff), paths[0])
    return out


def added_lines(project: Path, against: list[str], only: set[str] | None = None) -> dict[str, set[int]]:
    return {f: lines for f, (lines, _) in changes(project, against, only).items()}


def old_definitions(project: Path, revs: list[str], path: str) -> set[str]:
    """Names a file's earlier versions already define, so that editing an old function's def line passes."""
    names = set()
    for rev in revs:
        proc = subprocess.run(["git", "-C", str(project), "show", f"{rev}:{path}"], capture_output=True)
        if proc.returncode == 0:
            text = proc.stdout.decode("utf-8", "replace")
            names |= {n for _, n in top_level_definitions(path, text)} | {b.name for b in near_copy.bodies(path, text)}
    return names


def staged_lines(project: Path) -> dict[str, tuple[set[int], set[str]]]:
    """The lines the staged commit adds, and the names the file defined before, by file. In a merge, only the
    lines new to both parents count, and a name either parent defined is old."""
    found = changes(project, ["--cached"])
    parents = ["HEAD"]
    if _git_text(project, "rev-parse", "-q", "--verify", "MERGE_HEAD", check=False).strip():
        theirs = changes(project, ["--cached", "MERGE_HEAD"], set(found))
        found = {f: (lines & theirs.get(f, (set(), f))[0], old) for f, (lines, old) in found.items()}
        parents.append("MERGE_HEAD")
    return {f: (lines, old_definitions(project, parents, old)) for f, (lines, old) in found.items()}


def precommit(project: Path) -> list[str]:
    cfg = load_config(project)
    library = library_folders(project, cfg)
    texts = {}
    for rel in (kit_params.PIPELINE, kit_params.EXPLORE):
        in_index = git(project, "ls-files", "-z", "--", rel.as_posix()).strip("\0")
        texts[rel] = _git_text(project, "show", f":{rel.as_posix()}") if in_index else None
    pipe, expl, problems = kit_params.load(project, texts)
    for note in kit_params.foreign(project, texts):
        print(f"note: {note}", file=sys.stderr)
    hints = _hints(pipe, expl)
    out = list(problems)
    staged = staged_lines(project)
    for f, (lines, old) in sorted(staged.items()):
        cls = classify(f, library)
        if lines and in_scope(f, cfg) and cls not in ("test", "archive"):
            out += lint_text(f, _git_text(project, "show", f":{f}"), cls, lines, pipe, expl, hints, old)
    new = {f: lines for f, (lines, _) in staged.items()
           if lines and in_scope(f, cfg) and classify(f, library) == "library"}
    if new:
        head = _git_text(project, "rev-parse", "-q", "--verify", "HEAD^{commit}", check=False).strip()
        out += near_copies(library_texts(project, cfg, library, ""), new,
                           {f: old for f, (_, old) in staged.items()},
                           library_texts(project, cfg, library_then(project, "HEAD", library), "HEAD")
                           if head else None)
    return out


def changed(project: Path, files: list[str], base: str | None = "HEAD") -> list[str]:
    """Findings on the lines of these files that changed since `base`, committed or not, and in the whole of a
    file that base lacks. base None checks the files whole. The parameter files' own problems are left to
    the caller (kit_params.load), so that they are reported once."""
    cfg = load_config(project)
    library = library_folders(project, cfg)
    pipe, expl, _ = kit_params.load(project)
    hints = _hints(pipe, expl)
    out, new, olds = [], {}, {}
    root = project.resolve()
    if base is not None and not git(project, "rev-parse", "--verify", "-q", f"{base}^{{tree}}",
                                    check=False).strip():   # a tree is enough: the review may start at the empty one
        if base != "HEAD":
            raise KitError(f"--base {base} is not a commit or tree in {project}")
        base = None                                   # no commit yet: everything is new
    for f in files:
        p = (Path(f) if Path(f).is_absolute() else root / f).resolve()
        if not p.is_file() or root not in p.parents:
            continue
        rel = p.relative_to(root).as_posix()
        if not in_scope(rel, cfg):
            continue
        tracked = git(project, "ls-files", "-z", "--", f":(literal){rel}").strip("\0")
        # a file new since base shows as wholly added; one unchanged since base isn't in the diff at all
        lines, old = None, set()
        if base is not None and tracked:
            lines, before = changes(project, [base], {rel}).get(rel, (set(), rel))
            old = old_definitions(project, [base], before)
        out += lint_text(rel, p.read_text(encoding="utf-8", errors="replace"), classify(rel, library), lines,
                         pipe, expl, hints, old)
        if classify(rel, library) == "library" and lines != set():
            new[rel], olds[rel] = lines, old
    if new:
        out += near_copies(library_texts(project, cfg, library, None), new, olds,
                           library_texts(project, cfg, library_then(project, base, library), base)
                           if base is not None else None)
    return out


def backlog(project: Path) -> str:
    cfg = load_config(project)
    library = library_folders(project, cfg)
    pipe, expl, problems = kit_params.load(project)
    per_file, kinds = Counter(), Counter()
    found = [line for rel in code_files(project, cfg, library)[0]
             for line in lint_text(rel, (project / rel).read_text(encoding="utf-8", errors="replace"),
                                   classify(rel, library), None, pipe, expl, {})]
    texts = library_texts(project, cfg, library, None)
    found += near_copies(texts, {rel: None for rel in texts}, {})
    for line in found:
        per_file[FINDING.match(line).group(1)] += 1
        kinds[line.split(": typed ", 1)[1].split(" ")[0] if ": typed " in line else
              "function" if " in a pipeline script:" in line else
              "near copy" if NEAR in line else "parameter use"] += 1
    head = (f"code gate backlog: {sum(per_file.values())} findings in "
            f"{len(per_file)} files ({', '.join(f'{k} {n}' for k, n in kinds.most_common()) or 'none'})")
    return "\n".join([head, *problems, *(f"{n:6d}  {f}" for f, n in per_file.most_common())])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", type=Path, required=True)
    mode = ap.add_mutually_exclusive_group(required=True)
    for stream in (sys.stdout, sys.stderr):      # a file name that isn't UTF-8 is shown escaped, not a crash
        getattr(stream, "reconfigure", lambda **_: None)(errors="backslashreplace")
    mode.add_argument("--precommit", action="store_true", help="lint the lines the staged commit adds")
    mode.add_argument("--files", nargs="+", help="lint the lines changed since --base in these files")
    mode.add_argument("--all", nargs="*", metavar="F", help="count every finding by file, or list them in F")
    ap.add_argument("--base", default="HEAD", help="with --files: the commit to compare with (none: whole files)")
    a = ap.parse_args(argv)
    try:
        project = find_project(a.project)
        if a.all == []:
            print(backlog(project))
            return 0
        if not a.precommit:
            for note in kit_params.foreign(project):
                print(f"note: {note}", file=sys.stderr)
        if a.all:
            print("\n".join(changed(project, a.all, base=None)) or "code gate: nothing found")
            return 0
        if a.precommit:
            found = precommit(project)
        else:
            found = kit_params.load(project)[2] + changed(project, a.files, None if a.base == "none" else a.base)
    except KitError as e:
        print(f"lint_code: ERROR: {e}", file=sys.stderr)
        return 2
    if found:
        print("\n".join(found))
        remedy = (f" Move each typed value into {kit_params.PIPELINE} (pipeline) or {kit_params.EXPLORE} (quick "
                  "questions) with a comment saying what it is, or end the line with `# literal: <reason>`."
                  if any(": typed " in f for f in found) else "")
        if any(" in a pipeline script:" in f for f in found):
            has_library = bool(library_folders(project, load_config(project)))
            remedy += (" Move each function into the library (the package, or what library: in "
                       ".claude/research.yml names) and call it from the script." if has_library else
                       " The project has no library yet: name one with library: in .claude/research.yml, or add a "
                       "package, then move each function there.")
        if any(NEAR in f for f in found):
            remedy += (" Merge each near copy into the function it copies, with an argument for what differs, and "
                       "call that; if the two give different results, ask which definition is right first. A real "
                       "difference ends the definition line with `# distinct: <reason>`.")
        print(f"code gate: {len(found)} finding{'s' if len(found) != 1 else ''}.{remedy}", file=sys.stderr)
        return 1
    if not a.precommit:
        print("code gate: nothing found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
