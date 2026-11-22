import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from build_fixture import bare_overleaf, web_edit, write
from review_fixture import fake_review
from scaffold import cmd_attach, cmd_new
from session_start import KIT_SCRIPTS, build_context

MAIN = "\\documentclass{article}\n\\begin{document}\nHello.\n\\end{document}\n"
LIMITS = {"hook_budget_bytes": 8000, "rules_cap_bytes": 1536, "reserve_bytes": 1024,
          "min_state_bytes": 2048, "channel": "stdout"}
RULES = "# rules\n- fail hard\n"


def attached(tmp_path, push=True):
    """Scaffold + attach. push=True mirrors the instructed next step (push the attach commit),
    so origin carries .lint_baseline."""
    bare = bare_overleaf(tmp_path, {"main.tex": MAIN})
    p = cmd_new("demo", tmp_path, ["r"])
    cmd_attach(str(bare), p)
    if push:
        subprocess.run(["git", "-C", str(p / "paper"), "push", "-q", "origin", "main"], check=True)
    return p, bare


def test_unpushed_attach_reports_missing_origin_baseline(tmp_path):
    p, _ = attached(tmp_path, push=False)
    out = build_context(p, {}, LIMITS, RULES)
    assert "ERROR numbers (paper origin):" in out and "baseline file missing at origin/main" in out


def test_normal_session(tmp_path):
    p, _ = attached(tmp_path)
    out = build_context(p, {}, LIMITS, RULES)
    assert "project: demo" in out and "- fail hard" in out and "## Next steps" in out
    assert "code: 0 uncommitted" in out
    assert "Overleaf: up to date" in out
    assert "numbers (paper working tree): ok" in out
    assert "numbers (paper origin): ok" in out
    assert "numbers (slides working tree): ok" in out


def test_over_budget_names_state_and_omits_it(tmp_path):
    p, _ = attached(tmp_path)
    write(p / "state" / "CURRENT_STATE.md", "SECRET-STATE " * 600)
    out = build_context(p, {}, LIMITS, RULES)
    assert "OVER BUDGET: state/CURRENT_STATE.md" in out and "SECRET-STATE" not in out


def test_paper_not_attached(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"])
    out = build_context(p, {}, LIMITS, RULES)
    assert "paper not attached" in out and "numbers (slides working tree): ok" in out


def test_web_edit_caught_on_origin(tmp_path):
    p, bare = attached(tmp_path)
    web_edit(tmp_path, bare, "main.tex", MAIN.replace("Hello.", "We saw 42 cases."))
    out = build_context(p, {}, LIMITS, RULES)
    assert "Overleaf: 1 new commits — pull before editing" in out
    assert "NUMBERS LINT REGRESSION (paper origin): 1 > 0" in out
    assert "numbers (paper working tree): ok" in out


def test_fetch_failure_reported(tmp_path):
    p, _ = attached(tmp_path)
    subprocess.run(["git", "-C", str(p / "paper"), "remote", "set-url", "origin", str(tmp_path / "nope.git")],
                   check=True)
    assert "ERROR fetch failed" in build_context(p, {}, LIMITS, RULES)


def test_missing_config_reported(tmp_path):
    assert "ERROR research-kit: no .claude/research.yml found" in build_context(tmp_path, {}, LIMITS, RULES)


def many_untracked(p):
    for k in range(40):
        write(p / "notes" / f"untracked_file_with_a_long_name_{k:02d}.md", "x")


def test_path_list_capped_at_five(tmp_path):
    p, _ = attached(tmp_path)
    many_untracked(p)
    out = build_context(p, {}, {**LIMITS, "reserve_bytes": 1024}, RULES)
    assert "code: 40 uncommitted" in out and "+35 more" in out
    assert "untracked_file_with_a_long_name_05" not in out


def test_reserve_overflow_goes_to_log(tmp_path):
    p, _ = attached(tmp_path)
    many_untracked(p)
    out = build_context(p, {}, {**LIMITS, "reserve_bytes": 300}, RULES)
    status = out.split("--- status ---\n")[1]
    assert len(status.encode()) <= 300
    assert "more lines in state/.hook.log" in status
    log = (p / "state" / ".hook.log").read_text()
    assert "numbers (slides working tree)" in log and "code: 40 uncommitted" in log


def test_session_id_written(tmp_path):
    p, _ = attached(tmp_path)
    build_context(p, {"session_id": "abc-123"}, LIMITS, RULES)
    assert (p / "state" / ".session_id").read_text() == "abc-123\n"


def git_head(repo):
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True,
                          text=True, check=True).stdout.strip()


def record(p, sid):
    return json.loads((p / "state" / ".sessions" / f"{sid}.json").read_text())


def commit_note(p, name):
    write(p / "notes" / name, "x\n")
    subprocess.run(["git", "-C", str(p), "add", f"notes/{name}"], check=True)
    subprocess.run(["git", "-C", str(p), "commit", "-qm", name], check=True)


