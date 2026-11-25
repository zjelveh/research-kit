#!/usr/bin/env python3
"""Map a project's shared code and parameters, and where scripts go around them (code spec section 4).

  code_map.py --project P                the map: the summary, the library's functions and the parameters
  code_map.py --project P --files F ... [--base REV]
                                         the checks on these files: typed values on the lines changed
                                         since REV (default HEAD; none: whole files), repeats, paper
                                         outputs with several writers, and direct reads of the library's data
  code_map.py --project P --all          every list for the whole project

Caller counts, parameter users and writers are found by text, not by running the code. Nothing is saved.
Exit: 0 report printed, 2 config or project error.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit_params  # noqa: E402
import lint_code  # noqa: E402
from code_scan import (CODE_SUFFIXES, ENTRY_POINTS, classify, code_files, kits_reader, library_folders,  # noqa: E402
                       literals, parse_python, py_functions, r_functions, split_comment)
from kitlib import CONFIG_REL, KitError, find_project, load_config, paper_folders  # noqa: E402

REPEAT_LINES = 6
CALL = re.compile(r"([A-Za-z_.][\w.]*)\s*\(")
TRIVIAL = re.compile(r"[\s{}()\[\],;]*")
DATA_EXT = re.compile(r"\.(csv|tsv|txt|parquet|feather|rds|rda|rdata|dta|xls|xlsx|json|pkl|pickle|sqlite|db|gz|"
                      r"zip)$", re.I)
READER = re.compile(r"(?<![\w.])(?:read\.csv|read\.table|read\.dta|read_csv|read_tsv|read_delim|fread|readRDS|"
                    r"read_rds|read_parquet|read_feather|read_dta|read_sav|read_excel|open_dataset|"
                    r"(?:pd\.|pandas\.)?read_(?:csv|parquet|feather|stata|excel|pickle|json|table|fwf|spss|hdf|sas)|"
                    r"pq\.read_table|np\.load|pickle\.load)\s*\(")


def significant(lines: list[str]) -> list[tuple[int, str]]:
    out = []
    for n, line in enumerate(lines, 1):
        s = line.strip()
        if s and not s.startswith("#") and not TRIVIAL.fullmatch(s):
            out.append((n, re.sub(r"\s+", " ", s)))
    return out


def _pair_runs(windows: dict, keep) -> list:
    """Pairs of matching runs of windows: ((file, first, last), (file, first, last)), for the pairs of
    locations that `keep` accepts. Windows that overlap themselves within one file are left out."""
    diagonals = defaultdict(set)
    for locs in windows.values():
        locs = sorted(set(locs))
        for i in range(len(locs)):
            for j in range(i + 1, len(locs)):
                (fa, ka), (fb, kb) = locs[i], locs[j]
                if keep(fa, fb) and not (fa == fb and kb - ka < REPEAT_LINES):
                    diagonals[(fa, fb, kb - ka)].add(ka)
    out = []
    for (fa, fb, off), ks in diagonals.items():
        ks = sorted(ks)
        start = prev = ks[0]
        for k in ks[1:] + [None]:
            if k is not None and k == prev + 1:
                prev = k
                continue
            out.append(((fa, start, prev), (fb, start + off, prev + off)))
            if k is not None:
                start = prev = k
    return out


def _clusters(pairs: list) -> list[set]:
    """Groups runs that share an identical span into one repeated block."""
    parent = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a, b in pairs:
        parent[find(a)] = find(b)
    groups = defaultdict(set)
    for x in parent:
        groups[find(x)].add(x)
    return list(groups.values())


def block_repeats(sigs: dict[str, list[tuple[int, str]]], classes: dict[str, str]) -> tuple[list[dict], int]:
    windows = defaultdict(list)
    for f, sig in sigs.items():
        for k in range(len(sig) - REPEAT_LINES + 1):
            chunk = "\n".join(s for _, s in sig[k:k + REPEAT_LINES])
            windows[hashlib.sha1(chunk.encode()).hexdigest()].append((f, k))
    windows = {h: locs for h, locs in windows.items() if len(locs) > 1}
    live = _pair_runs(windows, lambda a, b: classes[a] != "archive" and classes[b] != "archive")
    archived = _pair_runs(windows, lambda a, b: classes[a] == "archive" or classes[b] == "archive")
    blocks = []
    for group in _clusters(live):
        spans = sorted((f, sigs[f][a][0], sigs[f][z + REPEAT_LINES - 1][0]) for f, a, z in group)
        blocks.append({"spans": spans, "size": max(z - a for _, a, z in group) + REPEAT_LINES,
                       "classes": {classes[f] for f, _, _ in spans}})
    blocks.sort(key=lambda b: (not ({"library", "pipeline"} & b["classes"]), -b["size"], b["spans"]))
    return blocks, len(_clusters(archived))


def output_writers(project: Path, cfg: dict, lits: dict[str, list[tuple[int, str]]], params: dict,
                   users: dict) -> dict | None:
    """Paper figures and tables whose name appears in two or more files: as a string literal, or as the value
    of a parameter those files read."""
    paper = (project / cfg["paper_dir"]).resolve()
    if not paper.is_dir():
        return None
    *_, figures, tables = paper_folders(project, cfg, paper)
    tails = {f: {t for _, s in found for t in (s, s.rsplit("/", 1)[-1])} for f, found in lits.items()}
    named = [(name, v.rsplit("/", 1)[-1]) for name, (v, *_) in params.items() if isinstance(v, str)]
    out = {}
    for d in (figures, tables):
        for p in sorted(d.iterdir()) if d.is_dir() else []:
            if p.is_file() and not p.name.startswith("."):
                who = {f for f, t in tails.items() if p.name in t or p.stem in t}
                who |= {f for name, tail in named if tail in (p.name, p.stem) for f in users.get(name, ())}
                if len(who) > 1:
                    out[p.relative_to(paper).as_posix()] = sorted(who)
    return out


def build(project: Path) -> dict:
    cfg = load_config(project)
    library = library_folders(project, cfg)
    files, ignored = code_files(project, cfg, library)
    classes = {f: classify(f, library) for f in files}
    pipe, expl, param_problems = kit_params.load(project)
    data_params = {n for n, (v, _, _) in pipe.items() if isinstance(v, str) and DATA_EXT.search(v)}
    funcs, outside, unparsed = [], {}, []
    calls, lits, sigs, defs = defaultdict(set), {}, {}, defaultdict(set)
    users, reads, passed, loader_files = defaultdict(set), [], [], set()
    for f in files:
        cls = classes[f]
        if cls == "test":
            continue
        text = (project / f).read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        if f.endswith(".py"):
            tree = parse_python(text)
            if tree is None:
                unparsed.append(f)
            fs = py_functions(f, tree) if tree is not None else []
        else:
            fs = r_functions(f, lines)
        sigs[f] = significant(lines)
        if cls == "archive":
            continue
        if kits_reader(f, text):
            fs = []                           # the kit's param() reader; a project's own file of that name is code
        if cls == "library":
            funcs += fs
        else:
            names = [x.name for x in fs if x.name not in ENTRY_POINTS]
            if names:
                outside[f] = names
        for x in fs:
            if x.name not in ENTRY_POINTS:
                defs[x.name].add(f)
        code_lines = [split_comment(line)[0] for line in lines]
        lits[f] = [(n, s) for n, c in enumerate(code_lines, 1) for s in literals(c)]
        by_line = defaultdict(set)
        for n, name in lint_code.param_calls(f, text):
            by_line[n].add(name)
            users[name].add(f)
        for n, c in enumerate(code_lines, 1):
            names = {x for name in CALL.findall(c) for x in (name, name.rsplit(".", 1)[-1])}
            calls[f].update(names)
            if cls == "library" and READER.search(c):
                loader_files.add(f)
            if cls != "library" and by_line[n] & data_params:
                passed.append((names, by_line[n] & data_params))
            if cls != "library" and READER.search(c) and (hit := sorted(by_line[n] & data_params)):
                reads.append((f, n, hit))     # kept below only for data the library itself loads
    callers = {fn.name: sum(1 for f in calls if f != fn.file and fn.name in calls[f]) for fn in funcs}
    # the library's data: what it reads with param(), or what scripts pass to its loaders (a package can't
    # call param(), so its loaders take the path as an argument); a helper that only writes doesn't count
    library_names = {fn.name for fn in funcs if fn.file in loader_files}
    library_data = {n for n in data_params if any(classes[f] == "library" for f in users[n])}
    library_data |= {n for names, used in passed if names & library_names for n in used}
    reads = [(f, n, hit) for f, n, names in reads if (hit := sorted(set(names) & library_data))]
    name_repeats = sorted(((n, sorted(fs)) for n, fs in defs.items() if len(fs) > 1),
                          key=lambda x: (not ({"library", "pipeline"} & {classes[f] for f in x[1]}), x[0]))
    blocks, archive_repeats = block_repeats(sigs, classes)
    params = {**{n: (*v, "pipeline") for n, v in pipe.items()}, **{n: (*v, "explore") for n, v in expl.items()}}
    return {"library": library, "ignored": ignored, "classes": classes, "funcs": funcs, "callers": callers,
            "params": params,
            "param_problems": param_problems, "foreign": kit_params.foreign(project), "users": users,
            "outside": outside,
            "name_repeats": name_repeats, "blocks": blocks, "archive_repeats": archive_repeats,
            "writers": output_writers(project, cfg, lits, params, users), "reads": reads, "unparsed": unparsed}


def _n(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def summary(m: dict) -> list[str]:
    core = lambda classes: bool({"library", "pipeline"} & set(classes))  # noqa: E731
    pipe_rep = sum(core({m["classes"][f] for f in fs}) for _, fs in m["name_repeats"]) + \
        sum(core(b["classes"]) for b in m["blocks"])
    all_rep = len(m["name_repeats"]) + len(m["blocks"])
    writers = m["writers"]
    unused = sum(1 for n in m["params"] if not m["users"].get(n))
    parts = [f"{_n(len(m['funcs']), 'library function')} "
             f"({sum(1 for f in m['funcs'] if m['callers'][f.name] == 0)} with no callers)",
             f"{_n(len(m['params']), 'parameter')} ({unused} unused)",
             f"{_n(sum(len(v) for v in m['outside'].values()), 'function')} outside the library",
             f"{_n(pipe_rep, 'repeat')} in pipeline code ({all_rep - pipe_rep} in explore, "
             f"{m['archive_repeats']} with archive copies)",
             "paper not attached" if writers is None else f"{_n(len(writers), 'output')} with several writers",
             f"{_n(len(m['reads']), 'direct read')} of library data"]
    lines = [f"code map: {', '.join(parts)}; library: {', '.join(m['library']) or 'none'}"]
    if m["ignored"]:
        lines.append(f"warning: git ignores {_n(len(m['ignored']), 'library code file')}: "
                     f"{', '.join(m['ignored'][:5])}{' ...' if len(m['ignored']) > 5 else ''}")
    lines += [f"warning: {p}" for p in m["param_problems"] + m["foreign"]]
    if m["unparsed"]:
        lines.append(f"note: {_n(len(m['unparsed']), 'Python file')} could not be parsed: "
                     f"{', '.join(m['unparsed'][:5])}{' ...' if len(m['unparsed']) > 5 else ''}")
    return lines


def _shown(value) -> str:
    return "[" + ", ".join(_shown(v) for v in value) + "]" if isinstance(value, list) else \
        f"{value:g}" if isinstance(value, float) else repr(value)


def report(m: dict, mode: str = "map", only: set[str] | None = None, typed: list[str] | None = None) -> str:
    """mode "map": the summary, the library and the parameters; "files": the checks, limited to `only`;
    "all": everything."""
    out = summary(m)
    if mode in ("map", "all"):
        out += ["", "## Library functions (callers counted by text)"]
        if not m["library"]:
            out.append("no library: name shared-code folders or files in research.yml's library key, or add a package")
        for f in m["funcs"]:
            out.append(f"{f.name}({f.args})  {f.file}:{f.line}  callers: {m['callers'][f.name]}  "
                       f"{f.desc or '(no description)'}")
        out += ["", f"## Parameters ({kit_params.PIPELINE} and {kit_params.EXPLORE}; read with param())"]
        if not m["params"]:
            out.append("none yet")
        for name, (value, line, about, where) in m["params"].items():
            used = sorted(m["users"].get(name, ()))
            out.append(f"{name} = {_shown(value)}  {where}:{line}  used in {len(used)}"
                       f"{': ' + ', '.join(used[:3]) + (' ...' if len(used) > 3 else '') if used else ''}  {about}")
    if mode == "map":
        out += ["", "Run with --files <changed files> to check new code, or --all for every list."]
        return "\n".join(out)
    if mode == "all":
        out += ["", "## Functions outside the library"]
        out += [f"{f}: {', '.join(names)}" for f, names in sorted(m["outside"].items())]
    keep = (lambda fs: True) if only is None else (lambda fs: bool(only & set(fs)))  # noqa: E731
    if typed is not None:
        out += ["", "## Code check (lint_code.py: typed numbers, dates and paths; functions in pipeline scripts)"]
        out += typed or ["none"]
    out += ["", "## Repeats"]
    out += [f"{name} defined in {', '.join(fs)}" for name, fs in m["name_repeats"] if keep(fs)]
    out += [f"{b['size']} lines: {', '.join(f'{f}:{a}-{z}' for f, a, z in b['spans'])}"
            for b in m["blocks"] if keep([f for f, _, _ in b["spans"]])]
    out += ["", "## Paper outputs with several writers (names found in strings and parameters)"]
    if m["writers"] is None:
        out.append("paper not attached")
    else:
        out += [f"{o}: {', '.join(ws)}" for o, ws in m["writers"].items() if keep(ws)]
    out += ["", "## Direct reads of the library's data (load it through a library function instead)"]
    out += [f"{f}:{n}  reads {', '.join(names)}" for f, n, names in m["reads"] if keep([f])]
    return "\n".join(out)


def relative_files(project: Path, files: list[str]) -> set[str]:
    root, out = project.resolve(), set()
    for f in files:
        p = Path(f)
        p = (p if p.is_absolute() else root / p).resolve()
        if p.is_file() and root in p.parents:
            out.add(p.relative_to(root).as_posix())
    return out


def files_report(project: Path, files: list[str], base: str | None = "HEAD") -> str:
    """The checks on these files; typed values on the lines changed since base (None: the whole files)."""
    only = relative_files(project, files)
    return report(build(project), "files", only, lint_code.changed(project, sorted(only), base))


def review_section(project: Path, files: list[str], base: str = "HEAD") -> str:
    """The checks on the changed files since the review's start, for /kit:review's brief. Never raises: the
    review goes on."""
    project = Path(project)
    if not (project / CONFIG_REL).is_file():
        return "not a kit project"
    try:
        text = files_report(project, files, base)
    except Exception as e:  # noqa: BLE001 - any failure here must leave the review running
        return f"code map unavailable: {e}"
    return text.replace("\n## ", "\n### ")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", type=Path, required=True)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--files", nargs="+", help="check these files (relative to the project): typed values, "
                                                 "repeats, writers and direct reads")
    mode.add_argument("--all", action="store_true", help="every list, for the whole project")
    ap.add_argument("--base", default="HEAD", help="with --files: the commit typed values are compared with "
                                                   "(none: the whole files)")
    a = ap.parse_args(argv)
    try:
        project = find_project(a.project)
        if a.files:
            print(files_report(project, a.files, None if a.base == "none" else a.base))
        elif a.all:
            print(report(build(project), "all", typed=[lint_code.backlog(project).splitlines()[0]]))
        else:
            print(report(build(project), "map"))
        return 0
    except KitError as e:
        print(f"code_map: ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
