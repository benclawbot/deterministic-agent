"""JSON Schema definitions for tool outputs.

The schema envelope wraps every tool result so downstream agents (the model,
subagents, lint checks) can rely on a typed shape instead of re-parsing
prose.

Each tool schema has two parts:
- `envelope`: the wrapper every tool returns (status, payload, truncated, error)
- `payload`: the tool-specific body

Adding a tool = adding one entry to TOOL_SCHEMAS. Hooks just call
`validate(tool_name, result_dict)` and exit 0/2.
"""
from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator

ENVELOPE_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["status", "payload"],
    "properties": {
        "status": {"enum": ["ok", "error", "truncated"]},
        "payload": {"type": "object"},
        "truncated": {"type": "boolean"},
        "error": {"type": ["string", "null"]},
    },
    "additionalProperties": False,
}

# Per-tool payload schemas. Keep tight; the point is determinism.
TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "terminal": {
        "type": "object",
        "required": ["output", "exit_code"],
        "properties": {
            "output": {"type": "string"},
            "exit_code": {"type": "integer"},
            "cwd": {"type": "string"},
            "duration_s": {"type": "number"},
        },
        "additionalProperties": True,
    },
    "web_search": {
        "type": "object",
        "required": ["results"],
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["url", "title"],
                    "properties": {
                        "url": {"type": "string", "format": "uri"},
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
            },
        },
        "additionalProperties": False,
    },
    "web_extract": {
        "type": "object",
        "required": ["results"],
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["url", "content"],
                    "properties": {
                        "url": {"type": "string"},
                        "title": {"type": "string"},
                        "content": {"type": "string"},
                        "truncated": {"type": "boolean"},
                        "error": {"type": ["string", "null"]},
                    },
                    "additionalProperties": False,
                },
            },
        },
        "additionalProperties": False,
    },
    "read_file": {
        "type": "object",
        "required": ["content", "total_lines"],
        "properties": {
            "content": {"type": "string"},
            "total_lines": {"type": "integer", "minimum": 0},
            "next_offset": {"type": ["integer", "null"]},
        },
        "additionalProperties": False,
    },
    "search_files": {
        "type": "object",
        "required": ["matches"],
        "properties": {
            "matches": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["path"],
                    "properties": {
                        "path": {"type": "string"},
                        "line": {"type": "integer"},
                        "content": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
            },
        },
        "additionalProperties": False,
    },
}


def envelope() -> dict[str, Any]:
    """Return the standard envelope schema (for hook self-description)."""
    return ENVELOPE_SCHEMA


def payload_schema(tool_name: str) -> dict[str, Any] | None:
    """Return the payload schema for a tool, or None if unknown."""
    return TOOL_SCHEMAS.get(tool_name)


def validate(tool_name: str, result: dict[str, Any]) -> tuple[bool, str | None]:
    """Validate a tool result against envelope + payload schema.

    Returns (ok, error_message). Hooks translate this into exit code:
    ok=True  -> exit 0 (allow)
    ok=False -> exit 2 (block, with stderr = error_message)
    """
    try:
        Draft202012Validator(ENVELOPE_SCHEMA).validate(result)
    except Exception as e:
        return False, f"envelope violation in {tool_name}: {e.message}"

    schema = TOOL_SCHEMAS.get(tool_name)
    if schema is None:
        return True, None  # unknown tool: envelope-only check passed

    try:
        Draft202012Validator(schema).validate(result.get("payload", {}))
    except Exception as e:
        return False, f"payload violation in {tool_name}: {e.message}"

    return True, None
