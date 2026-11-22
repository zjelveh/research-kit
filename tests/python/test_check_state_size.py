import pytest

from build_fixture import minimal_project, write
from check_state_size import allotment, state_report
from kitlib import KitError

LIMITS = {"hook_budget_bytes": 8000, "rules_cap_bytes": 1536, "reserve_bytes": 1024,
          "min_state_bytes": 2048, "channel": "stdout"}


def test_allotment():
    assert allotment(LIMITS, 1000) == 8000 - 1000 - 1024


def test_rules_over_cap_is_error():
    with pytest.raises(KitError, match="rules.md is 2000 bytes"):
        allotment(LIMITS, 2000)


def test_allotment_below_minimum_is_error():
    with pytest.raises(KitError, match="shorten the rules in effect"):
        allotment({**LIMITS, "hook_budget_bytes": 4000}, 1500)


def test_state_report(tmp_path):
    p = minimal_project(tmp_path)
    write(p / "state" / "CURRENT_STATE.md", "x" * 6000)
    size, allot = state_report(p, LIMITS, 1000)
    assert (size, allot) == (6000, 5976)


def test_default_rules_fit_the_cap():
    from kitlib import DEFAULTS, load_limits
    text = (DEFAULTS / "rules.md").read_text()
    assert len(text.encode()) <= load_limits()["rules_cap_bytes"] and "/kit:review" in text


def test_the_allotment_uses_the_personal_rules(tmp_path, capsys):
    import os
    from pathlib import Path
    from check_state_size import main
    personal = Path(os.environ["KIT_PERSONAL_DIR"])
    personal.mkdir()
    (personal / "rules.md").write_text("r" * 1500)
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "CURRENT_STATE.md").write_text("s\n")
    assert main(["--project", str(tmp_path)]) == 0
    assert "allotment 4848 bytes" in capsys.readouterr().out   # 7372 - 1500 - 1024


def test_unreadable_rules_are_an_error_not_over_budget(tmp_path, capsys):
    import os
    from pathlib import Path
    from check_state_size import main
    personal = Path(os.environ["KIT_PERSONAL_DIR"])
    personal.mkdir()
    rules = personal / "rules.md"
    rules.write_text("r\n")
    rules.chmod(0)
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "CURRENT_STATE.md").write_text("s\n")
    try:
        if os.access(rules, os.R_OK):
            pytest.skip("running as a user who can read mode-0 files")
        assert main(["--project", str(tmp_path)]) == 2
        assert "check_state_size: ERROR" in capsys.readouterr().err
    finally:
        rules.chmod(0o644)
