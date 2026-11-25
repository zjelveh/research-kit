#!/usr/bin/env python3
"""Independent review of a change by Codex (the /kit:review skill).

Reviews the code changed since the last complete review: it snapshots the reviewed state, runs
`codex exec` in a throwaway copy with a filled brief and a findings schema, and records the result in
<out>/<YYYY-MM-DDTHHMM>-codex-<head>/ (out: notes/reviews/, or --out). With --status it prints the
session-start status line instead.

Exit: 0 complete, nothing to review, or --status; 2 usage or project error; 3 codex missing or not
signed in; 4 timeout or interrupt; 5 codex failed or returned invalid findings.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kitlib import PLUGIN_ROOT, GitTimeout, KitError, git, git_timeout, read_env, time_left  # noqa: E402
import code_map  # noqa: E402

CODE_EXT = {".R", ".r", ".Rmd", ".qmd", ".py", ".sh", ".sql", ".stan", ".jl", ".do"}
TEMPLATES = PLUGIN_ROOT / "templates" / "review"
BRIEF_TEMPLATE = TEMPLATES / "brief.md"
SCHEMA = TEMPLATES / "findings.schema.json"
TMP_PREFIX = "kit-review-"
REF_NS = "refs/kit-reviews/"
BACK = 20
CHECK_TIMEOUT = 60       # seconds for `codex login status` and `codex --version`


class ReviewExit(Exception):
    """Ends a review with an exit code; the message is for the user."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


def is_code(path: str) -> bool:
    return Path(path).suffix in CODE_EXT


def out_dir(project: Path, out: str | None) -> Path:
    if not out:
        return project / "notes" / "reviews"
    p = Path(out)
    return p if p.is_absolute() else project / p


def tmp_root() -> Path:
    return Path(os.environ.get("KIT_REVIEW_TMP") or tempfile.gettempdir())


def reviews(out: Path) -> list[dict]:
    """The review records in `out`; unreadable ones, and ones whose `reviewed` or `finished` is not a
    string (a hand-edited meta.json), are skipped."""
    found = []
    for meta in sorted(out.glob("*/meta.json")):
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and all(isinstance(data.get(k, ""), str) for k in ("reviewed", "finished")):
            found.append({**data, "_folder": meta.parent.name})
    return found


def last_complete(out: Path) -> dict | None:
    """The newest complete Codex review; incomplete, failed and Claude-only reviews don't count."""
    done = [r for r in reviews(out) if r.get("reviewer") == "codex" and r.get("status") == "complete"
            and r.get("reviewed") and r.get("finished")]
    return max(done, key=lambda r: r["finished"]) if done else None


def is_commit(project: Path, rev: str) -> bool:
    return bool(git(project, "rev-parse", "--verify", "-q", f"{rev}^{{commit}}", check=False).strip())


def empty_tree(project: Path) -> str:
    return git(project, "hash-object", "-t", "tree", os.devnull).strip()


def default_start(project: Path) -> tuple[str, str]:
    back = git(project, "rev-parse", "--verify", "-q", f"HEAD~{BACK}", check=False).strip()
    return (back, f"{BACK} commits back") if back else (empty_tree(project), "the start of the history")


def range_start(project: Path, out: Path, base: str | None) -> tuple[str, str]:
    """(start, how it was chosen)."""
    if base:
        if not is_commit(project, base):
            raise ReviewExit(2, f"--base {base!r} is not a commit in {project}")
        return git(project, "rev-parse", f"{base}^{{commit}}").strip(), "given with --base"
    last = last_complete(out)
    if last:
        if is_commit(project, last["reviewed"]):
            return last["reviewed"], f"the last complete review, {last['_folder']}"
        print(f"codex_review: warning: the last review's state {last['reviewed'][:10]} is unreachable; "
              f"using the default start", file=sys.stderr)
    return default_start(project)


