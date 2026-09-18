"""LAWS.md linter: assert structured outputs conform to declared invariants.

Inspired by Bend's LAWS.bend but in markdown + Python. Skills opt in by
shipping a `LAWS.md` next to their SKILL.md. Each law is a named invariant
the skill's output must satisfy.

Law syntax (markdown, deliberately minimal):

    ## LAW: <name>
    - require: <jq-like path> <operator> <value>
    - require: <path> <operator> <value>
    - message: <human description>

Operators: ==, !=, in, notin, has, len>=, len<=

The linter parses LAWS.md, then validates a structured output (JSON/YAML
dict) against the laws. Returns a list of violations; an empty list means
the output is law-conformant.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

LAW_HEADER = re.compile(r"^##\s+LAW:\s*(?P<name>\S+)")
REQUIRE_LINE = re.compile(r"-\s*require:\s*(?P<path>\S+)\s+(?P<op>\S+)\s+(?P<value>.+?)\s*$")
MESSAGE_LINE = re.compile(r"-\s*message:\s*(?P<msg>.+?)\s*$")


@dataclass
class Law:
    name: str
    requires: list[tuple[str, str, str]]  # (path, op, value)
    message: str = ""


@dataclass
class Violation:
    law: str
    requirement: str
    message: str


def parse_laws(path: str | Path) -> list[Law]:
    """Parse a LAWS.md file into a list of Law objects."""
    text = Path(path).read_text()
    laws: list[Law] = []
    current: Law | None = None
    for raw in text.splitlines():
        m = LAW_HEADER.match(raw)
        if m:
            if current:
                laws.append(current)
            current = Law(name=m.group("name"), requires=[], message="")
            continue
        if current is None:
            continue
        rm = REQUIRE_LINE.match(raw)
        if rm:
            current.requires.append((rm.group("path"), rm.group("op"), rm.group("value").strip('"')))
            continue
        mm = MESSAGE_LINE.match(raw)
        if mm:
            current.message = mm.group("msg")
    if current:
        laws.append(current)
    return laws


def _resolve(obj: dict, path: str):
    """Resolve a dotted path like 'findings.0.url' against obj."""
    cur = obj
    for part in path.split("."):
        if cur is None:
            return None
        if part.isdigit():
            try:
                cur = cur[int(part)]
            except (IndexError, TypeError):
                return None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


_OPS = {
    "==": lambda a, b: a == _coerce(b),
    "!=": lambda a, b: a != _coerce(b),
    "has": lambda a, b: isinstance(a, (list, dict, str)) and b in a,
    "notin": lambda a, b: a not in _coerce_list(b),
    "in": lambda a, b: a in _coerce_list(b),
    "len>=": lambda a, b: isinstance(a, (list, dict, str)) and len(a) >= int(b),
    "len<=": lambda a, b: isinstance(a, (list, dict, str)) and len(a) <= int(b),
    "len==": lambda a, b: isinstance(a, (list, dict, str)) and len(a) == int(b),
}


def _coerce(s: str):
    if s == "true":
        return True
    if s == "false":
        return False
    if s == "null":
        return None
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d+\.\d+", s):
        return float(s)
    return s.strip('"').strip("'")


def _coerce_list(s: str) -> list:
    """Coerce a comma-separated list literal '{a,b,c}' into a list."""
    s = s.strip()
    if s.startswith("{") and s.endswith("}"):
        return [_coerce(x) for x in s[1:-1].split(",")]
    return [_coerce(s)]


def check(output: dict, laws: list[Law]) -> list[Violation]:
    """Check a structured output against laws. Returns violations."""
    violations: list[Violation] = []
    for law in laws:
        for path, op, value in law.requires:
            actual = _resolve(output, path)
            fn = _OPS.get(op)
            if fn is None:
                violations.append(Violation(law.name, f"{path} {op} {value}", f"unknown operator '{op}'"))
                continue
            try:
                if not fn(actual, value):
                    violations.append(
                        Violation(
                            law.name,
                            f"{path} {op} {value}",
                            f"{law.message or 'law violated'}: {path}={actual!r}",
                        )
                    )
            except Exception as e:
                violations.append(Violation(law.name, f"{path} {op} {value}", f"check errored: {e}"))
    return violations
