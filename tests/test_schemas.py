"""Tests for schemas.validate."""

from deterministic_agent import schemas


def test_valid_envelope_passes():
    ok, err = schemas.validate("web_search", {
        "status": "ok",
        "payload": {"results": [{"url": "https://x.com", "title": "t"}]},
    })
    assert ok and err is None


def test_missing_status_fails():
    ok, _ = schemas.validate("web_search", {"payload": {"results": []}})
    assert not ok


def test_missing_results_field_fails():
    ok, err = schemas.validate("web_search", {
        "status": "ok",
        "payload": {"items": []},
    })
    assert not ok
    assert "payload violation" in (err or "")


def test_terminal_schema_requires_exit_code():
    ok, _err = schemas.validate("terminal", {
        "status": "ok",
        "payload": {"output": "hi"},
    })
    assert not ok


def test_unknown_tool_envelope_only():
    """Unknown tools pass if the envelope is valid — no payload schema to violate."""
    ok, _ = schemas.validate("made_up_tool", {"status": "ok", "payload": {"anything": 1}})
    assert ok


def test_read_file_schema():
    ok, _ = schemas.validate("read_file", {
        "status": "ok",
        "payload": {"content": "hello", "total_lines": 1},
    })
    assert ok
