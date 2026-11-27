"""What the pipeline runs, which code reads and writes each data file, and the files the pipeline reads but
doesn't make (frozen results spec). Everything is found by text, not by running code.

The pipeline is the run-all scripts (run_all: in research.yml, or files named run_all.R / run_all.py), the
make_numbers scripts, the library, and every code file reached from those by an invocation or an import.
"""
from __future__ import annotations

import ast
import fnmatch
import re
import warnings
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from code_scan import classify, lines_of, literals, own_path, split_comment

CODE = (".R", ".r", ".py", ".sh")
NUMBERS = {"r": "analysis/numbers/make_numbers.R", "python": "analysis/numbers/make_numbers.py"}
DATA = re.compile(r"\.(csv|tsv|txt|parquet|feather|rds|rda|rdata|dta|xls|xlsx|json|pkl|pickle|sqlite|db|gz|zip|"
                  r"pdf|png|svg|tex|npy|npz|h5|arrow)$", re.I)
SCRIPT = re.compile(r"[\w./*{}()$-]+\.(?:R|r|py|sh)(?![\w.])")
LONG_LINE = 4000         # longer lines are skipped when looking for script names (a minified or data line)
WORD = re.compile(r"[A-Za-z_][\w-]*")
QUOTED = re.compile(r"\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'")
INVOKE = re.compile(r"(?<![\w.])(?:source|sys\.source|system2?|subprocess\.\w+|Popen|runpy\.run_path|exec)\s*\(")
IMPORT = re.compile(r"^\s*(?:from\s+([\w.]+)\s+import\s+\(?\s*([\w\s,]+)|import\s+([\w.]+(?:\s*,\s*[\w.]+)*))")
PARAM = re.compile(r"(?<![\w.])param(?:_path)?\(\s*[\"']([^\"']+)[\"']")
ASSIGN = re.compile(r"^\s*([A-Za-z_.][\w.]*)\s*(?::\s*[\w.\[\], |]+?)?\s*(?:<-|=(?!=)|:=)")
TEMPLATE = re.compile(r"%[-+ 0#]*\d*(?:\.\d+)?[sdifg]|\{[^{}]*\}|\*")
READ = re.compile(r"(?<!\w)(?:read\.csv|read\.table|read\.dta|read_csv|read_tsv|read_delim|fread|readRDS|read_rds|"
                  r"read_parquet|read_feather|read_dta|read_sav|read_excel|open_dataset|readLines|load|"
                  r"read_(?:csv|parquet|feather|stata|excel|pickle|json|table|fwf|spss|hdf|sas|ipc)|"
                  r"np\.load|pickle\.load|json\.load|read_text|read_bytes|fromJSON|read_json|"
                  r"scan_csv|scan_parquet)\s*\(|(?<![\w.])open\((?![^)]*[\"'][wax]b?\+?[\"'])")
WRITE = re.compile(r"(?<![\w.])(?:write\.csv|write\.table|write_csv|write_tsv|write_delim|fwrite|saveRDS|"
                   r"write_rds|save|ggsave|pdf|png|svg|writeLines|sink|write_parquet|write_feather|write_dta|"
                   r"write_xlsx|np\.save|np\.savez|pickle\.dump|json\.dump|write_table|write_ipc|write_json|"
                   r"save_kable|gtsave|shutil\.copy\w*|shutil\.move|copyfile|file\.copy)\s*\(|"
                   r"\.(?:to_csv|to_parquet|to_feather|to_pickle|to_excel|to_stata|to_json|to_latex|savefig|"
                   r"write_text|write_bytes|save)\s*\(|"
                   r"(?<![\w.])cat\([^)]*\bfile\s*=|(?<![\w.])open\([^)]*[\"'][wax]b?\+?[\"']")
