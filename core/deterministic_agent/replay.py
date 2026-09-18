"""Replay regression checks for research / monitoring skills.

Record the input set of a research-style run (queries, allowlist,
timestamp). On each subsequent run, replay the previous inputs and compare
output hashes. If the same inputs produce different output, something
drifted: model change, API change, prompt change, or a real change that
should be acknowledged.

State lives in ~/.local/share/deterministic-agent/replay/<skill>.json
by default. Override with DETERMINISTIC_AGENT_REPLAY_DIR.

This is a deterministic check by design — no LLM in the loop, just hash
equality. The model is *not* consulted to decide whether a regression is
"real"; humans are.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

STATE_DIR = Path(
    os.environ.get("DETERMINISTIC_AGENT_REPLAY_DIR", "~/.local/share/deterministic-agent/replay")
).expanduser()
STATE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ReplayRecord:
    skill: str
    inputs: dict
    output_hash: str
    timestamp: str


def _state_path(skill: str) -> Path:
    safe = skill.replace("/", "_").replace("..", "_")
    return STATE_DIR / f"{safe}.json"


def _hash_output(output) -> str:
    """Stable hash of any JSON-serializable output."""
    canonical = json.dumps(output, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _load(skill: str) -> ReplayRecord | None:
    p = _state_path(skill)
    if not p.exists():
        return None
    return ReplayRecord(**json.loads(p.read_text()))


def _save(rec: ReplayRecord) -> None:
    p = _state_path(rec.skill)
    p.write_text(json.dumps(rec.__dict__, indent=2))


def record(skill: str, inputs: dict, output) -> ReplayRecord:
    """Record a run and return the saved record."""
    rec = ReplayRecord(
        skill=skill,
        inputs=inputs,
        output_hash=_hash_output(output),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    _save(rec)
    return rec


def compare(skill: str, inputs: dict, output) -> tuple[bool, str]:
    """Compare current run against the last recorded one.

    Returns (matches, detail). matches=False means the same inputs
    produced different output since the last record. detail is the hash
    delta for debugging.
    """
    prev = _load(skill)
    if prev is None:
        record(skill, inputs, output)
        return True, "no prior record; baseline saved"

    if prev.inputs != inputs:
        record(skill, inputs, output)
        return True, f"inputs changed since last run; new baseline saved"

    cur_hash = _hash_output(output)
    if cur_hash == prev.output_hash:
        return True, f"output unchanged ({cur_hash[:12]})"

    return False, (
        f"regression detected: previous hash {prev.output_hash[:12]} "
        f"({prev.timestamp}) differs from current {cur_hash[:12]}. "
        f"Same inputs, different output — investigate or accept via `record()`."
    )
