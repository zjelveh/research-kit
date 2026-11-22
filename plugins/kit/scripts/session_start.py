#!/usr/bin/env python3
"""SessionStart hook for research-kit (spec §5.1).

Always exits 0. Every error is printed into the injected context so the model sees it.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lint_numbers  # noqa: E402
import codex_review  # noqa: E402
from check_state_size import allotment  # noqa: E402
from kitlib import (GitTimeout, KitError, atomic_write, find_project, git, git_deadline, in_effect,  # noqa: E402
                    link_stable, load_config, load_limits, read_env)

KIT_SCRIPTS = Path(__file__).resolve().parent
HEADER = "=== research-kit session context ==="
LOG_NOTE = " (full text: state/.hook.log)"


STEP_ERRORS = (KitError, OSError, UnicodeDecodeError)
LINE_CAP = 300


def repo_status(name: str, repo: Path) -> str:
    out = git(repo, "status", "--porcelain", "-uall", env=read_env())
    paths = [line[3:] for line in out.splitlines()]
    line = f"{name}: {len(paths)} uncommitted"
    if paths:
        more = len(paths) - 5
        line += " (" + ", ".join(paths[:5]) + (f", +{more} more" if more > 0 else "") + ")"
    if git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", check=False).strip():
        line += f"; {git(repo, 'rev-list', '--count', '@{u}..HEAD').strip()} unpushed"
    else:
        line += "; no upstream"
    return line


def fetch_status(paper: Path, branch: str) -> str:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        git(paper, "fetch", "--quiet", "origin", timeout=5, env=env)
    except STEP_ERRORS as e:
        return f"ERROR fetch failed: {e}"
    try:
        behind = git(paper, "rev-list", "--count", f"HEAD..origin/{branch}").strip()
    except STEP_ERRORS as e:
        return f"ERROR overleaf: {e}"
    return "Overleaf: up to date" if behind == "0" else f"Overleaf: {behind} new commits — pull before editing"


def lint_status(project: Path, cfg: dict, gate: str, source: str, label: str) -> str:
    try:
        count, base, _ = lint_numbers.run_gate(project, cfg, gate, source)
    except STEP_ERRORS as e:
        return f"ERROR numbers ({label}): {e}"
    if count > base:
        return f"NUMBERS LINT REGRESSION ({label}): {count} > {base}"
    return f"numbers ({label}): ok ({count} <= {base})"


def is_priority(line: str) -> bool:
    return (line.startswith("ERROR") or line.startswith("NUMBERS LINT REGRESSION")
            or (line.startswith("Overleaf:") and "new commits" in line))


def truncate_line(line: str) -> str:
    if len(line.encode()) <= LINE_CAP:
        return line
    keep = LINE_CAP - len(LOG_NOTE.encode())
    return line.encode()[:keep].decode(errors="ignore") + LOG_NOTE


def cap_lines(lines: list[str], reserve: int) -> list[str]:
    lines = [truncate_line(line) for line in lines]
    budget = reserve - 48  # keep room for the overflow line
    chosen, used = set(), 0
    order = [i for i, line in enumerate(lines) if is_priority(line)] + \
            [i for i, line in enumerate(lines) if not is_priority(line)]
    for i in order:
        size = len(lines[i].encode()) + 1
        if used + size <= budget:
            chosen.add(i)
            used += size
    shown = [line for i, line in enumerate(lines) if i in chosen]
    dropped = len(lines) - len(chosen)
    if dropped:
        shown.append(f"+{dropped} more lines in state/.hook.log")
    return shown


def paper_is_own_repo(paper: Path) -> bool:
    try:
        top = git(paper, "rev-parse", "--show-toplevel").strip()
    except GitTimeout:
        raise
    except STEP_ERRORS:
        return False
    return Path(top).resolve() == paper.resolve()


def repo_head(repo: Path) -> str | None:
    return git(repo, "rev-parse", "--verify", "-q", "HEAD", check=False).strip() or None


SESSION_ID_RE = re.compile(r"[A-Za-z0-9_-]+")


def record_session(project: Path, paper: Path, session_id: str, source: str | None) -> None:
    """Write state/.session_id (the latest conversation), and state/.sessions/<id>.json once per
    conversation: the start time, how it started, and both repos' HEAD, so /kit:checkpoint can list
    that conversation's commits. An existing record is never rewritten, so a resume or compaction
    (even after other conversations ran) keeps its original start. The id is written before git runs:
    when git times out there is no record, and /kit:checkpoint reports the id instead of guessing."""
    if not SESSION_ID_RE.fullmatch(session_id):
        raise KitError(f"unexpected session id {session_id!r}; no session record written")
    (project / "state").mkdir(exist_ok=True)
    (project / "state" / ".session_id").write_text(f"{session_id}\n", encoding="utf-8")   # no shared temp file: two sessions may start at once
    rec = project / "state" / ".sessions" / f"{session_id}.json"
    if not rec.is_file():
        start = {"session_id": session_id,
                 "started": dt.datetime.now().isoformat(timespec="seconds"),
                 "source": source,
                 "code_head": repo_head(project),
                 "paper_head": repo_head(paper) if paper.is_dir() and paper_is_own_repo(paper) else None}
        atomic_write(rec, json.dumps(start, indent=2) + "\n")


def paper_lines(project: Path, cfg: dict, paper: Path) -> list[str]:
    """The paper's status lines, in their usual order. Overleaf's checks (fetch, then the origin lint) run
    before the paper's tree walk, so a slow tree uses up the git budget last."""
    if not paper.is_dir():
        return ["paper not attached — run scaffold.py attach-paper"]
    worktree = lint_status(project, cfg, "paper", "worktree", "paper working tree")
    try:
        own = paper_is_own_repo(paper)
    except GitTimeout as e:
        return [f"ERROR paper repo: {e}", worktree]
    if not own:
        return [f"ERROR paper is not a git repo: {paper}", worktree]
    fetch = fetch_status(paper, cfg["paper_branch"])
    origin = lint_status(project, cfg, "paper", f"origin/{cfg['paper_branch']}", "paper origin")
    try:
        repo = repo_status("paper", paper)
    except STEP_ERRORS as e:
        repo = f"ERROR paper repo: {e}"
    return [repo, fetch, worktree, origin]


