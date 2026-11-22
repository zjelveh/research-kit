import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

import codex_review
from codex_review import STOP_SIGNALS, Interrupted, _interrupted, main
from review_fixture import assert_stopped, code_project, install_fake_codex, running

SCRIPT = Path(__file__).resolve().parents[2] / "plugins" / "kit" / "scripts" / "codex_review.py"


@pytest.fixture
def handlers():
    """Restore the stop-signal handlers a test changes."""
    saved = {sig: signal.getsignal(sig) for sig in STOP_SIGNALS}
    yield
    for sig, handler in saved.items():
        signal.signal(sig, handler)


def test_timeout_stops_codex_and_cleans_up(tmp_path, monkeypatch):
    record = install_fake_codex(tmp_path, monkeypatch, mode="sleep")
    p = code_project(tmp_path)
    t0 = time.monotonic()
    assert main(["--project", str(p), "--timeout", "0.03"]) == 4
    assert time.monotonic() - t0 < 30
    rec = json.loads(record.read_text())
    assert_stopped(rec["pid"], rec["child"])            # the child ignored SIGTERM
    meta = json.loads(next((p / "notes" / "reviews").glob("*/meta.json")).read_text())
    assert meta["status"] == "incomplete" and "timed out" in meta["notes"][0]
    assert not list((tmp_path / "tmp").glob("kit-review-*"))


def test_sigterm_stops_the_review_and_cleans_up(tmp_path, monkeypatch):
    record = install_fake_codex(tmp_path, monkeypatch, mode="sleep")
    p = code_project(tmp_path)
    proc = subprocess.Popen([sys.executable, str(SCRIPT), "--project", str(p)], env=os.environ.copy())
    for _ in range(300):
        if record.exists():
            break
        time.sleep(0.1)
    assert record.exists(), "fake codex never started"
    proc.send_signal(signal.SIGTERM)
    assert proc.wait(timeout=60) == 4
    rec = json.loads(record.read_text())
    assert_stopped(rec["pid"], rec["child"])
    meta = json.loads(next((p / "notes" / "reviews").glob("*/meta.json")).read_text())
    assert meta["status"] == "incomplete" and "interrupted" in meta["notes"]
    assert not list((tmp_path / "tmp").glob("kit-review-*"))


def test_a_signal_before_the_review_starts_is_exit_4(tmp_path, monkeypatch, handlers):
    p = code_project(tmp_path)

    def interrupted(project):
        raise Interrupted("SIGTERM")
    monkeypatch.setattr(codex_review, "housekeeping", interrupted)
    assert main(["--project", str(p)]) == 4


def test_an_ignored_signal_stays_ignored_and_handlers_are_restored(tmp_path, monkeypatch, handlers):
    """Under nohup SIGHUP is ignored, and must not end the review."""
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    before = signal.getsignal(signal.SIGTERM)
    seen = {}

    def fake_review(*args):
        seen.update({sig: signal.getsignal(sig) for sig in STOP_SIGNALS})
        return 0
    monkeypatch.setattr(codex_review, "review", fake_review)
    assert main(["--project", str(code_project(tmp_path))]) == 0
    assert seen[signal.SIGHUP] is signal.SIG_IGN
    assert seen[signal.SIGTERM] is _interrupted and seen[signal.SIGINT] is _interrupted
    assert signal.getsignal(signal.SIGTERM) is before and signal.getsignal(signal.SIGHUP) is signal.SIG_IGN


def test_after_the_first_signal_the_others_are_ignored(handlers):
    for sig in STOP_SIGNALS:
        signal.signal(sig, _interrupted)
    with pytest.raises(Interrupted):
        _interrupted(signal.SIGTERM, None)
    assert all(signal.getsignal(sig) is signal.SIG_IGN for sig in STOP_SIGNALS)


def test_a_signal_during_cleanup_does_not_cut_it_short(tmp_path, monkeypatch, handlers):
    install_fake_codex(tmp_path, monkeypatch)
    p = code_project(tmp_path)
    real_remove = codex_review.remove_copy

    def remove_while_signalled(project, tmp):
        os.kill(os.getpid(), signal.SIGTERM)                  # the first stop signal, mid-cleanup
        real_remove(project, tmp)
    monkeypatch.setattr(codex_review, "remove_copy", remove_while_signalled)
    assert main(["--project", str(p)]) == 0
    meta = json.loads(next((p / "notes" / "reviews").glob("*/meta.json")).read_text())
    assert meta["status"] == "complete"
    assert not list((tmp_path / "tmp").glob("kit-review-*"))
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    codex_review.hold_signals()                               # without main's handlers: a no-op
    assert signal.getsignal(signal.SIGTERM) is signal.SIG_DFL


def test_running_counts_a_live_process_when_proc_is_missing(monkeypatch):
    """Without /proc (macOS), assert_stopped must not pass for a process that still runs."""
    done = subprocess.Popen(["true"])
    done.wait()
    real_read = Path.read_text

    def no_proc(self, *args, **kw):
        if str(self).startswith("/proc/"):
            raise FileNotFoundError(self)
        return real_read(self, *args, **kw)
    monkeypatch.setattr(Path, "read_text", no_proc)
    assert running(os.getpid()) and not running(done.pid)
