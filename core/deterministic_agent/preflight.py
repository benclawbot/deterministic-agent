"""Pre-flight gates for irreversible actions.

Three categories are gated by default:
1. File writes outside the project's allowed roots
2. Network calls to non-allowlisted hosts (curl/wget/nc)
3. Process kills (catches accidental kill of the parent agent)

Each gate is a pure function (action, context) -> Verdict. Hooks call
`evaluate(action_name, payload)` and exit 0/2.

Defaults are conservative. Users override via a YAML config at
~/.config/deterministic-agent/gates.yaml (created on first run).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

CONFIG_PATH = Path(os.environ.get("DETERMINISTIC_AGENT_CONFIG", "~/.config/deterministic-agent/gates.yaml")).expanduser()

DEFAULT_CONFIG: dict = {
    "allowed_write_roots": ["$cwd", "$HOME/.hermes"],
    "allowed_network_hosts": [
        # conservative defaults; users add their own
        "github.com",
        "api.github.com",
        "pypi.org",
        "files.pythonhosted.org",
        "raw.githubusercontent.com",
    ],
    "require_confirmation_for_kill": True,
    "block_curl_to_ip_literal": True,
}


@dataclass(frozen=True)
class Verdict:
    allow: bool
    reason: str = ""


def _expand(p: str, cwd: str) -> str:
    if p == "$cwd":
        return cwd
    if p == "$HOME":
        return os.path.expanduser("~")
    return os.path.expanduser(p)


def _is_under(path: str, roots: list[str], cwd: str) -> bool:
    abs_path = os.path.abspath(path)
    for root in roots:
        r = os.path.abspath(_expand(root, cwd))
        try:
            os.path.commonpath([abs_path, r])
            if abs_path.startswith(r + os.sep) or abs_path == r:
                return True
        except ValueError:
            continue
    return False


# crude but effective: matches URLs anywhere, optionally preceded by curl/wget/nc or HTTP verb.
# Two-tier: prefer tool-prefixed capture (so we can attribute the call), then fall
# back to bare URLs in the command string (for "GET https://x", "POST https://y", etc.).
_NET_PATTERNS = [
    # tool + URL: curl/wget/nc followed by a URL
    re.compile(r"\b(?:curl|wget|nc)\b[^|\n;]*?(https?://[^\s\"'<>]+)", re.IGNORECASE),
    # bare URL anywhere in the command (no tool prefix required)
    re.compile(r"(https?://[^\s\"'<>]+)", re.IGNORECASE),
]


def _extract_urls(cmd: str) -> list[str]:
    """Find all URLs in a shell command string. Dedupes while preserving order."""
    found: list[str] = []
    seen: set[str] = set()
    for pat in _NET_PATTERNS:
        for m in pat.finditer(cmd):
            url = m.group(1)
            if url.startswith(("http://", "https://")) and url not in seen:
                found.append(url)
                seen.add(url)
    return found


def _host(url: str) -> str:
    m = re.match(r"https?://([^/:]+)", url)
    return m.group(1).lower() if m else ""


def _is_ip_literal(host: str) -> bool:
    return bool(re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", host)) or ":" in host  # IPv6


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return DEFAULT_CONFIG
    import yaml
    with CONFIG_PATH.open() as f:
        user = yaml.safe_load(f) or {}
    merged = {**DEFAULT_CONFIG, **user}
    return merged


def check_write(target_path: str, cwd: str, cfg: dict | None = None) -> Verdict:
    cfg = cfg or load_config()
    if _is_under(target_path, cfg["allowed_write_roots"], cwd):
        return Verdict(True)
    return Verdict(
        False,
        f"write target '{target_path}' is outside allowed roots: {cfg['allowed_write_roots']}. "
        f"Add to allowed_write_roots in {CONFIG_PATH} or run with explicit scope.",
    )


def check_network(command: str, cfg: dict | None = None) -> Verdict:
    cfg = cfg or load_config()
    urls = _extract_urls(command)
    if not urls:
        return Verdict(True)

    allowed = {h.lower() for h in cfg["allowed_network_hosts"]}
    for url in urls:
        host = _host(url)
        if not host:
            return Verdict(False, f"network call to unparseable URL: {url}")
        if cfg.get("block_curl_to_ip_literal", True) and _is_ip_literal(host):
            return Verdict(False, f"network call to IP literal blocked: {host}")
        if host not in allowed and not any(host.endswith("." + a) for a in allowed):
            return Verdict(
                False,
                f"network call to non-allowlisted host '{host}'. "
                f"Add to allowed_network_hosts in {CONFIG_PATH}.",
            )
    return Verdict(True)


def check_kill(pid: int | str, cfg: dict | None = None) -> Verdict:
    cfg = cfg or load_config()
    if cfg.get("require_confirmation_for_kill", True):
        return Verdict(
            False,
            f"kill of pid {pid} requires explicit confirmation. "
            f"Set require_confirmation_for_kill: false to override (not recommended).",
        )
    return Verdict(True)


def evaluate(action: str, payload: dict, cwd: str | None = None) -> Verdict:
    """Dispatch to the right gate based on action name."""
    cwd = cwd or os.getcwd()
    if action == "write_file":
        return check_write(payload.get("path", ""), cwd)
    if action == "patch":
        return check_write(payload.get("path", ""), cwd)
    if action == "terminal":
        return check_network(payload.get("command", ""))
    if action == "process_kill":
        return check_kill(payload.get("pid", 0))
    if action == "browser":
        # Browser navigation: block IPs and unknown hosts, like network calls.
        # check_network only matches URLs with a scheme, so construct one.
        host = payload.get("host", "") or payload.get("url", "")
        if not host:
            return Verdict(True, "no host in browser payload")
        url = host if "://" in host else f"https://{host}/"
        return check_network(f"GET {url}")
    return Verdict(True, f"no gate for action {action}")
