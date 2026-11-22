from build_fixture import minimal_project, write
from decisions_index import main

DOC = """# Decisions

<!-- BEGIN INDEX -->
<!-- END INDEX -->

### D-001 — Use a plugin (2026-10-07)
**Decision** ...

### D-002 — Overleaf git (2026-10-07)
"""


def proj(tmp_path, text=DOC):
    p = minimal_project(tmp_path)
    write(p / "state" / "DECISIONS.md", text)
    return p


def test_writes_index(tmp_path):
    p = proj(tmp_path)
    assert main(["--project", str(p)]) == 0
    t = (p / "state" / "DECISIONS.md").read_text()
    assert "- D-001 (2026-10-07): Use a plugin\n- D-002 (2026-10-07): Overleaf git\n" in t


def test_check_mode_detects_stale_then_clean(tmp_path):
    p = proj(tmp_path)
    assert main(["--project", str(p), "--check"]) == 1
    main(["--project", str(p)])
    assert main(["--project", str(p), "--check"]) == 0


def test_duplicate_id_fails(tmp_path):
    p = proj(tmp_path, DOC.replace("D-002", "D-001"))
    assert main(["--project", str(p)]) == 2


def test_malformed_heading_fails(tmp_path):
    p = proj(tmp_path, DOC.replace("### D-002 — Overleaf git (2026-10-07)", "### D-002 Overleaf git"))
    assert main(["--project", str(p)]) == 2


def test_missing_markers_fails(tmp_path):
    p = proj(tmp_path, DOC.replace("<!-- BEGIN INDEX -->\n", ""))
    assert main(["--project", str(p)]) == 2
