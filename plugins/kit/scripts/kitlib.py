"""Shared helpers for research-kit scripts: config, limits, git, globs, atomic writes."""
from __future__ import annotations

import contextlib
import keyword
import os
import re
import subprocess
import time
import types
from pathlib import Path

import yaml

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
LIMITS_FILE = PLUGIN_ROOT / "limits.yml"
DEFAULTS = PLUGIN_ROOT / "defaults"
ITEM_FILES = {"rules": "rules.md", "writing-voice": "writing-voice.md", "slides-style": "slides-style.md"}
VENUE_RE = re.compile(r"[a-z0-9][a-z0-9_-]*")
PERSONAL_CONFIG_KEYS = ("projects_root",)
CONFIG_REL = Path(".claude") / "research.yml"

CONFIG_STR_KEYS = ("paper_dir", "paper_branch", "numbers_tex", "notation_tex", "venue",
                   "lint.paper.baseline", "lint.slides.baseline")
CONFIG_LIST_KEYS = ("lint.paper.globs", "lint.slides.globs")
REQUIRED_CONFIG_KEYS = CONFIG_STR_KEYS + CONFIG_LIST_KEYS + ("languages", "packages")
LANGUAGES = ("r", "python")
R_PKG_RE = re.compile(r"^[A-Za-z][A-Za-z0-9.]*[A-Za-z0-9]$")
PY_PKG_RE = re.compile(r"^[a-z][a-z0-9_]*$")
LIMIT_INT_KEYS = ("hook_budget_bytes", "rules_cap_bytes", "reserve_bytes", "min_state_bytes",
                  "git_budget_seconds")
REQUIRED_LIMIT_KEYS = ("hook_budget_bytes", "rules_cap_bytes", "reserve_bytes",
                       "min_state_bytes", "git_budget_seconds", "channel")


class KitError(Exception):
    """A fail-hard error whose message is meant for the user."""


class GitTimeout(KitError):
    """A git call ran past its time limit, or the session-start budget was used up."""


def _get(data: dict, dotted: str):
    cur = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise KeyError(dotted)
        cur = cur[part]
    return cur


def _load_yaml(path: Path, allow_empty: bool = False) -> dict:
    path = Path(path)
    if not path.is_file():
        raise KitError(f"{path}: file not found")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
        raise KitError(f"{path}: cannot read YAML: {e}") from None
    if data is None and allow_empty:
        return {}
    if not isinstance(data, dict):
        raise KitError(f"{path}: expected a YAML mapping at the top level")
    return data


def package_name_problem(lang: str, name) -> str | None:
    """None if `name` is a valid package name for `lang`; otherwise the rule it breaks."""
    if lang == "r":
        if isinstance(name, str) and R_PKG_RE.fullmatch(name):
            return None
        return ("not a valid R package name (letters, digits and '.', starting with a letter, "
                "at least 2 characters, not ending in '.')")
    if isinstance(name, str) and PY_PKG_RE.fullmatch(name) and not keyword.iskeyword(name):
        return None
    return ("not a valid Python import name (lowercase letters, digits and '_', starting with "
            "a letter, not a keyword)")


def _check_languages(path: Path, data: dict) -> None:
    langs = data["languages"]
    if (not isinstance(langs, list) or not langs
            or not all(isinstance(x, str) and x in LANGUAGES for x in langs)):
        raise KitError(f"{path}: 'languages' must be a non-empty list of 'r' and/or 'python', got {langs!r}")
    if len(set(langs)) != len(langs):
        raise KitError(f"{path}: 'languages' lists a language twice: {langs!r}")
    pkgs = data["packages"]
    if not isinstance(pkgs, dict):
        raise KitError(f"{path}: 'packages' must be a mapping from language to package name "
                       f"({{}} for none), got {pkgs!r}")
    for lang, name in pkgs.items():
        if lang not in LANGUAGES:
            raise KitError(f"{path}: 'packages.{lang}': unknown language; use r or python")
        if lang not in langs:
            raise KitError(f"{path}: 'packages.{lang}': package language is not in 'languages' {langs!r}")
        if not isinstance(name, str):
            raise KitError(f"{path}: 'packages.{lang}': package name must be a quoted string, got {name!r}")
        problem = package_name_problem(lang, name)
        if problem:
            raise KitError(f"{path}: 'packages.{lang}': {name!r} is {problem}")