@contextlib.contextmanager
def index_copy(project: Path):
    """An environment whose index is a throwaway copy of the project's, so git commands that refresh or
    change the index leave the project's own untouched. (git diff refreshes the index it reads, even
    with GIT_OPTIONAL_LOCKS=0; with diff.autoRefreshIndex=false it lists touched files as changed.)
    The copy keeps the index's mtime: git checks the content of a file not older than the index file,
    and a fresh mtime would hide a same-size edit made in the second of the last index write."""
    index = Path(git(project, "rev-parse", "--path-format=absolute", "--git-path", "index").strip())
    with tempfile.TemporaryDirectory(prefix="kit-index-", dir=tmp_root()) as d:
        tmp_index = Path(d) / "index"
        if index.is_file():
            shutil.copy2(index, tmp_index)
        yield {**read_env(), "GIT_INDEX_FILE": str(tmp_index)}


def tree_blobs(project: Path, rev: str) -> dict[str, str]:
    """{path: blob id} for the files and symlinks in `rev`, from one ls-tree."""
    blobs = {}
    for entry in git(project, "ls-tree", "-r", "-z", rev).split("\0"):
        if entry:
            info, path = entry.split("\t", 1)
            _, kind, oid = info.split()
            if kind == "blob":
                blobs[path] = oid
    return blobs


def worktree_blob(project: Path, path: str) -> str | None:
    """The blob id `git add` would store for `path`: a symlink's text, not its target. None when the
    file is gone or unreadable."""
    f = project / path
    try:
        if f.is_symlink():
            timeout = time_left()
            try:
                proc = subprocess.run(["git", "-C", str(project), "hash-object", "--stdin"],
                                      input=os.fsencode(os.readlink(f)), capture_output=True, timeout=timeout)
            except subprocess.TimeoutExpired:
                raise git_timeout("git hash-object --stdin", project, timeout) from None
            return proc.stdout.decode().strip() if proc.returncode == 0 else None
        return git(project, "hash-object", "--", path).strip()
    except GitTimeout:
        raise
    except (OSError, KitError):
        return None


def changed_code_files(project: Path, start: str, out: Path | None = None) -> list[str]:
    """Code files that differ between `start` and the working tree, untracked files included, apart
    from those in `out` (the reviews folder). Reads only: nothing is written to the repository."""
    spec = pathspec(project, out)
    untracked = {p for p in git(project, "ls-files", "--others", "--exclude-standard", "-z", *spec,
                                env=read_env()).split("\0") if p and is_code(p)}
    with index_copy(project) as env:
        changed = {p for p in git(project, "diff", "--name-only", "--no-renames", "-z", start, *spec,
                                  env=env).split("\0") if p and p not in untracked}
    old = tree_blobs(project, start) if untracked else {}
    changed |= {p for p in untracked if p not in old or old[p] != worktree_blob(project, p)}
    return sorted(p for p in changed if is_code(p))


def plural(n: int) -> str:
    return f"{n} code file{'' if n == 1 else 's'}"


def review_status(project: Path, out: str | None = None) -> str | None:
    """The session-start status line, or None when there is nothing to say."""
    project = Path(project)
    if not git(project, "rev-parse", "--verify", "-q", "HEAD", check=False).strip():
        return None
    folder = out_dir(project, out)
    last = last_complete(folder)
    if last and is_commit(project, last["reviewed"]):
        n = len(changed_code_files(project, last["reviewed"], folder))
        return f"review: {plural(n)} changed since the last review ({last['finished'][:10]})" if n else None
    n = len(changed_code_files(project, default_start(project)[0], folder))
    return f"review: none yet ({plural(n)} changed in the last {BACK} commits)" if n else None


def head_commit(project: Path) -> str:
    head = git(project, "rev-parse", "--verify", "-q", "HEAD", check=False).strip()
    if not head:
        raise ReviewExit(2, f"{project} has no commits yet")
    return head