CALL = re.compile(r"([\w.$]+)\s*\(")
COPY = re.compile(r"(?<![\w.])(?:shutil\.copy\w*|shutil\.move|copyfile|file\.copy)\s*\(")
# calls that build, test or show a path: a name passed to them isn't being made
NOT_MAKERS = {"Path", "PurePath", "PurePosixPath", "file.path", "os.path.join", "os.path.exists", "exists",
              "os.path.isfile", "file.exists", "dir.exists", "print", "message", "cat", "paste", "paste0",
              "sprintf", "format", "str", "glue", "here", "normalizePath", "basename", "dirname",
              "stopifnot", "assert", "warning", "warn", "stop", "log", "info", "debug", "logging.info",
              "logging.warning", "logger.info", "relative_to", "resolve", "with_name", "with_suffix", "len"}
STATEMENT_LINES = 30     # a call spread over more lines than this is read in pieces


# --- files and the pipeline ------------------------------------------------------------------------------

def code_files(names: list[str], cfg: dict) -> list[str]:
    """The R, Python and shell files among these names that are the project's own, and the run-all files."""
    extra = set(cfg.get("run_all", []))
    return sorted(f for f in names if (f.endswith(CODE) or f in extra) and own_path(f, cfg))


def run_alls(cfg: dict, files: list[str], library: list[str]) -> list[str] | None:
    """The run-all scripts: run_all: in research.yml, or the files named run_all.R or run_all.py that aren't
    tests, explore or archived. None when the project has none."""
    if "run_all" in cfg:
        found = [f for f in cfg["run_all"] if f in set(files)]
    else:
        found = [f for f in files if PurePosixPath(f).name in ("run_all.R", "run_all.py")
                 and classify(f, library) not in ("test", "explore", "archive")]
    return found or None


def is_run_all(rel: str, cfg: dict) -> bool:
    return PurePosixPath(rel).stem == "run_all" or rel in cfg.get("run_all", [])


def _shell_code(line: str) -> str:
    """A shell line without its comment: # at the start of a word (also after ` ; ( |, as in `# note`)."""
    m = re.search(r"(?:^|[\s`;(|])#", line)
    return line[:m.start()] if m else line


