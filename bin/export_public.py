#!/usr/bin/env python3
"""Export a public release of research-kit into a separate git repo (shareable-kit spec §4).

Usage: export_public.py <public repo> -m <commit message>

Takes this repo's committed HEAD (never uncommitted changes) into a temporary folder and leaves out EXCLUDE.
It runs the leak check on that folder and on the commit message, with the terms in private/leak_terms.txt when
that file exists (a file holding no terms is refused), and stops on any hit before writing anything. The public
repo must be clean, untracked files included, must not share history with this repo (any of its root commits)
and must not be a shallow clone (which can hide shared history). The release tree is written from exactly the
checked files, byte for byte: each is hashed raw into a throwaway index, bypassing git's filters, line-ending
conversion and attributes, and every blob of the tree is checked against the checked bytes, so nothing in the
public repo (its files, its ignore rules, its config, its attributes) can add to it or change it. A release that
changes plugins/kit without a new version in plugin.json is refused, because installed copies update only when
the version changes. So is one that puts a path where the public repo has an ignored file (the same path, or one
inside the other), because the reset would overwrite or delete that file. The commit is made with git
commit-tree (no hooks run), HEAD moves to it only from the value read before, and the public repo's index and
files are reset to it; its other ignored files stay. If the reset fails after HEAD moved, it says how to finish
by hand. It never pushes. Exit 0 committed or nothing to release, 1 leak check failed, 2 refused or failed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import leak_check  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE = ("docs", "private", "bin/measure_hook_limit.py")
TERMS = "private/leak_terms.txt"
PLUGIN_DIR = "plugins/kit"
PLUGIN_JSON = "plugins/kit/.claude-plugin/plugin.json"


class Refused(Exception):
    pass


def run_git(repo: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env=env)


def git(repo: Path, *args: str, env: dict | None = None) -> str:
    r = run_git(repo, *args, env=env)
    if r.returncode:
        raise Refused(f"git {' '.join(args)} in {repo} failed: {r.stderr.strip()}")
    return r.stdout


def excluded(rel: str) -> bool:
    return any(rel == e or rel.startswith(e + "/") for e in EXCLUDE)


def stage(src: Path, dst: Path) -> None:
    """src's HEAD into dst, file modes kept, without the excluded paths."""
    tar = subprocess.run(["git", "-C", str(src), "archive", "--format=tar", "HEAD"], capture_output=True, check=True)
    subprocess.run(["tar", "-x", "-C", str(dst)], input=tar.stdout, check=True)
    for e in EXCLUDE:
        p = dst / e
        if p.is_dir() and not p.is_symlink():
            shutil.rmtree(p)
        elif p.exists() or p.is_symlink():
            p.unlink()
        prune_empty(p.parent, dst)


def prune_empty(d: Path, stop: Path) -> None:
    while d != stop and d.is_dir() and not any(d.iterdir()):
        d.rmdir()
        d = d.parent


def version(text: str, where: str) -> str:
    try:
        v = json.loads(text)["version"]
    except (ValueError, KeyError, TypeError) as e:
        raise Refused(f"{where}: cannot read version ({type(e).__name__}: {e})") from e
    if not isinstance(v, str) or not v.strip():
        raise Refused(f"{where}: version must be a non-empty string")
    return v


def load_terms(src: Path) -> tuple[str, ...]:
    file = src / TERMS
    if not file.exists() and not file.is_symlink():  # a broken link is an error, not a missing file
        print(f"export_public: no {TERMS}; checking fixed patterns and the account name only", file=sys.stderr)
        return ()
    terms = tuple(leak_check.read_terms(file))
    if not terms:
        raise Refused(f"{file} has no terms; add the private names or delete the file")
    print(f"export_public: {len(terms)} private terms from {TERMS}", file=sys.stderr)
    return terms


def message_hits(message: str, terms: tuple[str, ...]) -> list[str]:
    m = leak_check.fold(message)
    return [f"commit message: {n!r}" for n in (*leak_check.FIXED, *terms) if leak_check.fold(n) in m]


