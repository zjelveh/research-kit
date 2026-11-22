import json
import re
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]
REVIEW = KIT / "plugins" / "kit" / "templates" / "review"
PLACEHOLDERS = {"PROJECT", "START", "START_HOW", "HEAD", "REVIEWED", "STATE", "FILES", "CONTEXT", "PLAN", "AUTHOR"}


def objects(node):
    if isinstance(node, dict):
        if node.get("type") == "object":
            yield node
        for v in node.values():
            yield from objects(v)
    elif isinstance(node, list):
        for v in node:
            yield from objects(v)


def test_schema_is_strict():
    """Structured output needs every property required and no extra properties, at every level."""
    schema = json.loads((REVIEW / "findings.schema.json").read_text())
    found = list(objects(schema))
    assert len(found) == 2                                  # the answer and one finding
    for obj in found:
        assert obj["additionalProperties"] is False
        assert set(obj["required"]) == set(obj["properties"])


def test_brief_placeholders_are_exactly_the_known_ones():
    text = (REVIEW / "brief.md").read_text()
    assert set(re.findall(r"\{\{([A-Z_]+)\}\}", text)) == PLACEHOLDERS