def without_docstrings(text: str) -> str:
    """Python source with its docstrings blanked (line numbers kept); the text itself if it doesn't parse."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return text
    lines = text.split("\n")
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) \
                and isinstance(getattr(body[0], "value", None), ast.Constant) and isinstance(body[0].value.value, str):
            d = body[0]
            for i in range(d.lineno - 1, (d.end_lineno or d.lineno)):
                lines[i] = ""
    return "\n".join(lines)


def _code(f: str, line: str, shell: bool = False) -> str:
    return _shell_code(line) if shell or f.endswith(".sh") else split_comment(line)[0]


def _by_path(files: list[str], m: str) -> set[str]:
    pat = re.sub(r"\$(?:\{\w+\}|\(\w+\)|\w+)/", "*/", m).removeprefix("./")
    if "*" in pat:
        return {g for g in files if fnmatch.fnmatch(g, pat) or fnmatch.fnmatch(g, "*/" + pat)}
    return {g for g in files if g == pat or g.endswith("/" + pat)}


def follow(texts: dict[str, str], starts: list[str], library: list[str], numbers: list[str] = (),
           cleaned: bool = False) -> set[str]:
    """The pipeline: the starting scripts, the make_numbers scripts, the library, and every code file they reach.
    cleaned: Python texts already have their docstrings blanked."""
    files = sorted(texts)
    cls = {g: classify(g, library) for g in files}
    stems = defaultdict(set)
    for g in files:
        if not g.endswith(".sh") and cls[g] != "archive":
            stems[PurePosixPath(g).stem].add(g)
    modules = {g.removesuffix(".py").removesuffix("/__init__"): g for g in files if g.endswith(".py")}
    start_set = set(starts)

    def shell_like(f: str) -> bool:
        return f.endswith(".sh") or (f in start_set and not f.endswith((".R", ".r", ".py")))

    def reached(f: str) -> set[str]:
        out = set()
        shell, run_all = shell_like(f), f in start_set
        text = without_docstrings(texts[f]) if f.endswith(".py") and not cleaned else texts[f]
        if shell:
            for line in lines_of(text):
                c = _code(f, line, True)
                for m in (SCRIPT.findall(c) if len(c) < LONG_LINE else []):
                    out |= _by_path(files, m)
                for w in WORD.findall(QUOTED.sub(" ", c)):
                    if len(w) > 3:
                        out |= stems.get(w, set())
            return out - {f}
        for _, c in statements(f, text):
            if (run_all or INVOKE.search(c)) and len(c) < LONG_LINE:
                for m in SCRIPT.findall(c):
                    out |= _by_path(files, m)
            if f.endswith(".py") and (m := IMPORT.match(c)):
                wanted = [m.group(1)] + [f"{m.group(1)}.{n.strip()}" for n in m.group(2).split(",") if n.strip()] \
                    if m.group(1) else [n.strip() for n in m.group(3).split(",")]
                for name in wanted:
                    dotted = name.replace(".", "/")
                    out |= {g for mod, g in modules.items() if mod == dotted or mod.endswith("/" + dotted)}
        return out - {f}

    lib = [f for f in files if cls[f] == "library"]
    run, todo = set(), [f for f in [*starts, *numbers, *lib] if f in texts]
    while todo:
        f = todo.pop()
        if f not in run:
            run.add(f)
            todo += sorted(reached(f) - run)
    return run


# --- reads and writes ------------------------------------------------------------------------------------

def statements(f: str, text: str) -> list[tuple[int, str]]:
    """The file's code as statements: lines joined while a ( or [ is open, with the first line's number."""
    out, cur, start, depth = [], [], 0, 0
    for n, line in enumerate(lines_of(text), 1):
        c = _code(f, line)
        if not cur:
            start = n
        cur.append(c)
        bare = QUOTED.sub("", c)
        depth += sum(ch in "([" for ch in bare) - sum(ch in ")]" for ch in bare)
        if depth <= 0 or len(cur) >= STATEMENT_LINES:
            out.append((start, " ".join(cur)))
            cur, depth = [], 0
    if cur:
        out.append((start, " ".join(cur)))
    return out


def data_name(s: str, root: str | None = None) -> str | None:
    """A string as a data name: templates read as globs, an absolute path inside the project made relative;
    None when it isn't one (no data extension, no real stem, or outside the project)."""
    s = s.strip()
    if not DATA.search(s):
        return None
    if s.startswith("/"):
        if not root or not s.startswith(root.rstrip("/") + "/"):
            return None
        s = s[len(root.rstrip("/")) + 1:]
    s = TEMPLATE.sub("*", s).removeprefix("./")
    stem = PurePosixPath(s).name.rsplit(".", 1)[0].replace("*", "")
    return s if re.search(r"[A-Za-z0-9]", stem) else None


def _span(c: str, open_at: int) -> str:
    """The text inside the parentheses that open at c[open_at]."""
    d = 0
    for j in range(open_at, len(c)):
        d += c[j] == "("
        d -= c[j] == ")"
        if d == 0:
            return c[open_at:j + 1]
    return c[open_at:]


@dataclass
class Uses:
    reads: dict = field(default_factory=lambda: defaultdict(list))     # name -> [line]
    writes: dict = field(default_factory=lambda: defaultdict(list))    # strict
    loose: dict = field(default_factory=lambda: defaultdict(list))     # strict, plus names passed to any call


def _first_arg(span: str) -> str:
    """The first top-level argument inside a call's parentheses (span starts at the "(")."""
    d = 0
    for j, ch in enumerate(span):
        d += ch in "([{"
        d -= ch in ")]}"
        if ch == "," and d == 1:
            return span[1:j]
    return span[1:-1]


