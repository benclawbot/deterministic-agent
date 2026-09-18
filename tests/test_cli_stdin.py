"""Tests for the CLI stdin-via-dash contract used by hooks."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

CLI = [sys.executable, "-m", "deterministic_agent.cli"]


@pytest.fixture
def cli_path():
    """Path to the core/ directory so `python -m deterministic_agent.cli` works."""
    return str(Path(__file__).parent.parent / "core")


def test_preflight_via_stdin_blocks(cli_path):
    payload = json.dumps({"path": "/etc/passwd"})
    r = subprocess.run(
        [*CLI, "preflight", "write_file", "-"],
        input=payload.encode(),
        capture_output=True,
        cwd=cli_path,
    )
    assert r.returncode == 2
    assert "outside allowed roots" in r.stdout.decode()


def test_preflight_via_stdin_allows(cli_path):
    payload = json.dumps({"command": "ls -la"})
    r = subprocess.run(
        [*CLI, "preflight", "terminal", "-"],
        input=payload.encode(),
        capture_output=True,
        cwd=cli_path,
    )
    assert r.returncode == 0


def test_replay_via_stdin_blocks_double_dash(cli_path, tmp_path, monkeypatch):
    """replay takes two stdin args via - -; we can't feed both through subprocess
    stdin in one go, so this just verifies the parser rejects malformed input cleanly."""
    monkeypatch.setenv("DETERMINISTIC_AGENT_REPLAY_DIR", str(tmp_path))
    r = subprocess.run(
        [*CLI, "replay", "test-skill-stdin", "-", "-"],
        input=b"not json",
        capture_output=True,
        cwd=cli_path,
    )
    # malformed input → nonzero, but not a Python crash with traceback to user
    assert r.returncode != 0
    assert b"Traceback" not in r.stderr


def test_validate_via_stdin(cli_path):
    result = json.dumps({"status": "ok", "payload": {"results": [{"url": "https://x.com", "title": "t"}]}})
    r = subprocess.run(
        [*CLI, "validate", "web_search", "-"],
        input=result.encode(),
        capture_output=True,
        cwd=cli_path,
    )
    assert r.returncode == 0
