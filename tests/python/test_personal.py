import os
from pathlib import Path

import pytest

import kitlib
from kitlib import DEFAULTS, PLUGIN_ROOT, KitError, in_effect, item_rel, personal_config, personal_dir


def personal():
    return Path(os.environ["KIT_PERSONAL_DIR"])


def test_plugin_root_is_the_folder_holding_scripts():
    assert (PLUGIN_ROOT / "scripts" / "kitlib.py").is_file() and DEFAULTS == PLUGIN_ROOT / "defaults"


def test_personal_dir_overrides(monkeypatch, tmp_path):
    assert personal_dir() == personal()
    monkeypatch.delenv("KIT_PERSONAL_DIR")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert personal_dir() == tmp_path / "xdg" / "research-kit"
    monkeypatch.delenv("XDG_CONFIG_HOME")
    assert personal_dir() == Path.home() / ".config" / "research-kit"


def test_data_dir_overrides(monkeypatch, tmp_path):
    monkeypatch.delenv("KIT_DATA_DIR")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert kitlib.data_dir() == tmp_path / "xdg" / "research-kit"
    assert kitlib.stable_kit() == tmp_path / "xdg" / "research-kit" / "plugin" / "bin" / "kit"
    monkeypatch.delenv("XDG_DATA_HOME")
    assert kitlib.data_dir() == Path.home() / ".local" / "share" / "research-kit"


def test_default_in_effect_until_a_personal_file_exists():
    assert in_effect("rules") == (DEFAULTS / "rules.md", "default")
    (personal()).mkdir()
    (personal() / "rules.md").write_text("# mine\n")
    assert in_effect("rules") == (personal() / "rules.md", "personal")


def test_venues_resolve_by_name_and_a_personal_venue_can_be_new():
    assert in_effect("venue", "undecided") == (DEFAULTS / "venues" / "undecided.md", "default")
    with pytest.raises(KitError, match="no venues/my-journal.md"):
        in_effect("venue", "my-journal")
    (personal() / "venues").mkdir(parents=True)
    (personal() / "venues" / "my-journal.md").write_text("# my-journal\n")
    assert in_effect("venue", "my-journal")[1] == "personal"


@pytest.mark.parametrize("item,name", [("voice", None), ("rules", "x"), ("venue", None), ("venue", "../x"),
                                       ("venue", "My-Journal")])
def test_bad_items(item, name):
    with pytest.raises(KitError):
        item_rel(item, name)


def test_personal_config():
    assert personal_config() == {}
    personal().mkdir()
    (personal() / "config.yml").write_text("projects_root: /somewhere\n")
    assert personal_config() == {"projects_root": "/somewhere"}
    (personal() / "config.yml").write_text("projects_root: /x\ncolour: blue\n")
    with pytest.raises(KitError, match="unknown keys"):
        personal_config()


def test_link_stable_is_atomic_and_refuses_a_real_folder(tmp_path):
    link = kitlib.data_dir() / "plugin"
    link.unlink()
    link.symlink_to(tmp_path)                           # points elsewhere
    kitlib.link_stable()
    assert link.resolve() == PLUGIN_ROOT.resolve()
    kitlib.link_stable()                                # idempotent
    link.unlink()
    link.mkdir()
    with pytest.raises(KitError, match="not a symlink"):
        kitlib.link_stable()
    link.rmdir()
    link.symlink_to(PLUGIN_ROOT)                        # leave the fixture's state


def test_default_rules_within_cap_and_without_personal_lines():
    text = (DEFAULTS / "rules.md").read_text()
    assert len(text.encode()) <= kitlib.load_limits()["rules_cap_bytes"]
    assert "/kit:review" in text and "Codex CLI is installed" in text
    assert "standing request" not in text and "Ask for everything pending" not in text


def test_a_relative_kit_folder_is_an_error_and_a_relative_xdg_is_ignored(monkeypatch, tmp_path):
    monkeypatch.setenv("KIT_PERSONAL_DIR", "rel")
    with pytest.raises(KitError, match="absolute"):
        personal_dir()
    monkeypatch.setenv("KIT_DATA_DIR", "rel")
    with pytest.raises(KitError, match="absolute"):
        kitlib.data_dir()
    monkeypatch.delenv("KIT_PERSONAL_DIR")
    monkeypatch.setenv("XDG_CONFIG_HOME", "relxdg")
    assert personal_dir() == Path.home() / ".config" / "research-kit"


@pytest.mark.parametrize("text", ["", "# projects_root: /x\n"])
def test_an_empty_personal_config_sets_nothing(text):
    personal().mkdir()
    (personal() / "config.yml").write_text(text)
    assert personal_config() == {}


def test_odd_keys_in_the_personal_config_are_reported_not_a_crash():
    personal().mkdir()
    (personal() / "config.yml").write_text("1: a\nfoo: b\n")
    with pytest.raises(KitError, match="unknown keys"):
        personal_config()


def test_a_failed_relink_leaves_no_temporary_link(monkeypatch, tmp_path):
    link = kitlib.data_dir() / "plugin"
    link.unlink()
    link.symlink_to(tmp_path)

    def boom(*a):
        raise OSError("disk full")
    monkeypatch.setattr(kitlib.os, "replace", boom)
    with pytest.raises(OSError):
        kitlib.link_stable()
    assert [p.name for p in link.parent.iterdir()] == ["plugin"]
    monkeypatch.undo()
    link.unlink()
    link.symlink_to(PLUGIN_ROOT)