def uses(f: str, text: str, params: dict[str, str], root: str | None = None, cleaned: bool = False,
         stmts: list | None = None) -> Uses:
    """The data names one R or Python file reads and writes, with the line each statement starts on.
    cleaned: docstrings already blanked; stmts: the file's statements, when already split."""
    u = Uses()
    if not f.endswith((".R", ".r", ".py")):
        return u
    if stmts is None:
        stmts = statements(f, without_docstrings(text) if f.endswith(".py") and not cleaned else text)

    def direct(c: str) -> set[str]:
        names = {n for s in literals(c) if (n := data_name(s, root))}
        return names | {n for p in PARAM.findall(c) if p in params and (n := data_name(params[p], root))}

    held = defaultdict(set)
    for _, c in stmts:
        if (m := ASSIGN.match(c)) and (names := direct(c)) and not READ.search(c) and not WRITE.search(c):
            held[m.group(1)] |= names
    used = re.compile(r"(?<![\w.])(" + "|".join(re.escape(v) for v in sorted(held, key=len, reverse=True))
                      + r")(?!\w)") if held else None

    def names_in(c: str, assigned: str | None = None) -> set[str]:
        names = direct(c)
        if used:
            for v in set(used.findall(c)) - {assigned}:
                names |= held[v]
        return names

    for n, c in stmts:
        target = (m.group(1) if (m := ASSIGN.match(c)) else None)
        names = names_in(c, target)
        if not names:
            continue
        read = set()
        for m in READ.finditer(c):
            read |= names_in(_span(c, m.end() - 1) if c[m.end() - 1] == "(" else c[m.end() - 1:], target)
        for m in COPY.finditer(c):                   # copy(src, dest): the source is read
            read |= names_in(_first_arg(_span(c, m.end() - 1)), target)
        for name in read:
            u.reads[name].append(n)
        if WRITE.search(c):
            for name in names - read:
                if "*" not in name:              # a template can't be a strict write of one file
                    u.writes[name].append(n)
                u.loose[name].append(n)
        elif not read and not target:            # an assignment only holds its names
            for m in CALL.finditer(c):
                if m.group(1) not in NOT_MAKERS and m.group(1).rsplit(".", 1)[-1] not in NOT_MAKERS:
                    for name in names_in(_span(c, m.end() - 1), target):
                        u.loose[name].append(n)
    for n, c in stmts:                           # a param's name in a string: param_path(key) over a list of keys
        if not READ.search(c):
            for s in set(literals(c)) - set(PARAM.findall(c)):
                if s in params and (name := data_name(params[s], root)):
                    u.loose[name].append(n)
    for name in list(u.loose):                   # a file doesn't make what it reads, unless it writes it
        if name not in u.writes and any(same(name, r) for r in u.reads):
            del u.loose[name]
    return u


def same(a: str, b: str) -> bool:
    """Two data names name the same file: equal, or one ends with "/" plus the other; globs match as globs."""
    a, b = a.removeprefix("./"), b.removeprefix("./")
    if "*" in a or "*" in b:
        return any(fnmatch.fnmatchcase(x, y) or fnmatch.fnmatchcase(x, "*/" + y)
                   for x, y in ((a, b), (b, a)) if "*" in y)
    return a == b or a.endswith("/" + b) or b.endswith("/" + a)


# --- what the pipeline reads but doesn't make ------------------------------------------------------------

@dataclass
class Unmade:
    name: str
    readers: list     # [(file, line)]
    writers: list     # [(file, line)]


@dataclass
class Graph:
    run: set
    uses: dict        # file -> Uses
    cls: dict         # file -> class
    stmts: dict       # file -> statements (R and Python files)


def graph(texts: dict[str, str], starts: list[str], library: list[str], params: dict[str, str],
          numbers: list[str] = (), root: str | None = None, only_run: bool = False) -> Graph:
    """The pipeline and every file's reads and writes (only_run: just the pipeline's files)."""
    clean = {f: without_docstrings(t) if f.endswith(".py") else t for f, t in texts.items()}
    run = follow(clean, starts, library, numbers, cleaned=True)
    keep = [f for f in clean if f.endswith((".R", ".r", ".py")) and (not only_run or f in run)]
    stmts = {f: statements(f, clean[f]) for f in keep}
    return Graph(run, {f: uses(f, clean[f], params, root, True, stmts[f]) for f in keep},
                 {f: classify(f, library) for f in texts}, stmts)


