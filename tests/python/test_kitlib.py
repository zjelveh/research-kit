import json
from pathlib import Path

import pytest

from build_fixture import CONFIG, init_repo, minimal_project, write
from kitlib import git as kit_git
from kitlib import PLUGIN_ROOT, KitError, atomic_write, find_project, glob_to_regex, load_config, load_limits
from kitlib import package_name_problem


def test_load_config_ok(tmp_path):
    cfg = load_config(minimal_project(tmp_path))
    assert cfg["lint"]["paper"]["baseline"] == ".lint_baseline"


def test_load_config_missing_file(tmp_path):
    with pytest.raises(KitError, match="research.yml: file not found"):
        load_config(tmp_path)


def test_load_config_missing_nested_key(tmp_path):
    p = minimal_project(tmp_path, CONFIG.replace("    baseline: .lint_baseline_slides\n", ""))
    with pytest.raises(KitError, match="missing required key 'lint.slides.baseline'"):
        load_config(p)


def test_load_limits_validates_channel(tmp_path):
    f = write(tmp_path / "limits.yml", "hook_budget_bytes: 8000\nrules_cap_bytes: 1536\n"
              "reserve_bytes: 1024\nmin_state_bytes: 2048\ngit_budget_seconds: 20\nchannel: carrier-pigeon\n")
    with pytest.raises(KitError, match="channel must be"):
        load_limits(f)


def test_find_project_walks_up(tmp_path):
    p = minimal_project(tmp_path)
    (p / "notes" / "memos").mkdir(parents=True)
    assert find_project(p / "notes" / "memos") == p.resolve()


def test_find_project_none(tmp_path):
    with pytest.raises(KitError, match="no .claude/research.yml found"):
        find_project(tmp_path)


@pytest.mark.parametrize("pattern,path,ok", [
    ("sections/*.tex", "sections/intro.tex", True),
    ("sections/*.tex", "sections/sub/intro.tex", False),
    ("slides/*/*.tex", "slides/asc/talk.tex", True),
    ("**/*.tex", "a/b/c.tex", True),
    ("main.tex", "main.tex", True),
    ("main.tex", "xmain.tex", False),
])
def test_glob_to_regex(pattern, path, ok):
    assert bool(glob_to_regex(pattern).match(path)) is ok


def test_atomic_write_replaces(tmp_path):
    f = tmp_path / "a" / "x.txt"
    atomic_write(f, "one")
    atomic_write(f, "two")
    assert f.read_text() == "two" and not (tmp_path / "a" / "x.txt.tmp").exists()


def test_malformed_yaml_names_file(tmp_path):
    p = minimal_project(tmp_path, "paper_dir: [unclosed\n")
    with pytest.raises(KitError, match="research.yml: cannot read YAML"):
        load_config(p)


def test_config_globs_must_be_list(tmp_path):
    p = minimal_project(tmp_path, CONFIG.replace('globs: ["main.tex", "sections/*.tex"]', 'globs: "main.tex"'))
    with pytest.raises(KitError, match="'lint.paper.globs' must be a non-empty list"):
        load_config(p)


def test_config_empty_value(tmp_path):
    p = minimal_project(tmp_path, CONFIG.replace("paper_dir: paper", "paper_dir:"))
    with pytest.raises(KitError, match="'paper_dir' must be a non-empty string"):
        load_config(p)


GOOD_LIMITS = ("hook_budget_bytes: 8000\nrules_cap_bytes: 1536\nreserve_bytes: 1024\n"
               "min_state_bytes: 2048\ngit_budget_seconds: 20\nchannel: stdout\n")


def test_load_limits_ok_and_types(tmp_path):
    assert load_limits(write(tmp_path / "l.yml", GOOD_LIMITS))["hook_budget_bytes"] == 8000
    with pytest.raises(KitError, match="'reserve_bytes' must be a positive integer"):
        load_limits(write(tmp_path / "m.yml", GOOD_LIMITS.replace("1024", '"1024"')))


@pytest.mark.parametrize("new,msg", [
    ("", "missing required key 'git_budget_seconds'"),
    ("git_budget_seconds: 0\n", "'git_budget_seconds' must be a positive integer"),
    ("git_budget_seconds: -5\n", "'git_budget_seconds' must be a positive integer"),
])
def test_load_limits_needs_a_positive_git_budget(tmp_path, new, msg):
    with pytest.raises(KitError, match=msg):
        load_limits(write(tmp_path / "l.yml", GOOD_LIMITS.replace("git_budget_seconds: 20\n", new)))


def test_the_git_budget_leaves_the_hook_time_to_print():
    hooks = json.loads((PLUGIN_ROOT / "hooks" / "hooks.json").read_text())
    timeout = hooks["hooks"]["SessionStart"][0]["hooks"][0]["timeout"]
    assert load_limits()["git_budget_seconds"] <= timeout - 5


@pytest.mark.parametrize("pattern", ["[ab].tex", "{a,b}.tex", "a**b/x.tex"])
def test_glob_unsupported_syntax_fails(pattern):
    with pytest.raises(KitError, match="unsupported glob"):
        glob_to_regex(pattern)


