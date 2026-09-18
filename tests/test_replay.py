"""Tests for replay regression checks."""
import os
from pathlib import Path

import pytest

from deterministic_agent import replay


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setenv("DETERMINISTIC_AGENT_REPLAY_DIR", str(tmp_path))
    replay.STATE_DIR = Path(tmp_path)
    yield


def test_first_run_saves_baseline():
    inputs = {"query": "x"}
    output = {"results": [1, 2, 3]}
    matches, detail = replay.compare("test-skill", inputs, output)
    assert matches
    assert "no prior record" in detail


def test_identical_run_passes():
    inputs = {"query": "x"}
    output = {"results": [1, 2, 3]}
    replay.compare("test-skill", inputs, output)
    matches, detail = replay.compare("test-skill", inputs, output)
    assert matches
    assert "unchanged" in detail


def test_same_inputs_different_output_detected():
    inputs = {"query": "x"}
    replay.compare("test-skill", inputs, {"results": [1, 2, 3]})
    matches, detail = replay.compare("test-skill", inputs, {"results": [4, 5, 6]})
    assert not matches
    assert "regression detected" in detail


def test_changed_inputs_saves_new_baseline():
    replay.compare("test-skill", {"q": "a"}, {"r": 1})
    matches, detail = replay.compare("test-skill", {"q": "b"}, {"r": 2})
    assert matches
    assert "inputs changed" in detail
