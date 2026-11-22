#!/usr/bin/env python3
"""Leak check for a public export of research-kit (shareable-kit spec §1).

Usage: leak_check.py <tree> [--terms FILE]

Scans every file under <tree> except .git/, by content and by path name, for:
- private paths and dated lesson tags (FIXED);
- the account name, read from .claude-plugin/marketplace.json, outside ACCOUNT_ALLOWED;
- the terms in FILE (UTF-8, a byte-order mark allowed; one per line; blank lines and # comments skipped).
Matching folds case and compatibility forms on both sides (NFKC, then casefold), so "straße" matches "STRASSE".
A file that is not UTF-8 can't be checked, so it is a hit; a symlink is checked by its link text. A folder that
can't be read is an error, not skipped. Exit 0 clean, 1 with one line per hit on stdout, 2 usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import unicodedata
from pathlib import Path

FIXED = ("/" + "projects/", "/" + "home/", "(user" + ", 20")  # built from parts, so this file passes its own check
ACCOUNT_ALLOWED = frozenset({"README.md", "LICENSE", ".claude-plugin/marketplace.json",
                             "plugins/kit/.claude-plugin/plugin.json"})


class UsageError(Exception):
    pass


def account_name(tree: Path) -> str:
    mp = tree / ".claude-plugin" / "marketplace.json"
    try:
        name = json.loads(mp.read_text(encoding="utf-8"))["owner"]["name"]
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise UsageError(f"{mp}: cannot read owner.name ({type(e).__name__}: {e})") from e
    if not isinstance(name, str) or not name.strip():
        raise UsageError(f"{mp}: owner.name is empty")
    return name.strip()


def fold(s: str) -> str:
    return unicodedata.normalize("NFKC", s).casefold()


def read_terms(path: Path) -> list[str]:
    lines = (line.strip() for line in path.read_text(encoding="utf-8-sig").splitlines())
    return [t for t in lines if t and not t.startswith("#")]


def _raise(e: OSError) -> None:
    raise e


def tree_files(tree: Path) -> list[str]:
    """Every file under tree except .git/. A symlinked folder is listed as an entry (its target is scanned as
    text) and not entered."""
    out = []
    for dirpath, dirnames, filenames in os.walk(tree, onerror=_raise):
        d = Path(dirpath)
        links = [n for n in dirnames if (d / n).is_symlink()]
        dirnames[:] = [n for n in dirnames if n != ".git" and n not in links]
        out += [(d / f).relative_to(tree).as_posix() for f in filenames + links]
    return sorted(out)


def scan(tree: Path, terms: list[str] | tuple[str, ...] = (), files: list[str] | None = None) -> list[str]:
    """One 'path:line: term' (or 'path: path contains term', or 'path: not UTF-8 ...') per hit. files limits
    the scan to those paths."""
    account = account_name(tree)
    checks = [(p, frozenset()) for p in FIXED] + [(account, ACCOUNT_ALLOWED)] + [(t, frozenset()) for t in terms]
    hits = []
    for rel in sorted(files) if files is not None else tree_files(tree):
        p = tree / rel
        raw = os.readlink(p).encode() if p.is_symlink() else p.read_bytes()
        try:
            lines = [fold(line) for line in raw.decode("utf-8").splitlines()]
        except UnicodeDecodeError:
            hits.append(f"{rel}: not UTF-8 text, so it can't be checked")
            lines = []
        name = fold(rel)
        for needle, allowed in checks:
            if rel in allowed:
                continue
            n = fold(needle)
            hits += [f"{rel}:{i}: {needle!r}" for i, line in enumerate(lines, 1) if n in line]
            if n in name:
                hits.append(f"{rel}: path contains {needle!r}")
    return hits


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Scan a tree for private names before a public export.")
    ap.add_argument("tree", type=Path)
    ap.add_argument("--terms", type=Path, help="private terms, one per line")
    a = ap.parse_args(argv)
    try:
        if not a.tree.is_dir():
            raise UsageError(f"{a.tree}: not a folder")
        hits = scan(a.tree, read_terms(a.terms) if a.terms else ())
    except (UsageError, OSError, UnicodeDecodeError) as e:
        print(f"leak_check: {e}", file=sys.stderr)
        return 2
    for h in hits:
        print(h)
    print(f"leak check: {len(hits)} hit(s)" if hits else "leak check: clean", file=sys.stderr)
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
