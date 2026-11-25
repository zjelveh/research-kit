import os
from pathlib import Path

from kitlib import DEFAULTS
from personal import main


def personal():
    return Path(os.environ["KIT_PERSONAL_DIR"])


def test_which_prints_the_file_in_effect(capsys):
    assert main(["which", "rules"]) == 0
    assert capsys.readouterr().out.strip() == str(DEFAULTS / "rules.md")
    assert main(["which", "venue", "undecided"]) == 0
    assert capsys.readouterr().out.strip().endswith("defaults/venues/undecided.md")


def test_customize_copies_the_default_once(capsys):
    assert main(["customize", "rules"]) == 0
    copy = personal() / "rules.md"
    assert capsys.readouterr().out.strip() == str(copy)
    assert copy.read_text() == (DEFAULTS / "rules.md").read_text()
    assert main(["which", "rules"]) == 0 and capsys.readouterr().out.strip() == str(copy)
    copy.write_text("mine\n")
    assert main(["customize", "rules"]) == 2
    assert "already exists" in capsys.readouterr().err and copy.read_text() == "mine\n"


def test_customize_a_new_venue_starts_from_the_template(capsys):
    assert main(["customize", "venue", "my-journal"]) == 0
    text = (personal() / "venues" / "my-journal.md").read_text()
    assert text.startswith("# Venue: my-journal") and "{{" not in text


def test_where_and_errors(capsys):
    assert main(["where"]) == 0 and capsys.readouterr().out.strip() == str(personal())
    assert main(["which", "voice"]) == 2 and "unknown item" in capsys.readouterr().err
    assert main(["which", "venue", "nope"]) == 2 and "no venues/nope.md" in capsys.readouterr().err


def test_customize_leaves_no_temporary_files_and_never_overwrites(capsys, monkeypatch):
    import personal as mod
    assert main(["customize", "rules"]) == 0
    assert sorted(p.name for p in personal().iterdir()) == ["rules.md"]
    (personal() / "venues").mkdir()
    real_link = mod.os.link

    def racing_link(src, dst):                  # another process creates the file first
        Path(dst).write_text("theirs\n")
        return real_link(src, dst)
    monkeypatch.setattr(mod.os, "link", racing_link)
    assert main(["customize", "venue", "my-journal"]) == 2
    assert "already exists" in capsys.readouterr().err
    assert (personal() / "venues" / "my-journal.md").read_text() == "theirs\n"
    assert sorted(p.name for p in (personal() / "venues").iterdir()) == ["my-journal.md"]


def test_customize_a_new_idiom_starts_from_the_template(capsys):
    assert main(["customize", "idiom", "my-plot"]) == 0
    text = (personal() / "idioms" / "my-plot.md").read_text()
    assert text.startswith("---\nid: my-plot\n") and "{{" not in text
    assert "\norigin: own\n" in text
    assert main(["which", "idiom", "my-plot"]) == 0
    assert capsys.readouterr().out.strip().endswith("idioms/my-plot.md")


def test_customize_writing_patterns(capsys):
    assert main(["customize", "writing-patterns"]) == 0
    copy = personal() / "writing-patterns.md"
    assert copy.read_text() == (DEFAULTS / "writing-patterns.md").read_text()