def pathspec(project: Path, exclude: Path | None) -> list[str]:
    """`-- .`, leaving out `exclude` (the reviews folder) when it lies inside the project. A gitignored
    folder needs no exclusion, and `git add` refuses one that names an ignored path."""
    if exclude is not None:
        rel = os.path.relpath(Path(exclude).resolve(), project.resolve())
        outside = rel == ".." or rel.startswith(".." + os.sep)
        if not outside and not git(project, "check-ignore", "--", rel, check=False).strip():
            return ["--", ".", f":(exclude){rel}"]
    return ["--", "."]


def snapshot(project: Path, ref_name: str, exclude: Path | None = None) -> tuple[str, bool]:
    """(reviewed, dirty). A clean tree is reviewed at HEAD. Uncommitted work is recorded as a commit on
    top of HEAD, built with a temporary index so the project's index, branch and working tree are
    untouched, and kept under refs/kit-reviews/ so garbage collection keeps it. `exclude` (the reviews
    folder) never counts as uncommitted work: its own records would otherwise make every tree dirty."""
    head = head_commit(project)
    spec = pathspec(project, exclude)
    if not git(project, "status", "--porcelain", "-uall", *spec, env=read_env()).strip():
        return head, False
    with index_copy(project) as env:
        git(project, "add", "-A", *spec, env=env)
        tree = git(project, "write-tree", env=env).strip()
    commit = git(project, "commit-tree", tree, "-p", head, "-m", "research-kit review snapshot").strip()
    try:
        git(project, "update-ref", REF_NS + ref_name, commit, "")     # "": the ref must not exist yet
    except KitError as e:
        raise ReviewExit(2, f"could not create {REF_NS + ref_name} (a review in another worktree of this "
                            f"repo may have taken the name; run the review again): {e}") from None
    return commit, True


def snapshot_refs(project: Path) -> set[str]:
    """The folder names under refs/kit-reviews/, which every worktree of the repo shares."""
    return {ref[len(REF_NS):] for ref in git(project, "for-each-ref", "--format=%(refname)", REF_NS).split()}


def prune_refs(project: Path, out: Path, keep: str | None) -> None:
    """Delete the snapshot refs of the reviews in `out` except `keep` (a folder name), or all of them
    when keep is None. A ref whose folder is not in `out` belongs to another worktree's reviews."""
    for name in snapshot_refs(project):
        if name != keep and (out / name).is_dir():
            git(project, "update-ref", "-d", REF_NS + name)


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def run_is_dead(d: Path) -> bool:
    """Whether the run that made temp folder `d` has ended: the pid in it is not running, or it has no
    pid and is over a minute old (a run writes its pid right after making the folder), or it is gone."""
    try:
        pid = int((d / "pid").read_text().strip())
    except (OSError, ValueError):
        pid = None
    if pid is not None:
        return not pid_alive(pid)
    try:
        return time.time() - d.stat().st_mtime >= 60
    except OSError:
        return True


def kit_worktrees(project: Path) -> list[str]:
    """The repo's registered worktrees shaped like kit copies (.../kit-review-*/copy), as git lists them,
    whatever temp root they were made under."""
    listed = git(project, "worktree", "list", "--porcelain", check=False).splitlines()
    paths = [line[len("worktree "):] for line in listed if line.startswith("worktree ")]
    return [w for w in paths if Path(w).name == "copy" and Path(w).parent.name.startswith(TMP_PREFIX)]


def housekeeping(project: Path) -> None:
    """Remove copies left by runs that died; a copy whose owner still runs, or that is under a minute
    old and has no pid yet, is left alone (it may belong to a review in another project). Only the
    kit's own worktree entries are unregistered: `git worktree prune` would also drop the user's
    worktrees whose folder is missing for the moment (an unmounted drive), index and all."""
    for w in kit_worktrees(project):
        if run_is_dead(Path(w).parent):
            git(project, "worktree", "remove", "-f", "-f", w, check=False)   # -f -f: also when locked
    for d in tmp_root().glob(TMP_PREFIX + "*"):
        if d.is_dir() and run_is_dead(d):
            shutil.rmtree(d, ignore_errors=True)


