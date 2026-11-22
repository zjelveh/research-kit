"""Structural checks for every kit skill (Phase 2 conventions)."""
import re
from pathlib import Path

import pytest
import yaml

KIT = Path(__file__).resolve().parents[2]
SKILLS = KIT / "plugins" / "kit" / "skills"
SCRIPTS = KIT / "plugins" / "kit" / "scripts"
EXPECTED = {"writing", "slides", "checkpoint", "learn", "notes", "lit", "numbers", "new-project", "review"}
PRIVATE = ("/" + "projects/", "/" + "home/", "(user" + ", 20")  # built from parts: this file is scanned by the leak check


def skill_files():
    return sorted(SKILLS.glob("*/SKILL.md"))


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, f"{path}: missing YAML frontmatter"
    return yaml.safe_load(m.group(1)), text


def test_expected_skills_exist():
    assert {p.parent.name for p in skill_files()} == EXPECTED


@pytest.mark.parametrize("path", skill_files(), ids=[p.parent.name for p in skill_files()])
def test_frontmatter_and_size(path):
    fm, text = frontmatter(path)
    assert fm["name"] == path.parent.name
    assert fm["description"].startswith("Use when")
    assert len(text.splitlines()) < 500
    assert fm.get("disable-model-invocation", False) is False
    assert "Done when" in text and "Stop and ask" in text


@pytest.mark.parametrize("path", skill_files(), ids=[p.parent.name for p in skill_files()])
def test_referenced_scripts_and_links_exist(path):
    _, text = frontmatter(path)
    for name in re.findall(r'bin/kit"? ([\w]+\.py)', text):
        assert (SCRIPTS / name).is_file(), f"{path}: references missing script {name}"
    for link in re.findall(r"\]\(([\w./-]+\.md)\)", text):
        assert (path.parent / link).is_file(), f"{path}: broken link {link}"
    assert not re.findall(r"(?<!\$\{CLAUDE_PLUGIN_ROOT\}/)bin/kit", text), f"{path}: call the launcher by ${{CLAUDE_PLUGIN_ROOT}}"
    for bad in (*PRIVATE, ".venv/bin/python"):
        assert bad not in text, f"{path}: contains {bad!r}"


def test_supporting_files_have_no_plugin_variables():
    """${CLAUDE_PLUGIN_ROOT} is substituted only in SKILL.md bodies; other files Claude reads keep it literal."""
    for f in SKILLS.glob("*/*.md"):
        if f.name != "SKILL.md":
            assert "CLAUDE_PLUGIN_ROOT" not in f.read_text(), f


def test_defaults_exist_and_carry_no_personal_lines():
    d = KIT / "plugins" / "kit" / "defaults"
    for rel in ("rules.md", "writing-voice.md", "slides-style.md", "venues/undecided.md"):
        text = (d / rel).read_text()
        assert not any(b in text for b in PRIVATE), rel
    voice = (d / "writing-voice.md").read_text()
    assert "applied micro" not in voice and '"read"' not in voice and "toy" not in voice


def test_voice_checks_live_in_the_voice_file():
    voice = (KIT / "plugins" / "kit" / "defaults" / "writing-voice.md").read_text()
    assert "\n### Pre-send checks\n" in voice and "- [ ] No intensifiers" in voice
    assert "bail" not in voice
    writing = (SKILLS / "writing" / "SKILL.md").read_text()
    assert "Pre-send checks" in writing and "No intensifiers" not in writing
