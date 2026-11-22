"""Builds throwaway research-kit projects for tests (spec §7)."""
from __future__ import annotations

import subprocess
from pathlib import Path

CONFIG = """paper_dir: paper
paper_branch: main
languages: [r]
packages: {}
numbers_tex: paper/generated/numbers.tex
notation_tex: paper/generated/notation.tex
venue: undecided
lint:
  paper:
    globs: ["main.tex", "sections/*.tex"]
    baseline: .lint_baseline
  slides:
    globs: ["slides/*/*.tex"]
    baseline: .lint_baseline_slides
"""

GIT_ID = ["-c", "user.name=kit-test", "-c", "user.email=kit-test@example.invalid"]


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *GIT_ID, *args],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"git {args} failed: {proc.stderr}")
    return proc.stdout


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def minimal_project(root: Path, config: str = CONFIG) -> Path:
    """A project directory with config and state, no git, no paper/."""
    p = root / "proj"
    write(p / ".claude" / "research.yml", config)
    write(p / "state" / "CURRENT_STATE.md", "# Current state\n")
    write(p / ".lint_baseline_slides", "0\n")
    return p


def init_repo(path: Path, branch: str = "main") -> Path:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", branch)
    git(path, "add", "-A")
    git(path, "commit", "-q", "--allow-empty", "-m", "init")
    return path


def bare_overleaf(root: Path, files: dict[str, str], branch: str = "main") -> Path:
    """A bare repo standing in for an Overleaf git remote."""
    bare = root / "overleaf.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", branch, str(bare)], check=True)
    work = root / "overleaf-seed"
    for name, text in files.items():
        write(work / name, text)
    init_repo(work, branch)
    git(work, "remote", "add", "origin", str(bare))
    git(work, "push", "-q", "origin", branch)
    return bare


def web_edit(root: Path, bare: Path, name: str, text: str, branch: str = "main") -> None:
    """Simulate an Overleaf web edit: commit straight to the bare remote."""
    work = root / f"web-edit-{len(list(root.glob('web-edit-*')))}"
    subprocess.run(["git", "clone", "-q", "-b", branch, str(bare), str(work)], check=True)
    write(work / name, text)
    git(work, "add", "-A")
    git(work, "commit", "-q", "-m", "web edit")
    git(work, "push", "-q", "origin", branch)


def set_config(p: Path, old: str, new: str) -> None:
    """Replace one exact line fragment in the project's research.yml."""
    cfg = p / ".claude" / "research.yml"
    text = cfg.read_text()
    assert text.count(old) == 1, old
    cfg.write_text(text.replace(old, new))