ENV_LINKS = ("renv/library", ".venv")


def make_copy(project: Path, reviewed: str) -> Path:
    """A detached worktree of `reviewed` in a fresh temp folder, with the project's environments linked."""
    tmp = Path(tempfile.mkdtemp(prefix=TMP_PREFIX, dir=tmp_root()))
    (tmp / "pid").write_text(f"{os.getpid()}\n", encoding="utf-8")
    copy = tmp / "copy"
    git(project, "worktree", "add", "--detach", "-q", str(copy), reviewed)
    for rel in ENV_LINKS:
        src, dst = project / rel, copy / rel
        if src.exists() and not dst.exists() and not dst.is_symlink():
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.symlink_to(src.resolve(), target_is_directory=True)
    (copy / ".tmp").mkdir(exist_ok=True)
    return tmp


def remove_copy(project: Path, tmp: Path) -> None:
    """`git worktree remove -f -f` deletes the environment symlinks without following them. An entry it
    leaves (a copy never fully made) is removed by the next run's housekeeping."""
    git(project, "worktree", "remove", "-f", "-f", str(tmp / "copy"), check=False)
    shutil.rmtree(tmp, ignore_errors=True)


def new_folder(out: Path, head: str, reviewer: str = "codex", now: dt.datetime | None = None,
               project: Path | None = None) -> Path:
    """A new review folder. With `project`, a name is also taken when its snapshot ref exists: it may
    belong to a review in another worktree of the repo."""
    stamp = (now or dt.datetime.now()).strftime("%Y-%m-%dT%H%M")
    base = f"{stamp}-{reviewer}-{head[:7]}"
    out.mkdir(parents=True, exist_ok=True)
    taken = snapshot_refs(project) if project else set()
    for k in range(1, 1000):
        folder = out / (base if k == 1 else f"{base}-{k}")
        if folder.name in taken:
            continue
        try:
            folder.mkdir()
            return folder
        except FileExistsError:
            continue
    raise ReviewExit(2, f"too many reviews named {base} in {out}")


class Interrupted(Exception):
    pass


STOP_SIGNALS = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)


def now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def context_paths(project: Path) -> str:
    lines = [f"- `{project / rel}`" for rel in ("CLAUDE.md", "state/DECISIONS.md") if (project / rel).is_file()]
    return "\n".join(lines) or "- none"


def fill_brief(project: Path, start: str, how: str, head: str, reviewed: str, dirty: bool,
               files: list[str], plan: Path | None, author: str | None) -> str:
    values = {
        "PROJECT": str(project), "START": start, "START_HOW": how, "HEAD": head, "REVIEWED": reviewed,
        "STATE": "uncommitted work included, as a snapshot commit on top of HEAD" if dirty
                 else "committed work only",
        "FILES": "\n".join(f"  - `{f}`" for f in files),
        "CONTEXT": context_paths(project),
        "PLAN": f"`{plan}`" if plan else "none",
        "AUTHOR": author.strip() if author and author.strip() else "(none given)",
        "CODE_MAP": code_map.review_section(project, files, start),
    }
    text = BRIEF_TEMPLATE.read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def codex_path() -> str:
    """The `codex` on PATH, as an absolute path, so the program checked is the one run: given a bare
    name, exec would try the next `codex` on PATH whenever one fails to start."""
    found = shutil.which("codex")
    if not found:
        raise ReviewExit(3, "codex is not installed (not on PATH)")
    return os.path.abspath(found)