def test_new_session_records_start_heads(tmp_path):
    p, _ = attached(tmp_path)
    build_context(p, {"session_id": "s1", "source": "startup"}, LIMITS, RULES)
    r = record(p, "s1")
    assert r["session_id"] == "s1" and r["started"] and r["source"] == "startup"
    assert r["code_head"] == git_head(p) and r["paper_head"] == git_head(p / "paper")


def test_each_session_keeps_its_own_record(tmp_path):
    """Session A, then B, then A resumed: A keeps its original start (review finding 1)."""
    p, _ = attached(tmp_path)
    build_context(p, {"session_id": "A", "source": "startup"}, LIMITS, RULES)
    a_first = (p / "state" / ".sessions" / "A.json").read_text()
    commit_note(p, "a.md")
    build_context(p, {"session_id": "B", "source": "startup"}, LIMITS, RULES)
    commit_note(p, "b.md")
    build_context(p, {"session_id": "A", "source": "resume"}, LIMITS, RULES)
    build_context(p, {"session_id": "A", "source": "compact"}, LIMITS, RULES)
    assert (p / "state" / ".sessions" / "A.json").read_text() == a_first
    assert record(p, "B")["code_head"] != record(p, "A")["code_head"]
    assert (p / "state" / ".session_id").read_text() == "A\n"


def test_missing_record_created_on_resume_and_marked(tmp_path):
    """A conversation from before this change gets a record at its next hook run, marked as a resume."""
    p, _ = attached(tmp_path)
    write(p / "state" / ".session_id", "old\n")
    build_context(p, {"session_id": "old", "source": "resume"}, LIMITS, RULES)
    r = record(p, "old")
    assert r["source"] == "resume" and r["code_head"] == git_head(p)