def load_config(project: Path) -> dict:
    path = Path(project) / CONFIG_REL
    data = _load_yaml(path)
    if "pkg_name" in data:
        raise KitError(f"{path}: 'pkg_name' is from the config schema before languages; replace it with "
                       "'languages: [r]' (or [python], or [r, python]) and 'packages: {r: \"<name>\"}' "
                       "('packages: {}' when there is none)")
    for key in REQUIRED_CONFIG_KEYS:
        try:
            _get(data, key)
        except KeyError:
            raise KitError(f"{path}: missing required key '{key}'") from None
    for key in CONFIG_STR_KEYS:
        v = _get(data, key)
        if not isinstance(v, str) or not v.strip():
            raise KitError(f"{path}: '{key}' must be a non-empty string, got {v!r}")
    for key in CONFIG_LIST_KEYS:
        v = _get(data, key)
        if not isinstance(v, list) or not v or not all(isinstance(g, str) and g.strip() for g in v):
            raise KitError(f"{path}: '{key}' must be a non-empty list of non-empty strings, got {v!r}")
    _check_languages(path, data)
    return data


def load_limits(path: Path = LIMITS_FILE) -> dict:
    data = _load_yaml(path)
    for key in REQUIRED_LIMIT_KEYS:
        if key not in data:
            raise KitError(f"{path}: missing required key '{key}'")
    for key in LIMIT_INT_KEYS:
        v = data[key]
        if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
            raise KitError(f"{path}: '{key}' must be a positive integer, got {v!r}")
    if data["channel"] not in ("stdout", "additional_context"):
        raise KitError(f"{path}: channel must be 'stdout' or 'additional_context', "
                       f"got {data['channel']!r}")
    return data


def find_project(start: Path) -> Path:
    cur = Path(start).resolve()
    for p in (cur, *cur.parents):
        if (p / CONFIG_REL).is_file():
            return p
    raise KitError(f"no {CONFIG_REL} found in {cur} or any parent directory")


def _env_dir(var: str, xdg: str, fallback: Path) -> Path:
    """$var, which must be absolute; else $xdg/research-kit when $xdg is absolute (the XDG spec ignores a
    relative one); else fallback/research-kit."""
    if os.environ.get(var):
        p = Path(os.environ[var]).expanduser()
        if not p.is_absolute():
            raise KitError(f"{var}={os.environ[var]!r} must be an absolute path")
        return p
    base = os.environ.get(xdg)
    return (Path(base) if base and Path(base).is_absolute() else fallback) / "research-kit"


def personal_dir() -> Path:
    """The user's personal layer (shareable-kit spec §2): KIT_PERSONAL_DIR, else
    $XDG_CONFIG_HOME/research-kit, else ~/.config/research-kit. It need not exist."""
    return _env_dir("KIT_PERSONAL_DIR", "XDG_CONFIG_HOME", Path.home() / ".config")


def data_dir() -> Path:
    """Where the kit's Python environment and the stable plugin path live (spec §3): KIT_DATA_DIR, else
    $XDG_DATA_HOME/research-kit, else ~/.local/share/research-kit."""
    return _env_dir("KIT_DATA_DIR", "XDG_DATA_HOME", Path.home() / ".local" / "share")


def stable_kit() -> Path:
    """The launcher through the stable path, which plugin updates don't move: git hooks and printed
    commands use it."""
    return data_dir() / "plugin" / "bin" / "kit"


def link_stable(plugin: Path = PLUGIN_ROOT) -> None:
    """Point the stable path at `plugin`, atomically, so every run in a session uses one plugin version."""
    link = data_dir() / "plugin"
    if link.is_symlink() and Path(os.readlink(link)) == plugin:
        return
    if link.exists() and not link.is_symlink():
        raise KitError(f"{link} exists and is not a symlink; remove it")
    link.parent.mkdir(parents=True, exist_ok=True)
    tmp = link.with_name(f".plugin.{os.getpid()}")
    with contextlib.suppress(FileNotFoundError):
        tmp.unlink()
    os.symlink(plugin, tmp, target_is_directory=True)
    try:
        os.replace(tmp, link)
    except OSError:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise


def item_rel(item: str, name: str | None = None) -> Path:
    """An overridable item's file name, relative to the defaults and the personal folder."""
    if item == "venue":
        if not name or not VENUE_RE.fullmatch(name):
            raise KitError(f"venue name {name!r}: use lowercase letters, digits, - and _")
        return Path("venues") / f"{name}.md"
    if name is not None or item not in ITEM_FILES:
        raise KitError(f"unknown item {item!r}; use rules, writing-voice, slides-style or venue <name>")
    return Path(ITEM_FILES[item])


def in_effect(item: str, name: str | None = None) -> tuple[Path, str]:
    """(the file in effect, 'personal' or 'default'): a personal file replaces the default of the same name."""
    rel = item_rel(item, name)
    for source, root in (("personal", personal_dir()), ("default", DEFAULTS)):
        if (root / rel).is_file():
            return root / rel, source
    raise KitError(f"no {rel} in {personal_dir()} or in the kit's defaults")


def personal_config() -> dict:
    """The personal config.yml ({} when there is none); only PERSONAL_CONFIG_KEYS are allowed."""
    path = personal_dir() / "config.yml"
    if not path.is_file():
        return {}
    data = _load_yaml(path, allow_empty=True)
    unknown = sorted(str(k) for k in data if k not in PERSONAL_CONFIG_KEYS)
    if unknown:
        raise KitError(f"{path}: unknown keys {unknown}; known: {list(PERSONAL_CONFIG_KEYS)}")
    return data


def read_env() -> dict:
    """For read-only git calls: git status still refreshes the index in memory but doesn't write it back."""
    return {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}


_deadlines = []   # the active git_deadline records, outermost first


@contextlib.contextmanager
def git_deadline(seconds: float):
    """Inside, all git calls together must finish within `seconds`. Yields a record whose `timed_out` is set
    when the deadline stopped or skipped a call. Session start uses it so its output arrives even when git
    is slow. A nested deadline can only shorten the one around it."""
    end = time.monotonic() + seconds
    if _deadlines:
        end = min(end, _deadlines[-1].end)
    record = types.SimpleNamespace(timed_out=False, end=end, seconds=seconds)
    _deadlines.append(record)
    try:
        yield record
    finally:
        _deadlines[:] = [d for d in _deadlines if d is not record]   # by identity, even if exits interleave


def _passed_deadline():
    """Marks every active deadline that has passed, and returns the outermost of them (None if none has)."""
    now = time.monotonic()
    passed = [d for d in _deadlines if now >= d.end]
    for d in passed:
        d.timed_out = True
    return passed[0] if passed else None


def time_left(timeout: float | None = None) -> float | None:
    """The timeout for the next git call: `timeout`, cut to what is left of the deadline if one is set."""
    if not _deadlines:
        return timeout
    remaining = _deadlines[-1].end - time.monotonic()
    if remaining <= 0:
        _passed_deadline()
        raise GitTimeout("skipped: session start's time limit for git checks was used up")
    return remaining if timeout is None else min(timeout, remaining)


def git_timeout(command: str, repo: Path, timeout: float) -> GitTimeout:
    """The error for `command` (a git command line) stopped by its `timeout` in `repo`. When the deadline
    stopped it, the message names the budget; a call stopped by its own shorter timeout (fetch's) marks no
    record, since nothing later is skipped."""
    passed = _passed_deadline()
    if passed:
        return GitTimeout(f"{command} in {repo} stopped: session start's {passed.seconds:g}s for git checks "
                          "ran out")
    return GitTimeout(f"{command} timed out after {timeout:g}s in {repo}")


def git(repo: Path, *args: str, timeout: float | None = None, check: bool = True,
        env: dict | None = None) -> str:
    timeout = time_left(timeout)
    try:
        proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                              text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        raise git_timeout(f"git {' '.join(args)}", repo, timeout) from None
    if check and proc.returncode != 0:
        msg = proc.stderr.strip() or proc.stdout.strip()
        raise KitError(f"git {' '.join(args)} failed in {repo}: {msg}")
    return proc.stdout


def glob_to_regex(pattern: str) -> re.Pattern:
    """Supports '*', '?', and '**' as a whole segment; other glob syntax raises KitError."""
    if any(c in pattern for c in "[]{}"):
        raise KitError(f"unsupported glob syntax in {pattern!r}: character classes and braces are not supported")
    for seg in pattern.split("/"):
        if "**" in seg and seg != "**":
            raise KitError(f"unsupported glob {pattern!r}: '**' must be a whole path segment")
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + r"\Z")


def atomic_write(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
