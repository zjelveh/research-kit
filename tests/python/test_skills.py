"""Structural checks for every kit skill (Phase 2 conventions)."""
import re
from pathlib import Path

import pytest
import yaml

KIT = Path(__file__).resolve().parents[2]
SKILLS = KIT / "plugins" / "kit" / "skills"
SCRIPTS = KIT / "plugins" / "kit" / "scripts"
EXPECTED = {"writing", "slides", "checkpoint", "learn", "notes", "lit", "numbers", "new-project", "review", "figures",
            "code"}
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
    for rel in ("rules.md", "writing-voice.md", "writing-patterns.md", "slides-style.md", "figure-style.md",
                "venues/undecided.md"):
        text = (d / rel).read_text()
        assert not any(b in text for b in PRIVATE), rel


def test_voice_checks_live_in_the_voice_file():
    voice = (KIT / "plugins" / "kit" / "defaults" / "writing-voice.md").read_text()
    assert "\n### Pre-send checks\n" in voice and "- [ ] No intensifiers" in voice
    assert "bail" not in voice and "An example voice" in voice
    writing = (SKILLS / "writing" / "SKILL.md").read_text()
    assert "Pre-send checks" in writing and "No intensifiers" not in writing


def test_writing_patterns_name_no_model_paper_and_carry_checks():
    patterns = (KIT / "plugins" / "kit" / "defaults" / "writing-patterns.md").read_text()
    assert "doi.org" not in patterns and "\n### Pre-send checks\n" in patterns
    assert "bail" not in patterns and "kit customize writing-patterns" in patterns


def test_the_voice_has_no_sentence_shape_rules():
    voice = (KIT / "plugins" / "kit" / "defaults" / "writing-voice.md").read_text()
    assert "### Sentences" not in voice and "One idea per sentence" not in voice
    assert "in the claim's home" in voice


def test_default_rules_fit_the_cap_and_allow_section_approval():
    from kitlib import load_limits
    rules = (KIT / "plugins" / "kit" / "defaults" / "rules.md").read_text()
    assert len(rules.encode()) <= load_limits()["rules_cap_bytes"]
    assert "a whole section read in context" in rules
    assert "/kit:code" in rules and "params.yml" in rules


def test_code_skill_reads_the_map_first_and_states_the_hard_rule():
    text = (SKILLS / "code" / "SKILL.md").read_text()
    assert text.index("**(hard rule)**") < text.index("## 1. Map first")
    assert text.index("code_map.py --project") < text.index("## 2.")
    assert "analysis/explore/YYYY-MM-DD-<topic>" in text and "check-ignore" in text and "# literal: <reason>" in text
    assert "--files" in text and "--all" in text and "scaffold.py add-params" in text
    for heading in ("## 1. Map first", "## 2. Where the code goes", "## 3. Parameters", "## 4. The library",
                    "## 5. Methods and settings", "## 6. Before showing the code"):
        assert heading in text


def test_checkpoint_reports_the_code_map_and_the_readme_lists_code():
    text = (SKILLS / "checkpoint" / "SKILL.md").read_text()
    assert "8. **Code map**" in text and "steps 1–8" in text
    readme = (KIT / "README.md").read_text()
    assert "| `/kit:code` |" in readme and "explore/" in readme and "/kit:figures, /kit:code," in readme


def test_code_skill_makes_the_library_the_released_code():
    text = (SKILLS / "code" / "SKILL.md").read_text()
    assert "the paper's code as it will be released" in text and "thin drivers" in text
    assert "**(hard rule)** A pipeline script defines no function" in text and "run-all script" in text
