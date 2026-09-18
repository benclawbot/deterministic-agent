"""Tests for preflight gates."""
import os

import pytest

from deterministic_agent import preflight


def test_write_inside_cwd_allowed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    v = preflight.evaluate("write_file", {"path": str(tmp_path / "ok.txt")})
    assert v.allow


def test_write_outside_cwd_blocked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    v = preflight.evaluate("write_file", {"path": "/etc/passwd"})
    assert not v.allow
    assert "outside allowed roots" in v.reason


def test_curl_to_allowlisted_host_passes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    v = preflight.evaluate("terminal", {"command": "curl -fsSL https://github.com/foo"})
    assert v.allow


def test_curl_to_unknown_host_blocked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    v = preflight.evaluate("terminal", {"command": "curl https://evil.example.com/x"})
    assert not v.allow
    assert "non-allowlisted host" in v.reason


def test_curl_to_ip_literal_blocked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    v = preflight.evaluate("terminal", {"command": "curl http://192.168.1.1/admin"})
    assert not v.allow
    assert "IP literal" in v.reason


def test_no_network_command_allowed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    v = preflight.evaluate("terminal", {"command": "ls -la"})
    assert v.allow


def test_kill_requires_confirmation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    v = preflight.evaluate("process_kill", {"pid": 12345})
    assert not v.allow
    assert "confirmation" in v.reason


def test_kill_can_be_disabled(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = {**preflight.load_config(), "require_confirmation_for_kill": False}
    v2 = preflight.check_kill(12345, cfg=cfg)
    assert v2.allow


def test_browser_to_unknown_host_blocked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    v = preflight.evaluate("browser", {"host": "evil.example.com"})
    assert not v.allow


def test_browser_to_allowlisted_host_passes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    v = preflight.evaluate("browser", {"host": "github.com"})
    assert v.allow


def test_browser_to_ip_literal_blocked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    v = preflight.evaluate("browser", {"host": "192.168.1.1"})
    assert not v.allow