def codex_version(codex: str) -> str:
    """`codex --version`, once `codex login status` says it is signed in; neither may hang the review."""
    try:
        login = subprocess.run([codex, "login", "status"], capture_output=True, text=True, timeout=CHECK_TIMEOUT)
        if login.returncode != 0:
            raise ReviewExit(3, "codex is not signed in: run `codex login` in a terminal")
        return subprocess.run([codex, "--version"], capture_output=True, text=True,
                              timeout=CHECK_TIMEOUT).stdout.strip()
    except subprocess.TimeoutExpired as e:
        raise ReviewExit(3, f"{shlex.join(e.cmd)} did not answer within {CHECK_TIMEOUT:g} s") from None
    except OSError as e:
        raise ReviewExit(3, f"{codex} could not be run: {e}") from None


def codex_model() -> tuple[str | None, str | None]:
    cfg = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "config.toml"
    try:
        import tomllib
        data = tomllib.loads(cfg.read_text(encoding="utf-8"))
    except (OSError, ValueError, ModuleNotFoundError):
        return None, None
    return data.get("model"), data.get("model_reasoning_effort")


def codex_command(codex: str, copy: Path, folder: Path) -> list[str]:
    return [codex, "exec", "-C", str(copy), "-s", "workspace-write",
            "-c", "sandbox_workspace_write.exclude_slash_tmp=true",
            "-c", "sandbox_workspace_write.exclude_tmpdir_env_var=true",
            "--output-schema", str(SCHEMA), "-o", str(folder / "findings.json"), "-"]