def build_context(cwd: Path, hook_input: dict, limits: dict, rules: str | None, rules_note: str | None = None) -> str:
    try:
        project = find_project(cwd)
        cfg = load_config(project)
    except KitError as e:
        return f"{HEADER}\nERROR research-kit: {e}\n"
    parts, status = [f"{HEADER} project: {project.name}"], []
    rules_bytes = 0
    if rules is None:
        status.append(rules_note or "ERROR rules: no rules file in effect")
    else:
        n = len(rules.encode())
        if n > limits["rules_cap_bytes"]:
            where = rules_note.removeprefix("rules: ") if rules_note else "rules.md"
            status.append(f"ERROR rules: {where} is {n} bytes; cap is {limits['rules_cap_bytes']} — not loaded")
        else:
            rules_bytes = n
            parts.append(rules.rstrip())
            if rules_note:
                status.append(rules_note)
    state = project / "state" / "CURRENT_STATE.md"
    try:
        allot = allotment(limits, rules_bytes)
        if not state.is_file():
            raise KitError(f"{state}: file not found")
        text = state.read_text(encoding="utf-8")
        size = len(text.encode())
        if size > allot:
            parts.append(f"!!! OVER BUDGET: state/CURRENT_STATE.md is {size} bytes; its allotment is {allot} "
                         "bytes. It was NOT loaded. Run /kit:checkpoint to trim it; read the file directly meanwhile.")
        else:
            parts.append(text.rstrip())
    except STEP_ERRORS as e:
        status.append(f"ERROR state: {e}")
    paper = project / cfg["paper_dir"]
    with git_deadline(limits["git_budget_seconds"]) as budget:
        if hook_input.get("session_id"):
            try:
                record_session(project, paper, hook_input["session_id"], hook_input.get("source"))
            except STEP_ERRORS as e:
                status.append(f"ERROR session id: {e}")
        paper_part = paper_lines(project, cfg, paper)   # before the code repo's tree walk, shown after it
        try:
            status.append(repo_status("code", project))
        except STEP_ERRORS as e:
            status.append(f"ERROR code repo: {e}")
        try:
            line = codex_review.review_status(project)
            if line:
                status.append(line)
        except STEP_ERRORS as e:
            status.append(f"ERROR review status: {e}")
        status += paper_part
        status.append(lint_status(project, cfg, "slides", "worktree", "slides working tree"))
    if budget.timed_out:   # first, so cap_lines never moves it to the log
        status.insert(0, f"ERROR git checks: out of time ({limits['git_budget_seconds']}s), so some status lines "
                         "are missing; a large untracked folder slows git, so add it to .gitignore")
    log = project / "state" / ".hook.log"
    try:
        with log.open("a", encoding="utf-8") as fh:
            fh.write(f"--- {dt.datetime.now().isoformat(timespec='seconds')}\n" + "\n".join(status) + "\n")
    except STEP_ERRORS as e:
        status.append(f"ERROR hook log: {e}")
    parts.append("--- status ---\n" + "\n".join(cap_lines(status, limits["reserve_bytes"])))
    return "\n".join(parts) + "\n"


def emit(text: str, channel: str) -> None:
    if channel == "additional_context":
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}))
    else:
        sys.stdout.write(text)


def main() -> int:
    notes = []
    try:
        link_stable()  # first (shareable-kit spec §3): every later run in this session uses this plugin version
    except (KitError, OSError) as e:
        notes.append(f"ERROR research-kit: stable path not updated: {e}")
    try:
        raw = "" if sys.stdin.isatty() else sys.stdin.read()
        hook_input = json.loads(raw) if raw.strip() else {}
        limits = load_limits()
        try:
            path, source = in_effect("rules")
            rules, rules_note = path.read_text(encoding="utf-8"), f"rules: {source} ({path})"
        except STEP_ERRORS as e:
            rules, rules_note = None, f"ERROR rules: {e}"
        text = build_context(Path(hook_input.get("cwd") or os.getcwd()), hook_input, limits, rules, rules_note)
        channel = limits["channel"]
    except Exception as e:  # top-level handler (spec §5.1): the error must reach the model
        text, channel = f"{HEADER}\nERROR research-kit hook crashed: {type(e).__name__}: {e}\n", "stdout"
    if notes:
        text = text.rstrip("\n") + "\n" + "\n".join(notes) + "\n"
    emit(text, channel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