def check_repos(pub: Path, src: Path) -> None:
    if git(src, "status", "--porcelain"):
        raise Refused(f"{src} has uncommitted changes; the export takes HEAD, so commit first")
    top = run_git(pub, "rev-parse", "--show-toplevel") if pub.is_dir() else None
    if top is None or top.returncode or Path(top.stdout.strip()).resolve() != pub:
        raise Refused(f"{pub} is not the top folder of a git repo; create it with: git init -b main {pub}")
    if pub == src or src in pub.parents or pub in src.parents:
        raise Refused(f"the public repo {pub} must be outside {src}")
    if git(pub, "status", "--porcelain", "--untracked-files=all"):
        raise Refused(f"{pub} has uncommitted changes")
    # A clone or a worktree of src holds one of src's root commits (of any branch); committing there would publish
    # the private history.
    for root in git(src, "rev-list", "--max-parents=0", "--all").split():
        if run_git(pub, "cat-file", "-e", f"{root}^{{commit}}").returncode == 0:
            raise Refused(f"{pub} shares history with {src} (commit {root[:12]}); a public repo needs its own "
                          "history: git init -b main <new folder>")
    # A shallow clone of src lacks the root commit, yet its HEAD is one of src's commits.
    if git(pub, "rev-parse", "--is-shallow-repository").strip() == "true":
        raise Refused(f"{pub} is a shallow clone, so its history can't be checked against {src}; a public repo "
                      "needs its own history: git init -b main <new folder>")


def raw(p: Path) -> bytes:
    """The bytes a release holds for p: a symlink's link text, else the file's contents."""
    return os.fsencode(os.readlink(p)) if p.is_symlink() else p.read_bytes()


def blob_id(data: bytes, algo: str) -> str:
    """The id git gives a blob of exactly these bytes."""
    return hashlib.new(algo, b"blob %d\0" % len(data) + data).hexdigest()


def stage_tree(pub: Path, staging: Path, files: list[str], tmp: Path) -> str:
    """Write files (staging's files, as checked) byte for byte as a tree in pub's object store and return its id.
    Each blob is hashed with --no-filters and entered with its mode into a throwaway index, so pub's index, files,
    ignore rules, filters, attributes and line-ending settings play no part. Paths are given as arguments, not
    on stdin lines, so no name is read differently. Run from inside staging (the paths are relative to it)."""
    env = {**os.environ, "GIT_INDEX_FILE": str(tmp / "index")}
    base = ["git", "--git-dir", git(pub, "rev-parse", "--absolute-git-dir").strip(), "--work-tree", str(staging)]

    def g(*args: str, data: bytes | None = None) -> str:
        r = subprocess.run([*base, *args], cwd=staging, input=data, capture_output=True, env=env)
        if r.returncode:
            raise Refused(f"git {' '.join(args[:3])} against {pub} failed: {r.stderr.decode(errors='replace').strip()}")
        return r.stdout.decode()

    links = {f for f in files if (staging / f).is_symlink()}
    regular = [f for f in files if f not in links]
    ids = {f: g("hash-object", "-w", "--no-filters", "--stdin", data=raw(staging / f)).strip() for f in links}
    for i in range(0, len(regular), 500):  # in batches, within the limit on argument length
        batch = regular[i:i + 500]
        ids.update(zip(batch, g("hash-object", "-w", "--no-filters", "--", *batch).split()))
    if sorted(ids) != files:
        raise Refused("git hash-object did not return an id for every file")
    modes = {f: "120000" if f in links else "100755" if os.lstat(staging / f).st_mode & stat.S_IXUSR else "100644"
             for f in files}
    entries = b"".join(b"%s %s\t%s\0" % (modes[f].encode(), ids[f].encode(), os.fsencode(f)) for f in files)
    g("update-index", "-z", "--index-info", data=entries)
    tree = g("write-tree").strip()
    algo = "sha1" if len(tree) == 40 else "sha256"
    listed = {}
    for entry in filter(None, git(pub, "ls-tree", "-r", "-z", tree).split("\0")):
        meta, name = entry.split("\t", 1)
        listed[name] = meta.split()[2]
    if sorted(listed) != files:
        raise Refused("the release tree differs from the checked files")
    changed = [f for f in files if listed[f] != blob_id(raw(staging / f), algo)]
    if changed:
        raise Refused(f"the release tree holds other bytes than the checked files: {', '.join(changed)}")
    return tree


def parents(rel: str) -> list[str]:
    """'a/b/c' -> ['a', 'a/b']."""
    parts = rel.split("/")
    return ["/".join(parts[:i]) for i in range(1, len(parts))]