def readers_of(g: Graph) -> dict[str, list]:
    """Data name -> [(file, line)] read by pipeline files that aren't tests, explore or archived."""
    out = defaultdict(list)
    for f in g.run:
        if g.cls[f] not in ("test", "explore", "archive") and f in g.uses:
            for name, lines in g.uses[f].reads.items():
                out[name] += [(f, n) for n in lines]
    return out


def made_by_pipeline(g: Graph, name: str) -> list:
    """(file, line) where a pipeline file that isn't archived writes this name (loose). A reached file named like
    a test (run_x_test.py) counts: being generous here only removes findings."""
    return sorted((f, n) for f in g.run if g.cls[f] != "archive" and f in g.uses
                  for m, lines in g.uses[f].loose.items() if same(m, name) for n in lines)


def strict_writers(g: Graph, name: str) -> list:
    return sorted((f, n) for f, u in g.uses.items() for m, lines in u.writes.items() if same(m, name)
                  for n in lines)


def unmade(g: Graph, frozen_paths: list[str]) -> list[Unmade]:
    """Files the pipeline reads, that some code file writes, that no pipeline file writes, and that frozen.yml
    doesn't declare; same-file names merged into the longest."""
    out = []
    for name, at in readers_of(g).items():
        if any(same(name, fz) for fz in frozen_paths) or made_by_pipeline(g, name):
            continue
        ws = strict_writers(g, name)
        if ws:
            out.append(Unmade(name, sorted(set(at)), ws))
    return merged(out)


def merged(items: list[Unmade]) -> list[Unmade]:
    out: list[Unmade] = []
    for x in sorted(items, key=lambda x: (-len(x.name), x.name)):
        hit = next((o for o in out if same(o.name, x.name)), None)
        if hit:
            hit.readers = sorted(set(hit.readers) | set(x.readers))
            hit.writers = sorted(set(hit.writers) | set(x.writers))
        else:
            out.append(Unmade(x.name, list(x.readers), list(x.writers)))
    return sorted(out, key=lambda x: x.name)


# --- the paper's files -----------------------------------------------------------------------------------

def paper_unmade(project: Path, cfg: dict, texts: dict[str, str], g: Graph) -> list[Unmade]:
    """Files in the paper's tables/ and figures/ that the manuscript names and no pipeline file names; their
    writers are the files outside the pipeline that name them (empty: none does)."""
    from kitlib import paper_folders
    paper = (project / cfg["paper_dir"]).resolve()
    if not paper.is_dir():
        return []
    root = project.resolve()
    *_, figures, tables = paper_folders(project, cfg, paper)
    outputs = [p for d in (figures, tables) if d.is_dir() for p in sorted(d.iterdir())
               if p.is_file() and not p.name.startswith(".")]
    if not outputs:
        return []
    manuscript = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in sorted(paper.rglob("*.tex"))
                           if figures not in p.parents and tables not in p.parents and ".git" not in p.parts)
    out = []
    for p in outputs:
        if not re.search(r"(?<![\w-])" + re.escape(p.stem) + r"(?![\w-])", manuscript):
            continue
        quoted = re.compile(r"[\"'](?:[^\"'\n]*/)?" + re.escape(p.stem) + r"(?:\.\w+)?[\"']")
        named = sorted((f, n) for f, st in g.stmts.items() for n, c in st if quoted.search(c))
        if any(f in g.run and g.cls[f] not in ("test", "archive") for f, _ in named):
            continue
        out.append(Unmade(p.relative_to(root).as_posix(), [("paper", 0)], named))
    return out


# --- for the printed fix ---------------------------------------------------------------------------------

def resolve(project: Path, reader: str, name: str) -> str:
    """The name as a project path: tried from the folder of the file that names it and each folder above it."""
    root = project.resolve()
    folder = PurePosixPath(reader).parent
    for d in [folder, *folder.parents]:
        cand = (root / d / name).resolve()
        if root in cand.parents and cand.is_file():
            return cand.relative_to(root).as_posix()
    return name