def signal_group(proc: subprocess.Popen, sig: int) -> None:
    try:
        os.killpg(proc.pid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def stop_group(proc: subprocess.Popen) -> None:
    """SIGTERM to Codex's process group; once the leader exits, or after 10 s, SIGKILL to the group, so
    children that ignored SIGTERM don't outlive the review."""
    for sig, wait in ((signal.SIGTERM, 10), (signal.SIGKILL, 5)):
        signal_group(proc, sig)
        try:
            proc.wait(timeout=wait)
        except subprocess.TimeoutExpired:
            pass


SANDBOX_LINE = "sandbox: workspace-write [workdir]"
HEADER_WAIT_S = 60.0        # Codex prints its header within a second or two


def sandbox_line(log: Path) -> str | None:
    """The `sandbox:` line of the header Codex prints first: "" if the header has none, None while
    the header is incomplete."""
    try:
        with open(log, "rb") as fh:
            lines = fh.read(65536).decode("utf-8", "replace").splitlines()
    except OSError:
        return None
    rules = [i for i, line in enumerate(lines) if line.strip() == "--------"]
    if len(rules) < 2:
        return None
    return next((line.strip() for line in lines[rules[0]:rules[1]] if line.startswith("sandbox:")), "")


def check_sandbox(log: Path, final: bool = False) -> bool:
    """True once the header shows a sandbox limited to the copy, False while it is incomplete (final:
    no more waiting). A wider sandbox, or none shown, is an error: a Codex upgrade may have dropped the
    /tmp exclusions."""
    line = sandbox_line(log)
    if line is None and not final:
        return False
    if line != SANDBOX_LINE:
        raise ReviewExit(5, f"Codex's sandbox is not limited to the copy ({line or 'no sandbox line in its log'}), "
                            f"so Codex was stopped; check the Codex settings bullet in "
                            f"{PLUGIN_ROOT / 'KNOWN-ISSUES.md'}")
    return True


def run_codex(cmd: list[str], copy: Path, brief: str, log: Path, timeout_s: float) -> int | None:
    """Codex's exit code, or None on timeout. Codex runs in its own process group, stopped as a whole,
    and as soon as its header shows a sandbox wider than the copy."""
    env = {**os.environ, "TMPDIR": str(copy / ".tmp")}
    start = time.monotonic()
    deadline = start + timeout_s
    with open(log, "wb") as fh, tempfile.TemporaryFile() as stdin:   # a file: no pipe to keep feeding
        stdin.write(brief.encode("utf-8"))
        stdin.seek(0)
        proc = subprocess.Popen(cmd, stdin=stdin, stdout=fh, stderr=subprocess.STDOUT,
                                env=env, start_new_session=True)
        try:
            checked = False
            while True:
                try:
                    proc.wait(timeout=max(deadline - time.monotonic(), 0) if checked else 0.2)
                    break
                except subprocess.TimeoutExpired:
                    checked = checked or check_sandbox(log, final=time.monotonic() - start > HEADER_WAIT_S)
                    if time.monotonic() >= deadline:
                        stop_group(proc)
                        return None
            if not checked and (proc.returncode == 0 or sandbox_line(log)):   # a failed Codex's own error, unless
                check_sandbox(log, final=True)                                  # its header shows a wider sandbox
            signal_group(proc, signal.SIGKILL)       # background processes Codex left: the copy goes next
            return proc.returncode
        except BaseException:
            stop_group(proc)
            raise


SEVERITIES = ("high", "medium", "low")
CATEGORIES = {"code bug", "wrong number", "reasoning error", "overclaim", "test gap"}
TOP_KEYS = {"summary_markdown", "findings", "verified", "not_checked"}
FINDING_KEYS = {"id", "severity", "category", "file", "line", "claim", "evidence", "suggested_fix"}


def validate(data) -> list[str]:
    """Problems with Codex's answer against the schema's required fields and types; [] when valid."""
    if not isinstance(data, dict):
        return ["the answer is not a JSON object"]
    problems = []
    if set(data) != TOP_KEYS:
        problems.append(f"top-level keys are {sorted(data)}, expected {sorted(TOP_KEYS)}")
    if not isinstance(data.get("summary_markdown"), str):
        problems.append("summary_markdown is not a string")
    for key in ("verified", "not_checked"):
        if not (isinstance(data.get(key), list) and all(isinstance(x, str) for x in data[key])):
            problems.append(f"{key} is not a list of strings")
    findings = data.get("findings")
    if not isinstance(findings, list):
        return problems + ["findings is not a list"]
    for k, f in enumerate(findings, start=1):
        if not isinstance(f, dict) or set(f) != FINDING_KEYS:
            problems.append(f"finding {k}: fields must be exactly {sorted(FINDING_KEYS)}")
            continue
        if f["severity"] not in SEVERITIES:
            problems.append(f"finding {k}: severity {f['severity']!r}")
        if f["category"] not in CATEGORIES:
            problems.append(f"finding {k}: category {f['category']!r}")
        if not (f["line"] is None or (isinstance(f["line"], int) and not isinstance(f["line"], bool))):
            problems.append(f"finding {k}: line {f['line']!r} is not an integer or null")
        for key in ("id", "file", "claim", "evidence", "suggested_fix"):
            if not isinstance(f[key], str):
                problems.append(f"finding {k}: {key} is not a string")
    return problems


def render_report(data: dict, meta: dict) -> str:
    where_from = "uncommitted work included" if meta["dirty"] else "committed work only"
    lines = [f"# Codex review {meta['folder']}", "",
             f"From `{meta['base'][:10]}` to `{meta['reviewed'][:10]}` ({len(meta['changed_files'])} code "
             f"files; {where_from}). Model: {meta['model'] or 'Codex default'}.", "",
             data["summary_markdown"].strip(), "", "## Findings", ""]
    for f in sorted(data["findings"], key=lambda f: SEVERITIES.index(f["severity"])):
        where = f["file"] + (f":{f['line']}" if f["line"] is not None else "")
        lines += [f"### {f['id']} ({f['severity']}, {f['category']}): `{where}`", "",
                  f"**Claim:** {f['claim']}", "", f"**Evidence:** {f['evidence']}", "",
                  f"**Suggested fix:** {f['suggested_fix']}", ""]
    if not data["findings"]:
        lines += ["None.", ""]
    lines += ["## Verified", ""] + [f"- {v}" for v in data["verified"]] + ["", "## Not checked", ""]
    lines += [f"- {v}" for v in data["not_checked"]]
    return "\n".join(lines) + "\n"


def log_tail(log: Path, n: int = 40) -> str | None:
    try:
        return "\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-n:])
    except OSError:
        return None


def work_tree_top(project: Path) -> Path:
    """`project` resolved (an empty one is the cwd); it must be the top of a git work tree."""
    project = Path(project).resolve()
    top = git(project, "rev-parse", "--show-toplevel", check=False).strip()
    if not top or Path(top).resolve() != project:
        raise ReviewExit(2, f"{project} is not the top of a git work tree; run from the project root or "
                            f"pass --project")
    return project


def kit_project(project: Path, out: str | None) -> Path:
    """--project, checked: the skill passes "${CLAUDE_PROJECT_DIR}", which is empty in Claude's Bash
    tool, so it is the cwd, which may be a subfolder or the paper clone. Without --out it must be a
    research-kit project (the kit's own repo reviews with --out docs/reviews/)."""
    project = work_tree_top(project)
    if not out and not (project / ".claude" / "research.yml").is_file():
        raise ReviewExit(2, f"{project} is not a research-kit project (no .claude/research.yml); run from "
                            f"the project root or pass --project")
    return project


def review(project: Path, base: str | None, brief_file: Path | None, plan: Path | None,
           out_arg: str | None, timeout_min: float) -> int:
    project = work_tree_top(project)
    brief_file, plan = (Path(f).resolve() if f else None for f in (brief_file, plan))   # the caller's cwd
    for f, what in ((brief_file, "--brief"), (plan, "--plan")):
        if f and not f.is_file():
            raise ReviewExit(2, f"{what} {f}: file not found")
    out = out_dir(project, out_arg)
    housekeeping(project)
    head = head_commit(project)
    start, how = range_start(project, out, base)
    files = changed_code_files(project, start, out)
    if not files:
        print(f"codex_review: no code file changed since {how}; nothing to review")
        return 0
    author = Path(brief_file).read_text(encoding="utf-8") if brief_file else None
    folder = new_folder(out, head, project=project)
    print(f"codex_review: review folder {folder}", flush=True)
    meta = {"reviewer": "codex", "folder": folder.name, "codex_version": None, "model": None,
            "effort": None, "base": start, "head": head, "reviewed": None, "dirty": None,
            "changed_files": files, "started": now_iso(), "finished": None, "duration_s": None,
            "status": "error", "command": None, "stderr_tail": None, "notes": []}
    t0, tmp = time.monotonic(), None
    try:
        if author is not None:
            (folder / "author_brief.md").write_text(author, encoding="utf-8")
        meta["reviewed"], meta["dirty"] = snapshot(project, folder.name, exclude=out)
        brief = fill_brief(project, start, how, head, meta["reviewed"], meta["dirty"], files, plan, author)
        (folder / "brief.md").write_text(brief, encoding="utf-8")
        codex = codex_path()
        meta["codex_version"] = codex_version(codex)
        meta["model"], meta["effort"] = codex_model()
        tmp = make_copy(project, meta["reviewed"])
        cmd = codex_command(codex, tmp / "copy", folder)
        meta["command"] = shlex.join(cmd)
        print(f"codex_review: reviewing {plural(len(files))} into {folder} "
              f"(up to {timeout_min:g} minutes)", flush=True)
        code = run_codex(cmd, tmp / "copy", brief, folder / "codex.log", timeout_min * 60)
        if code is None:
            meta["status"] = "incomplete"
            raise ReviewExit(4, f"Codex timed out after {timeout_min:g} minutes; see {folder / 'codex.log'}")
        if code != 0:
            raise ReviewExit(5, f"codex exited {code}; see {folder / 'codex.log'}")
        try:
            data = json.loads((folder / "findings.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise ReviewExit(5, f"Codex's answer is missing or not JSON ({e})") from None
        problems = validate(data)
        if problems:
            raise ReviewExit(5, "Codex's answer does not match the schema: " + "; ".join(problems[:5]))
        meta["status"] = "complete"
        (folder / "report.md").write_text(render_report(data, meta), encoding="utf-8")
        prune_refs(project, out, folder.name if meta["dirty"] else None)
        print(f"codex_review: complete, {len(data['findings'])} findings: {folder / 'report.md'}")
        return 0
    except (KeyboardInterrupt, Interrupted):
        meta["status"] = "incomplete"
        meta["notes"].append("interrupted")
        print(f"codex_review: interrupted; partial output in {folder}", file=sys.stderr)
        return 4
    except ReviewExit as e:
        meta["notes"].append(str(e))
        if e.code == 3:
            meta["notes"].append("codex unavailable; brief.md is ready for a Claude-only review")
        if e.code == 5:
            meta["stderr_tail"] = log_tail(folder / "codex.log") or str(e)
        raise
    except KitError as e:
        meta["notes"].append(str(e))
        raise
    finally:
        hold_signals()
        if tmp:
            remove_copy(project, tmp)
        # keep the snapshot when Codex was unavailable: a Claude-only review reads the state brief.md
        # names; the next complete review prunes it
        if meta["status"] != "complete" and meta.get("dirty") and "codex unavailable" not in " ".join(meta["notes"]):
            git(project, "update-ref", "-d", REF_NS + folder.name, check=False)
        meta["finished"] = now_iso()
        meta["duration_s"] = round(time.monotonic() - t0, 1)
        (folder / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def _interrupted(signum, frame):
    """The first stop signal ends the review; the rest are ignored, so cleanup runs to completion."""
    for sig in STOP_SIGNALS:
        signal.signal(sig, signal.SIG_IGN)
    raise Interrupted(signal.Signals(signum).name)


def hold_signals() -> None:
    """Ignore the stop signals routed to _interrupted, so cleanup runs to completion; main restores the
    handlers afterwards. Outside main (no _interrupted handler) it changes nothing."""
    for sig in STOP_SIGNALS:
        if signal.getsignal(sig) is _interrupted:
            signal.signal(sig, signal.SIG_IGN)


def catch_signals() -> dict:
    """Route the stop signals to _interrupted, except those the caller ignores (SIGHUP under nohup);
    return the handlers replaced."""
    return {sig: signal.signal(sig, _interrupted) for sig in STOP_SIGNALS
            if signal.getsignal(sig) is not signal.SIG_IGN}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", type=Path, default=Path.cwd())
    ap.add_argument("--base", help="start of the range (default: the last complete review)")
    ap.add_argument("--brief", type=Path, help="the author's brief: claims, weak spots, files outside the commits")
    ap.add_argument("--plan", type=Path, help="the plan task file, for a finished plan task")
    ap.add_argument("--out", help="output directory (default: notes/reviews/)")
    ap.add_argument("--timeout", type=float, default=45.0, help="minutes (default 45)")
    ap.add_argument("--status", action="store_true", help="print the status line and exit")
    a = ap.parse_args(argv)
    replaced = {}
    try:
        project = kit_project(a.project, a.out)
        if a.status:
            print(review_status(project, a.out) or "review: up to date")
            return 0
        replaced = catch_signals()
        return review(project, a.base, a.brief, a.plan, a.out, a.timeout)
    except (KeyboardInterrupt, Interrupted):
        print("codex_review: interrupted", file=sys.stderr)
        return 4
    except ReviewExit as e:
        print(f"codex_review: {e}", file=sys.stderr)
        return e.code
    except KitError as e:
        print(f"codex_review: ERROR: {e}", file=sys.stderr)
        return 2
    except Exception as e:        # review()'s finally has run: meta.json is written, the copy removed
        print(f"codex_review: ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    finally:
        for sig, handler in replaced.items():
            if handler is not None:
                signal.signal(sig, handler)


if __name__ == "__main__":
    raise SystemExit(main())
