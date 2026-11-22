"""Helpers for the codex_review tests: a project with code, a fake `codex`, fake review records."""
from __future__ import annotations

import json
import os
import shutil
import signal
import stat
import time
from pathlib import Path

from build_fixture import CONFIG, git, init_repo, write

FAKE_CODEX = r'''#!/usr/bin/env python3
import json, os, signal, subprocess, sys, time
from pathlib import Path
args = sys.argv[1:]
mode = os.environ.get("FAKE_CODEX_MODE", "ok")
if args == ["--version"]:
    print("codex-cli 0.0-test"); sys.exit(0)
if args[:2] == ["login", "status"]:
    if mode == "hang":
        time.sleep(60)
    sys.exit(1 if mode == "nologin" else 0)
assert args[0] == "exec", args
copy = Path(args[args.index("-C") + 1]); out = Path(args[args.index("-o") + 1])
time.sleep(float(os.environ.get("FAKE_CODEX_STDIN_DELAY", "0")))   # a slow start
brief = sys.stdin.read()
sandbox = os.environ.get("FAKE_CODEX_SANDBOX", "workspace-write [workdir]")
if sandbox != "noheader":                # the header codex exec prints first
    print(f"OpenAI Codex v0.0-test\n--------\nworkdir: {copy}\napproval: never", flush=True)
    if sandbox != "noline":
        print(f"sandbox: {sandbox}", flush=True)
    print("--------\nuser", flush=True)
time.sleep(float(os.environ.get("FAKE_CODEX_DELAY", "0")))
done = os.environ.get("FAKE_CODEX_DONE")
if done:
    Path(done).write_text("ran\n")
child = None
if mode in ("sleep", "background"):    # a child left running; in sleep mode it ignores SIGTERM, as a hung tool might
    if mode == "sleep":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    child = subprocess.Popen(["sleep", "60"]).pid
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
rec = os.environ.get("FAKE_CODEX_RECORD")
if rec:
    files = sorted(str(p.relative_to(copy)) for p in copy.rglob("*") if ".git" not in p.parts and p.is_file())
    Path(rec).write_text(json.dumps({
        "argv": args, "brief": brief, "files": files, "tmpdir": os.environ.get("TMPDIR"),
        "pid": os.getpid(), "child": child,
        "env_marker": (copy / "renv" / "library" / "marker").is_file(),
        "binary": (copy / "fig.bin").read_bytes().hex() if (copy / "fig.bin").exists() else None}))
if mode == "sleep":
    time.sleep(60)
if mode == "fail":
    print("boom", file=sys.stderr); sys.exit(1)
if mode == "invalid":
    out.write_text("not json"); sys.exit(0)
if mode == "badschema":
    out.write_text(json.dumps({"findings": []})); sys.exit(0)
out.write_text(json.dumps({
    "summary_markdown": "One bug.",
    "findings": [{"id": "F1", "severity": "high", "category": "code bug", "file": "analysis/a.R", "line": 3,
                  "claim": "c", "evidence": "e", "suggested_fix": "f"}],
    "verified": ["v"], "not_checked": []}))
'''


def code_project(tmp_path: Path, commits: int = 3) -> Path:
    """A kit project's git repo with code files, a memo and an ignored data folder, `commits` commits
    after init."""
    p = tmp_path / "proj"
    write(p / ".claude" / "research.yml", CONFIG)
    write(p / "analysis" / "a.R", "x <- 0\n")
    write(p / "analysis" / "b.py", "y = 0\n")
    write(p / "notes" / "memo.md", "memo\n")
    write(p / ".gitignore", "data/\n")
    init_repo(p)
    for k in range(commits):
        write(p / "analysis" / "a.R", f"x <- {k + 1}\n")
        git(p, "add", "-A")
        git(p, "commit", "-q", "-m", f"c{k}")
    return p


def install_fake_codex(tmp_path: Path, monkeypatch, mode: str = "ok") -> Path:
    """Put a fake `codex` first on PATH, isolate temp space and Codex config; return the record path.
    Every other folder holding a `codex` leaves PATH, so the real one can't run even if the fake fails."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    fake = bin_dir / "codex"
    fake.write_text(FAKE_CODEX)
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    rest = [d for d in os.environ["PATH"].split(os.pathsep) if not os.path.lexists(os.path.join(d or ".", "codex"))]
    monkeypatch.setenv("PATH", os.pathsep.join([str(bin_dir), *rest]))
    assert shutil.which("codex") == str(fake), shutil.which("codex")
    monkeypatch.setenv("FAKE_CODEX_MODE", mode)
    record = tmp_path / "record.json"
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    (tmp_path / "tmp").mkdir(exist_ok=True)
    monkeypatch.setenv("KIT_REVIEW_TMP", str(tmp_path / "tmp"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codexhome"))
    return record


def fake_review(project: Path, name: str, reviewed: str, status: str = "complete",
                reviewer: str = "codex", finished: str = "2026-10-18T10:00:00") -> Path:
    folder = project / "notes" / "reviews" / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "meta.json").write_text(json.dumps(
        {"reviewer": reviewer, "status": status, "reviewed": reviewed, "finished": finished}))
    return folder


def head(project: Path) -> str:
    return git(project, "rev-parse", "HEAD").strip()


def running(pid: int) -> bool:
    """A zombie runs no code, so it counts as stopped; without /proc (macOS) it can't be told apart."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:
        return "\nState:\tZ" not in Path(f"/proc/{pid}/status").read_text()
    except OSError:
        return True


def assert_stopped(*pids: int, wait: float = 5) -> None:
    """Each process has exited, within `wait` seconds; any still running is killed, then the test fails."""
    deadline = time.monotonic() + wait
    alive = [pid for pid in pids if running(pid)]
    while alive and time.monotonic() < deadline:
        time.sleep(0.1)
        alive = [pid for pid in alive if running(pid)]
    for pid in alive:
        os.kill(pid, signal.SIGKILL)
    assert not alive, f"still running after the review returned: {alive}"