def test_session_start_before_attach(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"])
    build_context(p, {"session_id": "s1", "source": "startup"}, LIMITS, RULES)
    r = record(p, "s1")
    assert r["code_head"] == git_head(p) and r["paper_head"] is None


def test_unsafe_session_id_is_an_error_line(tmp_path):
    p, _ = attached(tmp_path)
    out = build_context(p, {"session_id": "../escape", "source": "startup"}, LIMITS, RULES)
    assert "ERROR session id:" in out
    assert not (p / "state" / "escape.json").exists() and not (p / "state" / ".sessions").exists()


def test_main_emits_configured_channel(tmp_path):
    p, _ = attached(tmp_path)
    r = subprocess.run([sys.executable, str(KIT_SCRIPTS / "session_start.py")],
                       input=json.dumps({"cwd": str(p), "session_id": "s1"}),
                       capture_output=True, text=True)
    assert r.returncode == 0
    from kitlib import load_limits
    if load_limits()["channel"] == "additional_context":
        assert "project: demo" in json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
    else:
        assert "project: demo" in r.stdout


def test_missing_origin_branch_is_an_error_line_not_a_crash(tmp_path):
    p, _ = attached(tmp_path)
    cfg = p / ".claude" / "research.yml"
    cfg.write_text(cfg.read_text().replace("paper_branch: main", "paper_branch: nosuch"))
    out = build_context(p, {}, LIMITS, RULES)
    assert "## Next steps" in out and "- fail hard" in out
    assert "ERROR" in out.split("--- status ---\n")[1]


def test_long_lines_do_not_hide_regressions(tmp_path):
    p, bare = attached(tmp_path)
    for k in range(6):
        write(p / "notes" / (f"{k}" + "é" * 90 + ".md"), "x")
    web_edit(tmp_path, bare, "main.tex", MAIN.replace("Hello.", "We saw 42 cases."))
    out = build_context(p, {}, LIMITS, RULES)
    status = out.split("--- status ---\n")[1]
    assert len(status.encode()) <= LIMITS["reserve_bytes"]
    assert "NUMBERS LINT REGRESSION (paper origin)" in status
    assert "new commits" in status


def test_non_utf8_state_is_an_error_line(tmp_path):
    p, _ = attached(tmp_path)
    with open(p / "state" / "CURRENT_STATE.md", "ab") as fh:
        fh.write(b"\xff\xfe")
    out = build_context(p, {}, LIMITS, RULES)
    assert "- fail hard" in out and "ERROR state" in out and "code:" in out


def test_oversized_rules_not_injected(tmp_path):
    p, _ = attached(tmp_path)
    out = build_context(p, {}, LIMITS, "R" * 20000)
    assert len(out.encode()) <= LIMITS["hook_budget_bytes"] + 200
    assert "ERROR rules" in out and "## Next steps" in out


def test_paper_not_a_git_repo(tmp_path):
    p, _ = attached(tmp_path)
    shutil.move(str(p / "paper" / ".git"), str(tmp_path / "moved.git"))
    out = build_context(p, {}, LIMITS, RULES)
    assert "ERROR paper is not a git repo" in out
    assert "paper: " not in out.split("--- status ---\n")[1]


def test_review_status_line(tmp_path):
    p = cmd_new("demo", tmp_path, ["r"])
    out = build_context(p, {}, LIMITS, RULES)
    assert "review: none yet (2 code files changed in the last 20 commits)" in out   # make_numbers.R, renv/activate.R
    head = subprocess.run(["git", "-C", str(p), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    fake_review(p, "r", head, finished="2026-10-18T10:00:00")
    assert "review:" not in build_context(p, {}, LIMITS, RULES)
    write(p / "analysis" / "numbers" / "make_numbers.R", "# changed\n")
    assert "review: 1 code file changed since the last review (2026-10-18)" in build_context(p, {}, LIMITS, RULES)


def test_review_status_error_is_reported(tmp_path, monkeypatch):
    import session_start

    def boom(project):
        raise session_start.KitError("broken")
    monkeypatch.setattr(session_start.codex_review, "review_status", boom)
    p = cmd_new("demo", tmp_path, ["r"])
    assert "ERROR review status: broken" in build_context(p, {}, LIMITS, RULES)


def test_session_start_leaves_the_code_index_alone(tmp_path):
    """A plain git status would rewrite .git/index after a stat-only change, racing other sessions'
    git commands for index.lock."""
    p, _ = attached(tmp_path)
    indexes = {}
    for repo, tracked in ((p, "CLAUDE.md"), (p / "paper", "main.tex")):
        st = (repo / tracked).stat()
        os.utime(repo / tracked, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
        indexes[repo / ".git" / "index"] = (repo / ".git" / "index").read_bytes()
    out = build_context(p, {}, LIMITS, RULES)
    assert "code: 0 uncommitted" in out and "paper: 0 uncommitted" in out
    for index, before in indexes.items():
        assert index.read_bytes() == before, index


def test_main_loads_personal_rules_and_names_the_source(tmp_path, monkeypatch, capsys):
    import session_start
    p = cmd_new("demo", tmp_path, ["r"])
    personal = Path(os.environ["KIT_PERSONAL_DIR"])
    personal.mkdir()
    (personal / "rules.md").write_text("# my rules\n- be brief\n")
    monkeypatch.chdir(p)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert session_start.main() == 0
    out = capsys.readouterr().out
    assert "# my rules\n- be brief" in out
    assert f"rules: personal ({personal / 'rules.md'})" in out


def test_main_uses_the_default_rules_without_a_personal_file(tmp_path, monkeypatch, capsys):
    import session_start
    from kitlib import DEFAULTS
    p = cmd_new("demo", tmp_path, ["r"])
    monkeypatch.chdir(p)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    session_start.main()
    out = capsys.readouterr().out
    assert (DEFAULTS / "rules.md").read_text().rstrip() in out and "rules: default (" in out


def test_personal_rules_over_the_cap_are_not_loaded(tmp_path, monkeypatch, capsys):
    import session_start
    p = cmd_new("demo", tmp_path, ["r"])
    personal = Path(os.environ["KIT_PERSONAL_DIR"])
    personal.mkdir()
    (personal / "rules.md").write_text("x" * 5000)
    monkeypatch.chdir(p)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    session_start.main()
    out = capsys.readouterr().out
    assert "ERROR rules:" in out and str(personal / "rules.md") in out and "x" * 100 not in out


def test_main_repoints_the_stable_path(tmp_path, monkeypatch, capsys):
    import session_start
    from kitlib import PLUGIN_ROOT, data_dir
    p = cmd_new("demo", tmp_path, ["r"])
    link = data_dir() / "plugin"
    link.unlink()
    link.symlink_to(tmp_path)
    monkeypatch.chdir(p)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    session_start.main()
    assert link.resolve() == PLUGIN_ROOT.resolve()


def test_a_stable_path_failure_is_reported_in_the_context(tmp_path, monkeypatch, capsys):
    import session_start
    from kitlib import PLUGIN_ROOT, data_dir
    p = cmd_new("demo", tmp_path, ["r"])
    link = data_dir() / "plugin"
    link.unlink()
    link.mkdir()
    monkeypatch.chdir(p)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert session_start.main() == 0
    out = capsys.readouterr().out
    assert "ERROR research-kit: stable path not updated" in out and "hook crashed" not in out
    link.rmdir()
    link.symlink_to(PLUGIN_ROOT)


def test_personal_rules_that_are_not_utf8_are_an_error_line_not_a_crash(tmp_path, monkeypatch, capsys):
    import session_start
    p = cmd_new("demo", tmp_path, ["r"])
    personal = Path(os.environ["KIT_PERSONAL_DIR"])
    personal.mkdir()
    (personal / "rules.md").write_bytes(b"# r\n\xff\xfe\n")
    monkeypatch.chdir(p)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    session_start.main()
    out = capsys.readouterr().out
    assert "ERROR rules:" in out and "hook crashed" not in out


def test_the_stable_path_is_repointed_even_when_the_hook_input_is_bad(tmp_path, monkeypatch, capsys):
    import session_start
    from kitlib import PLUGIN_ROOT, data_dir
    p = cmd_new("demo", tmp_path, ["r"])
    link = data_dir() / "plugin"
    link.unlink()
    link.symlink_to(tmp_path)
    monkeypatch.chdir(p)
    monkeypatch.setattr("sys.stdin", io.StringIO("{not json"))
    session_start.main()
    assert "hook crashed" in capsys.readouterr().out
    assert link.resolve() == PLUGIN_ROOT.resolve()