def test_glob_rejects_trailing_newline():
    assert not glob_to_regex("main.tex").match("main.tex\n")


def test_atomic_write_cleans_up_on_failure(tmp_path, monkeypatch):
    def boom(self, target):
        raise OSError("disk full")
    monkeypatch.setattr(Path, "replace", boom)
    with pytest.raises(OSError, match="disk full"):
        atomic_write(tmp_path / "x.txt", "data")
    assert not (tmp_path / "x.txt.tmp").exists()


def test_git_wrapper(tmp_path):
    r = init_repo(tmp_path / "r")
    assert kit_git(r, "rev-parse", "--abbrev-ref", "HEAD").strip() == "main"
    with pytest.raises(KitError, match="git rev-parse --verify nope failed"):
        kit_git(r, "rev-parse", "--verify", "nope")
    assert kit_git(r, "rev-parse", "--verify", "nope", check=False) == ""


def cfg_with(tmp_path, old, new):
    assert old in CONFIG, old
    return minimal_project(tmp_path, CONFIG.replace(old, new))


def test_languages_and_packages_ok(tmp_path):
    p = cfg_with(tmp_path, "languages: [r]\npackages: {}",
                 'languages: [r, python]\npackages: {r: "mypkg", python: "my_pkg"}')
    cfg = load_config(p)
    assert cfg["languages"] == ["r", "python"]
    assert cfg["packages"] == {"r": "mypkg", "python": "my_pkg"}


def test_old_pkg_name_schema_points_to_migration(tmp_path):
    p = cfg_with(tmp_path, "languages: [r]\npackages: {}", "pkg_name: demo")
    with pytest.raises(KitError, match="schema before languages.*replace it with"):
        load_config(p)


def test_missing_languages(tmp_path):
    p = cfg_with(tmp_path, "languages: [r]\n", "")
    with pytest.raises(KitError, match="missing required key 'languages'"):
        load_config(p)


@pytest.mark.parametrize("value,msg", [
    ("[]", "non-empty list"),
    ("[julia]", "non-empty list"),
    ("r", "non-empty list"),
    ("[r, r]", "lists a language twice"),
])
def test_bad_languages(tmp_path, value, msg):
    p = cfg_with(tmp_path, "languages: [r]", f"languages: {value}")
    with pytest.raises(KitError, match=msg):
        load_config(p)


@pytest.mark.parametrize("value,msg", [
    ("", "'packages' must be a mapping"),
    ("[r]", "'packages' must be a mapping"),
    ('{julia: "x"}', "'packages.julia': unknown language"),
    ('{python: "x"}', "'packages.python': package language is not in 'languages'"),
    ('{r: "2fast"}', "'packages.r': '2fast' is not a valid R package name"),
    ('{r: yes}', "'packages.r': package name must be a quoted string, got True"),
])
def test_bad_packages(tmp_path, value, msg):
    p = cfg_with(tmp_path, "packages: {}", f"packages: {value}")
    with pytest.raises(KitError, match=msg):
        load_config(p)


@pytest.mark.parametrize("lang,name,ok", [
    ("r", "mypkg", True), ("r", "my.pkg", True), ("r", "x", False), ("r", "pkg.", False),
    ("r", "2fast", False), ("python", "my_pkg", True), ("python", "MyPkg", False),
    ("python", "class", False), ("python", "9lives", False), ("python", None, False),
    ("r", "mypkg\n", False), ("python", "my_pkg\n", False),
])
def test_package_name_rules(lang, name, ok):
    assert (package_name_problem(lang, name) is None) is ok


def test_missing_packages(tmp_path):
    p = cfg_with(tmp_path, "packages: {}\n", "")
    with pytest.raises(KitError, match="missing required key 'packages'"):
        load_config(p)


def test_half_migrated_config_still_refused(tmp_path):
    p = cfg_with(tmp_path, "packages: {}", "packages: {}\npkg_name: demo")
    with pytest.raises(KitError, match="schema before languages"):
        load_config(p)


def test_library_key_is_optional_and_a_list_of_strings(tmp_path):
    assert "library" not in load_config(minimal_project(tmp_path / "a"))
    cfg = load_config(minimal_project(tmp_path / "b", CONFIG + "library: [analysis/R, analysis/paths.py]\n"))
    assert cfg["library"] == ["analysis/R", "analysis/paths.py"]
    assert load_config(minimal_project(tmp_path / "c", CONFIG + "library: []\n"))["library"] == []
    for bad in ("library: analysis/R\n", "library: [analysis/R, 3]\n", "library: ['']\n"):
        with pytest.raises(KitError, match="'library' must be a list"):
            load_config(minimal_project(tmp_path / f"d{len(bad)}", CONFIG + bad))


def test_paper_folders_lives_in_kitlib(tmp_path):
    from kitlib import paper_folders
    p = minimal_project(tmp_path)
    cfg = load_config(p)
    paper = (p / "paper").resolve()
    assert paper_folders(p, cfg, paper)[-2:] == [paper / "figures", paper / "tables"]
