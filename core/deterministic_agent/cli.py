"""CLI entry point.

Subcommands:
- validate <tool_name> <result.json>   schema check a tool result
- preflight <action> <payload.json>    gate check an action
- lawlint <laws.md> <output.json>      check output against LAWS.md
- replay <skill> <inputs.json> <out>   record or compare a research run
- init                                 write default config to ~/.config/deterministic-agent/gates.yaml

Hooks call into the same Python functions; the CLI is for ad-hoc use
and testing. Exit codes: 0 = pass, 2 = fail (matches Hermes/Claude hook
convention).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from . import lawlint, preflight, replay, schemas


def _read_json(path: str) -> dict:
    """Read JSON from a file path, or stdin if path is '-'."""
    try:
        if path == "-":
            return json.loads(sys.stdin.read())
        return json.loads(Path(path).read_text())
    except json.JSONDecodeError as e:
        print(f"deterministic-agent: invalid JSON input: {e.msg} (line {e.lineno} col {e.colno})", file=sys.stderr)
        sys.exit(2)
    except FileNotFoundError:
        print(f"deterministic-agent: file not found: {path}", file=sys.stderr)
        sys.exit(2)


def _emit(verdict_like, *, ok: bool, detail: str = "") -> int:
    """Print a one-line JSON verdict and return exit code."""
    print(json.dumps({"ok": ok, "detail": detail}))
    return 0 if ok else 2


def cmd_validate(args: list[str]) -> int:
    if len(args) != 2:
        print("usage: validate <tool_name> <result.json>", file=sys.stderr)
        return 2
    tool_name, path = args
    result = _read_json(path)
    ok, err = schemas.validate(tool_name, result)
    return _emit(None, ok=ok, detail=err or "valid")


def cmd_preflight(args: list[str]) -> int:
    if len(args) != 2:
        print("usage: preflight <action> <payload.json|->", file=sys.stderr)
        return 2
    action, path = args
    payload = _read_json(path)
    v = preflight.evaluate(action, payload)
    return _emit(None, ok=v.allow, detail=v.reason or "allowed")


def cmd_lawlint(args: list[str]) -> int:
    if len(args) != 2:
        print("usage: lawlint <laws.md> <output.json|->", file=sys.stderr)
        return 2
    laws_path, output_path = args
    laws = lawlint.parse_laws(laws_path)
    output = _read_json(output_path)
    violations = lawlint.check(output, laws)
    if not violations:
        return _emit(None, ok=True, detail=f"all {len(laws)} laws conformant")
    detail = "; ".join(f"[{v.law}] {v.requirement}: {v.message}" for v in violations)
    return _emit(None, ok=False, detail=detail)


def cmd_replay(args: list[str]) -> int:
    if len(args) != 3:
        print("usage: replay <skill> <inputs.json|-> <output.json|->", file=sys.stderr)
        return 2
    skill, inputs_path, output_path = args
    inputs = _read_json(inputs_path)
    output = _read_json(output_path)
    matches, detail = replay.compare(skill, inputs, output)
    return _emit(None, ok=matches, detail=detail)


def cmd_init(args: list[str]) -> int:
    cfg_path = preflight.CONFIG_PATH
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    if cfg_path.exists():
        print(f"config already exists at {cfg_path}", file=sys.stderr)
        return 0
    import yaml
    cfg_path.write_text(yaml.safe_dump(preflight.DEFAULT_CONFIG, sort_keys=False))
    print(f"wrote default config to {cfg_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, args = argv[0], argv[1:]
    dispatch = {
        "validate": cmd_validate,
        "preflight": cmd_preflight,
        "lawlint": cmd_lawlint,
        "replay": cmd_replay,
        "init": cmd_init,
    }
    fn = dispatch.get(cmd)
    if fn is None:
        print(f"unknown command: {cmd}", file=sys.stderr)
        return 2
    return fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
