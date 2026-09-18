"""Tests for lawlint."""
from pathlib import Path

from deterministic_agent import lawlint


LAWS_FIXTURE = """# LAWS

## LAW: every_finding_cites_location
- require: findings.0.file has ":"
- message: must cite file:line

## LAW: severity_is_canonical
- require: findings.0.severity in {critical,high,medium,low,nit}
- message: severity must be canonical
"""


def _write_laws(tmp_path: Path) -> Path:
    p = tmp_path / "LAWS.md"
    p.write_text(LAWS_FIXTURE)
    return p


def test_parse_laws_extracts_named_laws(tmp_path):
    p = _write_laws(tmp_path)
    laws = lawlint.parse_laws(p)
    assert len(laws) == 2
    assert laws[0].name == "every_finding_cites_location"
    assert laws[1].name == "severity_is_canonical"


def test_conformant_output_passes(tmp_path):
    p = _write_laws(tmp_path)
    laws = lawlint.parse_laws(p)
    out = {"findings": [{"file": "src/x.py:42", "severity": "high"}]}
    assert lawlint.check(out, laws) == []


def test_missing_severity_violated(tmp_path):
    p = _write_laws(tmp_path)
    laws = lawlint.parse_laws(p)
    out = {"findings": [{"file": "src/x.py:42", "severity": "yikes"}]}
    violations = lawlint.check(out, laws)
    assert len(violations) >= 1
    assert violations[0].law == "severity_is_canonical"


def test_missing_locator_violated(tmp_path):
    p = _write_laws(tmp_path)
    laws = lawlint.parse_laws(p)
    out = {"findings": [{"file": "src/x.py", "severity": "high"}]}
    violations = lawlint.check(out, laws)
    assert any(v.law == "every_finding_cites_location" for v in violations)