def check_ignored(pub: Path, release: list[str]) -> None:
    """Refuse when pub has an ignored file at a release path, inside a path the release makes a file, or where
    the release needs a folder: the reset to the release would overwrite or delete it. Other ignored files are
    left alone, even in an ignored folder the release adds files to. One line per outer path."""
    files, folders = set(release), {}  # folders: each folder the release makes -> its first path there
    for r in release:
        for d in parents(r):
            folders.setdefault(d, r)
    clashes = {}
    for p in filter(None, git(pub, "ls-files", "-z", "-o", "-i", "--exclude-standard").split("\0")):
        p = p.rstrip("/")  # a nested repo is listed as its folder
        if p in files or p in folders:
            clashes.setdefault(p, (p, p if p in files else folders[p]))
        for d in parents(p):
            if d in files:
                clashes.setdefault(d, (p, d))
    if clashes:
        raise Refused("\n".join(f"{pub}: ignored file {p} is where the release puts {r}; move it, then rerun"
                                for p, r in (clashes[k] for k in sorted(clashes))))


def check_version(pub: Path, parent: str, tree: str) -> None:
    """Refuse a change to plugins/kit (content, mode, a file added or removed) under the parent's version. A
    parent without plugin.json (a repo created with only a README) makes this a first release."""
    old = run_git(pub, "show", f"{parent}:{PLUGIN_JSON}")
    if old.returncode:
        return
    new = version(git(pub, "show", f"{tree}:{PLUGIN_JSON}"), f"{PLUGIN_JSON} in this release")
    if version(old.stdout, f"{PLUGIN_JSON} at {pub}'s HEAD") != new:
        return
    r = run_git(pub, "diff-tree", "--quiet", parent, tree, "--", PLUGIN_DIR)
    if r.returncode == 1:
        raise Refused(f"{PLUGIN_DIR} changed but its version is still {new}; bump version in {PLUGIN_JSON} "
                      "and commit, or installed copies will not update")
    if r.returncode:
        raise Refused(f"git diff-tree in {pub} failed: {r.stderr.strip()}")


def export(pub: Path, message: str, src: Path = ROOT) -> int:
    pub, src = pub.resolve(), src.resolve()
    check_repos(pub, src)
    terms = load_terms(src)
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        staging = tmp / "export"
        staging.mkdir()
        stage(src, staging)
        files = leak_check.tree_files(staging)  # the one list that is checked, hashed and committed
        hits = leak_check.scan(staging, terms, files) + message_hits(message, terms)
        if hits:
            print("\n".join(hits))
            print(f"export_public: leak check failed ({len(hits)} hits); nothing was written to {pub}", file=sys.stderr)
            return 1
        tree = stage_tree(pub, staging, files, tmp)
    r = run_git(pub, "rev-parse", "--verify", "--quiet", "HEAD^{commit}")
    parent = r.stdout.strip() if r.returncode == 0 else None
    if parent and git(pub, "rev-parse", f"{parent}^{{tree}}").strip() == tree:
        print("export_public: the public repo already matches HEAD; nothing to release")
        return 0
    if parent:
        check_version(pub, parent, tree)
    check_ignored(pub, files)
    commit = git(pub, "commit-tree", tree, *(["-p", parent] if parent else []), "-m", message).strip()
    who = git(pub, "log", "-1", "--format=author %an <%ae>, committer %cn <%ce>", commit).strip()
    short = git(pub, "rev-parse", "--short", commit).strip()
    git(pub, "update-ref", "HEAD", commit, parent or "0" * len(commit))  # all zeros: HEAD must still be unborn
    try:
        git(pub, "reset", "-q", "--hard", "HEAD")
    except (Refused, OSError) as e:
        print(f"export_public: {e}", file=sys.stderr)
        print(f"export_public: HEAD in {pub} is now {commit}, but its files are not updated: fix the cause, then run "
              f"git -C {shlex.quote(str(pub))} reset --hard", file=sys.stderr)
        return 2
    print(f"export_public: committed {short} in {pub} as {who}. Not pushed.")
    return 0


def main(argv: list[str] | None = None, src: Path = ROOT) -> int:
    ap = argparse.ArgumentParser(description="Export a public release into a separate git repo (never pushes).")
    ap.add_argument("public_repo", type=Path)
    ap.add_argument("-m", "--message", required=True, help="commit message for the release commit")
    a = ap.parse_args(argv)
    try:
        return export(a.public_repo, a.message, src=src)
    except (Refused, leak_check.UsageError, OSError, UnicodeDecodeError, subprocess.CalledProcessError) as e:
        print(f"export_public: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
