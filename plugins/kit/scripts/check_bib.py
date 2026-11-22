#!/usr/bin/env python3
"""Every \\cite key in the manuscript and slides must exist in a .bib they use; list entries lacking a DOI or URL
(spec §5.3). The manuscript is the paper's lint globs plus everything they \\input or \\include; its .bib
files are the ones it names (\\bibliography, \\addbibresource), else those beside its files.

Exit: 0 ok, 1 missing keys, 2 error.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kitlib import KitError, load_config  # noqa: E402

CITE_RE = re.compile(r"\\[A-Za-z]*cite[A-Za-z]*\*?(?:\[[^\]]*\])*\{([^}]*)\}")
ENTRY_RE = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,")
FIELD_RE = re.compile(r"(?:^|[\s,])(?:doi|url)\s*=", re.IGNORECASE)
NON_ENTRIES = {"comment", "string", "preamble"}
# \input{x}, \include{x}, \subfile{x}, and TeX's braceless \input x
INPUT_RE = re.compile(r"\\(?:input|include|subfile)\s*\{([^}]+)\}|\\input\s+([^\s{}\\%]+)")
# \newcommand, \renewcommand or \providecommand (starred too) with a plain value, such as \papertables in a talk
# made by scaffold.py new-talk
DEF_RE = re.compile(r"\\(?:(?:re)?newcommand|providecommand)\*?\s*\{?\\([A-Za-z]+)\}?\s*\{([^{}\\]*)\}")
BIBRES_RE = re.compile(r"\\(?:bibliography|addbibresource)\s*(?:\[[^\]]*\])?\{([^}]+)\}")


class Manuscript(NamedTuple):
    files: list[Path]       # every file reached, each once
    bibs: set[Path]         # .bib files the files name
    missing_bibs: list[str]  # named .bib files that exist nowhere
    unresolved: list[str]   # \input names that resolve to no file


def strip_comments(text: str) -> str:
    """Cut each line at its first unescaped % (preceded by an even number of backslashes)."""
    out = []
    for line in text.splitlines():
        for m in re.finditer(r"%", line):
            i = m.start()
            n = len(line[:i]) - len(line[:i].rstrip("\\"))
            if n % 2 == 0:
                line = line[:i]
                break
        out.append(line)
    return "\n".join(out)


def read(path: Path) -> str:
    return strip_comments(path.read_text(encoding="utf-8", errors="replace"))


def resolve(name: str, dirs: list[Path], ext: str) -> Path | None:
    """First existing file for a LaTeX file argument, tried with and without its extension."""
    for d in dirs:
        for cand in (d / name, d / f"{name}{ext}"):
            if cand.is_file():
                return cand.resolve()
    return None


def kpsewhich(name: str) -> str | None:
    """Path of a file that comes with the TeX distribution (such as IEEEabrv.bib), or None."""
    if not shutil.which("kpsewhich"):
        return None
    proc = subprocess.run(["kpsewhich", name], capture_output=True, text=True)
    return proc.stdout.strip() or None


def manuscript(repo: Path, globs: list[str]) -> Manuscript:
    """The glob-matched files and every file they \\input or \\include, recursively, with the .bib files
    they name. LaTeX resolves an \\input from the folder of the file being compiled, so each chain is
    resolved from its root file's folder first; a file reached from two roots is read from both.
    Plain path macros (\\papertables) are expanded in \\input names. The walk repeats until the macros
    known for each root folder stop changing, so a macro defined in a file read later still counts."""
    roots = sorted({p.resolve() for g in globs for p in repo.glob(g) if p.is_file()})
    defs: dict[Path, dict[str, str]] = {}  # root folder -> plain macros defined along its chains
    while True:
        before = {k: dict(v) for k, v in defs.items()}
        doc = walk(repo, roots, defs)
        if defs == before:
            return doc


def walk(repo: Path, roots: list[Path], defs: dict[Path, dict[str, str]]) -> Manuscript:
    files, seen, bibs, missing, unresolved = {}, set(), set(), [], []
    stack = [(r, r.parent) for r in reversed(roots)]
    while stack:
        f, root_dir = stack.pop()
        if (f, root_dir) in seen:
            continue
        seen.add((f, root_dir))
        files[f] = None
        text = read(f)
        known = defs.setdefault(root_dir, {})
        known.update(DEF_RE.findall(text))
        dirs = [root_dir, f.parent, repo]
        where = os.path.relpath(f, repo)
        for m in INPUT_RE.finditer(text):
            name = (m.group(1) or m.group(2)).strip()
            expanded = re.sub(r"\\([A-Za-z]+)", lambda d: known.get(d.group(1), d.group(0)), name)
            target = resolve(expanded, dirs, ".tex")
            if target:
                stack.append((target, root_dir))
            else:
                unresolved.append(f"{name} (in {where})")
        for m in BIBRES_RE.finditer(text):
            for name in (n.strip() for n in m.group(1).split(",")):
                if not name or "://" in name:  # remote resources are not checked
                    continue
                bib = resolve(name, dirs, ".bib")
                system = None if bib else kpsewhich(name if name.endswith(".bib") else f"{name}.bib")
                if bib or system:
                    bibs.add(bib or Path(system))
                else:
                    missing.append(f"{name} (named in {where})")
    return Manuscript(list(files), bibs, missing, unresolved)


def cited_keys(files: list[Path]) -> set[str]:
    keys = set()
    for tex in files:
        for m in CITE_RE.finditer(read(tex)):
            keys.update(k.strip() for k in m.group(1).split(",") if k.strip() and k.strip() != "*")
    return keys


def bib_entries(bibs: list[Path]) -> dict[str, bool]:
    """key -> has DOI or URL."""
    entries = {}
    for bib in bibs:
        text = bib.read_text(encoding="utf-8", errors="replace")
        matches = [m for m in ENTRY_RE.finditer(text) if m.group(1).lower() not in NON_ENTRIES]
        for k, m in enumerate(matches):
            end = matches[k + 1].start() if k + 1 < len(matches) else len(text)
            entries[m.group(2)] = bool(FIELD_RE.search(text, m.end(), end))
    return entries


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", type=Path, default=Path.cwd())
    a = ap.parse_args(argv)
    try:
        cfg = load_config(a.project)
        paper = a.project / cfg["paper_dir"]
        paper_globs = cfg["lint"]["paper"]["globs"]
        doc = manuscript(paper, paper_globs) if paper.is_dir() else Manuscript([], set(), [], [])
        if paper.is_dir() and not doc.files:
            raise KitError(f"no files match lint.paper.globs {paper_globs} in {paper}")
        talks = manuscript(a.project, cfg["lint"]["slides"]["globs"])
        if doc.missing_bibs or talks.missing_bibs:
            raise KitError("named .bib not found: " + "; ".join(doc.missing_bibs + talks.missing_bibs))
        # none named: the .bib files beside the manuscript's own files; slides fall back to the paper's
        paper_bibs = doc.bibs or {b.resolve() for f in doc.files for b in f.parent.glob("*.bib")}
        slide_bibs = talks.bibs or paper_bibs
        cited_paper, cited_slides = cited_keys(doc.files), cited_keys(talks.files)
        for name in doc.unresolved + talks.unresolved:
            print(f"check_bib: warning: \\input {name} not found; citations in it are not checked",
                  file=sys.stderr)
        if not paper_bibs and not slide_bibs:
            if cited_paper or cited_slides:
                raise KitError(f"{len(cited_paper | cited_slides)} citation keys but no .bib file named by "
                               f"or beside the manuscript in {paper}")
            print("no citations, no .bib: ok")
            return 0
        if cited_slides and not slide_bibs:
            raise KitError(f"the slides cite {len(cited_slides)} keys but no .bib file is named or found")
        paper_entries, slide_entries = bib_entries(sorted(paper_bibs)), bib_entries(sorted(slide_bibs))
    except KitError as e:
        print(f"check_bib: ERROR: {e}", file=sys.stderr)
        return 2
    used = {**slide_entries, **paper_entries}
    for key in sorted(k for k, ok in used.items() if not ok):
        print(f"no DOI or URL: {key}")
    missing = [f"{k}" for k in sorted(cited_paper - paper_entries.keys())] + \
              [f"{k} (slides)" for k in sorted(cited_slides - slide_entries.keys())]
    for key in missing:
        print(f"missing from .bib: {key}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
